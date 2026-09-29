"""Shared state can participate in the transaction accepting a human answer."""

import asyncio
from dataclasses import replace
import os
from uuid import uuid4

import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    field,
    resolve_read,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.exceptions import SharedStateRuntimeError
from edsl.sharedstate.postgres import (
    PostgresStateBackend,
    checkpoints,
    definitions,
    events,
)
from edsl.sharedstate.steps import StepContext


@pytest.fixture
def database():
    url = os.environ.get("EDSL_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("EDSL_TEST_POSTGRES_URL is not configured")
    base = create_engine(url, pool_pre_ping=True)
    schema = "state_transaction_" + uuid4().hex
    with base.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = base.execution_options(schema_translate_map={None: schema})
    answers = Table(
        "human_answers",
        MetaData(),
        Column("response_id", Integer, primary_key=True),
        Column("answer", Text, nullable=False),
    )
    try:
        PostgresStateBackend.create_schema(engine)
        answers.create(engine)
        yield engine, answers, schema
    finally:
        with base.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        base.dispose()


@pytest.fixture
def state():
    machine = Machine(
        name="Counter",
        constants={},
        fields={"count": state_field(T.integer(), 0)},
        commands={
            "increment": Command(
                inputs={}, effects=(set_("count", field("count") + 1),)
            )
        },
        view={"count": field("count")},
        complete_when=field("count") >= 1,
    )
    return SharedStateMap(SharedState(counter=machine), state_id="human-counter")


def count_rows(conn, table):
    return conn.scalar(select(func.count()).select_from(table))


@pytest.mark.parametrize("finish", ["commit", "rollback", "answer_error"])
def test_answer_state_reads_and_checkpoints_share_commit(database, state, finish):
    engine, answers, _ = database
    target = state.by("room").counter
    with engine.connect() as conn:
        transaction = conn.begin()
        backend = PostgresStateBackend(state, conn, namespace="human-survey:test")
        backend.apply(resolve_write(target.increment(), StepContext({}, "response-1")))
        assert backend.read(
            resolve_read(target.read(), StepContext({}, "response-1"))
        ).value == {"count": 1}
        backend.finalize(target.is_complete(), "room", execution_id="response-1")
        assert backend.is_finalized("room", "counter")
        backend.pin_checkpoint("served-page")
        conn.execute(answers.insert().values(response_id=1, answer="accepted"))
        # State methods must not make either half visible ahead of the answer commit.
        with engine.connect() as observer:
            assert all(
                count_rows(observer, table) == 0
                for table in (answers, definitions, events, checkpoints)
            )
        if finish == "commit":
            transaction.commit()
        else:
            if finish == "answer_error":
                with pytest.raises(IntegrityError):
                    conn.execute(
                        answers.insert().values(response_id=1, answer="duplicate")
                    )
            transaction.rollback()
    with engine.connect() as observer:
        expected = (1, 1, 3, 1) if finish == "commit" else (0, 0, 0, 0)
        assert (
            tuple(
                count_rows(observer, table)
                for table in (answers, definitions, events, checkpoints)
            )
            == expected
        )


def test_failed_operation_rolls_back_its_savepoint(database, state, monkeypatch):
    engine, answers, _ = database
    with engine.begin() as conn:
        backend = PostgresStateBackend(state, conn, namespace="human-survey:test")
        append = backend._append

        def fail_after_writes(*args):
            append(*args)
            raise RuntimeError("interrupted after event append")

        monkeypatch.setattr(backend, "_append", fail_after_writes)
        with pytest.raises(RuntimeError, match="interrupted"):
            backend.apply(
                resolve_write(
                    state.by("room").counter.increment(), StepContext({}, "response-1")
                )
            )
        assert backend.checkpoint() == 0
        assert backend.snapshot("room").state["counter"]["count"] == 0
        conn.execute(answers.insert().values(response_id=1, answer="unrelated answer"))
    with engine.connect() as observer:
        assert count_rows(observer, answers) == 1
        assert count_rows(observer, events) == 0


@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_backend_expires_with_caller_transaction(database, state, finish):
    engine, _, _ = database
    with engine.connect() as conn:
        with pytest.raises(SharedStateRuntimeError, match="active caller-owned"):
            PostgresStateBackend(state, conn, namespace="human-survey:test")
        transaction = conn.begin()
        backend = PostgresStateBackend(state, conn, namespace="human-survey:test")
        getattr(transaction, finish)()
        with pytest.raises(SharedStateRuntimeError, match="ended or changed"):
            backend.snapshot("room")
        with conn.begin():
            with pytest.raises(SharedStateRuntimeError, match="ended or changed"):
                backend.checkpoint()
            assert (
                PostgresStateBackend(
                    state, conn, namespace="human-survey:test"
                ).checkpoint()
                == 0
            )


def test_caller_savepoint_rollback_discards_state(database, state):
    engine, answers, _ = database
    with engine.begin() as conn:
        conn.execute(answers.insert().values(response_id=1, answer="earlier answer"))
        savepoint = conn.begin_nested()
        backend = PostgresStateBackend(state, conn, namespace="human-survey:test")
        backend.apply(
            resolve_write(
                state.by("room").counter.increment(), StepContext({}, "response-2")
            )
        )
        savepoint.rollback()
        with pytest.raises(SharedStateRuntimeError, match="ended or changed"):
            backend.history()
    with engine.connect() as observer:
        assert count_rows(observer, answers) == 1
        assert count_rows(observer, definitions) == 0
        assert count_rows(observer, events) == 0


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
def test_async_session_answer_and_state_are_atomic(database, state, failure):
    pytest.importorskip("asyncpg")
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine, answers, schema = database

    async def request():
        async_engine = create_async_engine(
            engine.url.set(drivername="postgresql+asyncpg"),
            execution_options={"schema_translate_map": {None: schema}},
        )
        try:
            async with AsyncSession(async_engine) as session:
                async with session.begin():

                    def write(sync_session):
                        backend = PostgresStateBackend(
                            state,
                            sync_session.connection(),
                            namespace="human-survey:test",
                        )
                        backend.apply(
                            resolve_write(
                                state.by("room").counter.increment(),
                                StepContext({}, "response-1"),
                            )
                        )

                    await session.run_sync(write)
                    await session.execute(
                        answers.insert().values(response_id=1, answer="accepted")
                    )
                    if failure:
                        raise failure("request interrupted before commit")
        finally:
            await async_engine.dispose()

    if failure:
        with pytest.raises(failure, match="request interrupted"):
            asyncio.run(request())
    else:
        asyncio.run(request())
    with engine.connect() as observer:
        assert count_rows(observer, answers) == (0 if failure else 1)
        assert count_rows(observer, events) == (0 if failure else 1)


def test_reconstructed_request_replays_read_and_answer(database, state):
    engine, _, _ = database
    target = state.by("room").counter
    read = resolve_read(target.read(), StepContext({}, "response-1"))
    write = resolve_write(target.increment(), StepContext({}, "response-1"))
    with engine.begin() as conn:
        first = PostgresStateBackend(state, conn, namespace="human-survey:test")
        observation = first.read(read)
        assert observation.value == {"count": 0}
    # Another respondent changes the live state after the first page was served.
    with engine.begin() as conn:
        other = PostgresStateBackend(state, conn, namespace="human-survey:test")
        other.apply(resolve_write(target.increment(), StepContext({}, "response-2")))
    for _ in range(2):
        with engine.begin() as conn:
            replay = PostgresStateBackend(state, conn, namespace="human-survey:test")
            assert replay.read(read) == observation
            replay.apply(write)
            with pytest.raises(SharedStateRuntimeError, match="idempotency"):
                replay.apply(replace(write, runtime_context={"changed": True}))
    reopened = PostgresStateBackend(state, engine, namespace="human-survey:test")
    assert reopened.snapshot("room").state["counter"]["count"] == 2
    assert len(reopened.history()) == 3  # One pinned read, two distinct answers.
