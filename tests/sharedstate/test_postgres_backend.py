"""Run with EDSL_TEST_POSTGRES_URL pointing at a disposable/local test database."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from uuid import uuid4

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    field,
    set_,
    state_field,
    resolve_read,
    resolve_write,
)
from edsl.sharedstate.steps import StepContext
from edsl.sharedstate.exceptions import SharedStateRuntimeError


@pytest.fixture
def database():
    url = os.environ.get("EDSL_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("EDSL_TEST_POSTGRES_URL is not configured")
    from sqlalchemy import create_engine, delete
    from edsl.sharedstate.postgres import PostgresStateBackend, definitions, events

    engine = create_engine(url, pool_pre_ping=True)
    PostgresStateBackend.create_schema(engine)
    namespace = "test-" + str(uuid4())
    yield engine, namespace
    with engine.begin() as conn:
        for table in (events, definitions):
            conn.execute(
                delete(table).where(
                    table.c.namespace.in_([namespace, namespace + "-other"])
                )
            )
    engine.dispose()


def counter():
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
        complete_when=field("count") >= 2,
    )
    return SharedStateMap(SharedState(counter=machine), state_id="same-client-id")


def test_concurrent_writes_deduplicate_and_namespaces_isolate(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    step = state.by("room").counter.increment()
    operations = [
        resolve_write(step, StepContext({}, f"worker-{i}")) for i in range(20)
    ]

    def write(operation):
        return PostgresStateBackend(state, engine, namespace=namespace).apply(operation)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, operations + operations))
    reopened = PostgresStateBackend(state, engine, namespace=namespace)
    assert reopened.snapshot("room").state["counter"]["count"] == 20
    assert reopened.snapshot("room").version == 20
    assert len(reopened.history()) == 20
    isolated = PostgresStateBackend(state, engine, namespace=namespace + "-other")
    assert isolated.snapshot("room").version == 0
    assert reopened.snapshot("another-room").version == 0
    with pytest.raises(SharedStateRuntimeError, match="idempotency"):
        reopened.apply(replace(operations[0], runtime_context={"different": True}))


def test_postgres_matches_sqlite_snapshots_reads_and_close(database, tmp_path):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    target = state.by("room").counter
    backends = [
        SQLiteStateBackend(state, tmp_path / "state.sqlite"),
        PostgresStateBackend(state, engine, namespace=namespace),
    ]
    outputs = []
    for backend in backends:
        backend.apply(resolve_write(target.increment(), StepContext({}, "first")))
        checkpoint = backend.checkpoint()
        backend.apply(resolve_write(target.increment(), StepContext({}, "second")))
        observation = backend.read(
            resolve_read(target.read(), StepContext({}, "reader")),
            at_sequence=checkpoint,
        )
        assert observation.value == {"count": 1}
        assert observation.version == 1
        first_close = backend.finalize(
            target.is_complete(), "room", execution_id="closer"
        )
        duplicate = backend.finalize(
            target.is_complete(), "room", execution_id="closer"
        )
        assert first_close.observed_version == duplicate.observed_version == 3
        outputs.append(
            (
                backend.snapshot("room"),
                [(e["kind"], e["version"]) for e in backend.history()],
            )
        )
    assert outputs[0] == outputs[1]


def test_definition_changes_and_failed_commands_do_not_commit(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    operation = resolve_write(
        state.by("room").counter.increment(), StepContext({}, "writer")
    )
    with pytest.raises(Exception):
        backend.apply(replace(operation, command="does_not_exist"))
    assert backend.checkpoint() == 0
    backend.apply(operation)
    changed = SharedStateMap(
        SharedState(
            counter=replace(
                state.definition.machines["counter"], view={"other": field("count")}
            )
        ),
        state_id=state.state_id,
    )
    with pytest.raises(SharedStateRuntimeError, match="definition changed"):
        PostgresStateBackend(changed, engine, namespace=namespace)
    assert backend.snapshot("room").version == 1
