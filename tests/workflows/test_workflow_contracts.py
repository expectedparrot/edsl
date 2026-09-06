"""Scientific and recovery contracts spanning workflow features."""

import json

import pytest

from edsl import Agent, QuestionFreeText, QuestionNumerical, Survey
from edsl.instructions import Instruction
from edsl.sharedstate import SQLiteStateBackend, resolve_write
from edsl.sharedstate.steps import StepContext
from edsl.workflows import (
    Collection,
    HumanWorkflow,
    SQLiteWorkflowStore,
    Workflow,
    WorkflowCoordinator,
    WorkflowSimulation,
    quorum,
    role,
    seeded_uniform,
)


def question(name="reply", text="Reply"):
    return QuestionFreeText(question_name=name, question_text=text)


def setup_ledger(tmp_path, *, blocked=False):
    state_map = Collection("contract-ledger")
    ledger = state_map.by("study").collection
    backend = SQLiteStateBackend(state_map, tmp_path / "state.sqlite")
    q = question()
    builder = Workflow("response contract")
    first = builder.step("first", Survey([q])) if blocked else None
    builder.step(
        "respond",
        Survey([q]),
        after=first,
        writes=(ledger.add(actor="person", value=q.answer),),
    )
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        builder.compile(), store, state_backends={state_map.state_id: backend}
    )
    instance = coordinator.launch([Agent(name="person")])
    item = store.items(instance, step_name="respond")[0]["id"]
    return coordinator, instance, item, backend, ledger


def test_rejected_submission_cannot_mutate_state(tmp_path):
    c, _, item, backend, _ = setup_ledger(tmp_path, blocked=True)
    with pytest.raises(ValueError, match="cannot accept"):
        c.submit(item, {"reply": "too early"}, idempotency_key="request")
    assert backend.snapshot("study").state["collection"]["items"] == []
    assert c.store.submission_intent(item) is None


def test_crash_after_effect_commit_replays_the_accepted_answer(tmp_path, monkeypatch):
    c, instance, item, backend, _ = setup_ledger(tmp_path)
    apply = backend.apply

    def commit_then_crash(operation):
        apply(operation)
        raise RuntimeError("lost acknowledgement")

    monkeypatch.setattr(backend, "apply", commit_then_crash)
    with pytest.raises(RuntimeError, match="lost acknowledgement"):
        c.submit(item, {"reply": "accepted"}, idempotency_key="request")
    assert c.store.item(item)["status"] == "committing"
    with pytest.raises(ValueError, match="different content"):
        c.submit(item, {"reply": "regenerated"}, idempotency_key="request")
    monkeypatch.setattr(backend, "apply", apply)
    restarted = WorkflowCoordinator(
        HumanWorkflow.from_dict(json.loads(json.dumps(c.workflow.to_dict()))),
        SQLiteWorkflowStore(tmp_path / "workflow.sqlite"),
        state_backends=c.state_backends,
    )

    class MustNotAnswerAgain:
        def answer(self, agent, opened):
            pytest.fail("recovery must not regenerate an accepted response")

    WorkflowSimulation(
        restarted, {"person": Agent(name="person")}, MustNotAnswerAgain()
    ).run(instance, resume=True)
    assert restarted.store.item_answers(item) == {"reply": "accepted"}
    assert backend.snapshot("study").state["collection"]["items"] == [
        {"actor": "person", "value": "accepted"}
    ]
    assert restarted.store.pending_effects(item) == []


def test_stale_worker_cannot_submit_after_replacement_lease(tmp_path):
    c, _, item, backend, _ = setup_ledger(tmp_path)
    stale = c.store.start_attempt(item, lease_seconds=300)
    with c.store.connect() as db:
        db.execute(
            "UPDATE workflow_attempts SET lease_expires_at = '2000-01-01' WHERE id = ?",
            (stale["id"],),
        )
    active = c.store.start_attempt(item, lease_seconds=300)
    with pytest.raises(ValueError, match="current lease"):
        c.submit(
            item, {"reply": "stale"}, idempotency_key="old", attempt_id=stale["id"]
        )
    with pytest.raises(ValueError, match="identify the attempt"):
        c.submit(item, {"reply": "anonymous worker"}, idempotency_key="anonymous")
    assert backend.history() == []
    c.submit(item, {"reply": "current"}, idempotency_key="new", attempt_id=active["id"])
    assert c.store.item_answers(item) == {"reply": "current"}


def test_repeated_submission_requires_identical_content(tmp_path):
    c, _, item, backend, _ = setup_ledger(tmp_path)
    c.submit(item, {"reply": "first"}, idempotency_key="request")
    c.submit(item, {"reply": "first"}, idempotency_key="request")
    with pytest.raises(ValueError, match="different content"):
        c.submit(item, {"reply": "different"}, idempotency_key="request")
    with pytest.raises(ValueError, match="accepted submission is immutable"):
        c.submit(item, {"reply": "first"}, idempotency_key="different-request")
    assert len(backend.history()) == 1


def test_reopen_uses_the_saved_observation(tmp_path):
    c, _, _, backend, ledger = setup_ledger(tmp_path)
    builder = Workflow("observation")
    builder.step(
        "observe",
        Survey([question(text="Seen {{ shared_state.collection.items }}")]),
        reads=(ledger.read(),),
    )
    c = WorkflowCoordinator(builder.compile(), c.store, state_backends=c.state_backends)
    instance = c.launch([Agent(name="observer")])
    item = c.store.items(instance)[0]["id"]
    before = c.open(item).survey.to_dict()
    backend.apply(
        resolve_write(
            ledger.add(actor="another", value="new information"),
            StepContext({}, "outside"),
        )
    )
    after = c.open(item).survey.to_dict()
    assert after == before == c.store.rendered_item(item)["survey"]
    assert sum(event["kind"] == "read" for event in backend.history()) == 1


def test_render_preserves_survey_rules_memory_and_instructions(tmp_path):
    consent, detail = question("consent"), question("detail")
    survey = Survey(
        [Instruction(name="intro", text="Study instructions"), consent, detail]
    )
    survey.add_stop_rule(consent, "{{ consent.answer }} == 'no'")
    survey.set_full_memory_mode()
    builder = Workflow("survey composition")
    builder.step("interview", survey)
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "survey.sqlite")
    )
    instance = c.launch([Agent(name="person")])
    rendered = c.open(c.store.items(instance)[0]["id"]).survey
    assert rendered.to_dict() == survey.to_dict()


@pytest.mark.parametrize(
    "template",
    [
        "{{ workflow.derived }}",
        "{{ workflow['derived'] }}",
        "{{ workflow.get('derived') }}",
    ],
)
def test_private_derived_values_are_absent_from_runtime_context(tmp_path, template):
    builder = Workflow("private statistic")
    private = builder.step(
        "private",
        Survey([QuestionNumerical(question_name="bid", question_text="Bid")]),
        assigned_to=role("bidder"),
        visible_to=role("facilitator"),
    )
    builder.derive("secret", mean=private.outputs("bid").mean())
    builder.step(
        "observe",
        Survey([question(text=template)]),
        assigned_to=role("observer"),
        after=private,
    )
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "visibility.sqlite")
    )
    instance = c.launch(
        [
            Agent(name="bidder", traits={"role": "bidder"}),
            Agent(name="observer", traits={"role": "observer"}),
        ]
    )
    c.submit(
        c.store.items(instance, step_name="private")[0]["id"],
        {"bid": 12345},
        idempotency_key="bid",
    )
    rendered = (
        c.open(c.store.items(instance, step_name="observe")[0]["id"])
        .survey.questions[0]
        .question_text
    )
    assert "12345" not in rendered
    assert "secret" not in rendered


@pytest.mark.parametrize(
    "reference",
    [
        "workflow.derived.secret.mean",
        "workflow.derived['secret']['mean']",
        'workflow.derived["secret"]["mean"]',
        "workflow.derived.get('secret').get('mean')",
    ],
)
def test_visibility_checks_parse_reference_syntax(tmp_path, reference):
    builder = Workflow("private statistic")
    private = builder.step(
        "private",
        Survey([QuestionNumerical(question_name="bid", question_text="Bid")]),
        visible_to=role("facilitator"),
    )
    builder.derive("secret", mean=private.outputs("bid").mean())
    builder.step(
        "observe",
        Survey([question(text="{{ " + reference + " }}")]),
        assigned_to=role("observer"),
        after=private,
    )
    with pytest.raises(ValueError, match="output visibility"):
        builder.compile()


def test_quorum_success_releases_normal_dependencies(tmp_path):
    builder = Workflow("quorum")
    votes = builder.step(
        "vote", Survey([question()]), assigned_to=role("voter"), completion=quorum(1)
    )
    builder.step("report", Survey([question()]), assigned_to=role("chair"), after=votes)
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "quorum.sqlite")
    )
    instance = c.launch(
        [
            Agent(name="a", traits={"role": "voter"}),
            Agent(name="b", traits={"role": "voter"}),
            Agent(name="chair", traits={"role": "chair"}),
        ]
    )
    c.submit(
        c.store.items(instance, step_name="vote")[0]["id"],
        {"reply": "yes"},
        idempotency_key="vote",
    )
    assert c.store.items(instance, step_name="report")[0]["status"] == "ready"
    assert [row["status"] for row in c.store.items(instance, step_name="vote")] == [
        "completed",
        "superseded",
    ]


def test_workflow_binding_rejects_changed_definition(tmp_path):
    builder = Workflow("version")
    builder.step("respond", Survey([question()]))
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "version.sqlite")
    )
    instance = c.launch([Agent(name="person")])
    changed = Workflow("version")
    changed.step("respond", Survey([question(text="Changed question")]))
    restarted = WorkflowCoordinator(changed.compile(), c.store)
    with pytest.raises(ValueError, match="definition changed"):
        restarted.open(c.store.items(instance)[0]["id"])


def test_restore_loads_the_pinned_workflow_snapshot(tmp_path):
    builder = Workflow("restored")
    builder.step("respond", Survey([question(text="Original")]))
    store = SQLiteWorkflowStore(tmp_path / "restore.sqlite")
    original = WorkflowCoordinator(builder.compile(), store)
    instance = original.launch([Agent(name="person")])
    restored = WorkflowCoordinator.restore(instance, store)
    item = store.items(instance)[0]
    assert restored.open(item["id"]).survey.questions[0].question_text == "Original"
    assert restored.workflow.to_dict() == store.definition(instance)


def test_explicit_random_seed_reproduces_new_instances(tmp_path):
    builder = Workflow("randomization")
    builder.step("respond", Survey([question()]))
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "random.sqlite")
    )
    first = c.launch([Agent(name="person")], random_seed="scientific-seed")
    second = c.launch([Agent(name="person")], random_seed="scientific-seed")
    assert first != second
    draw = seeded_uniform(key="allocation")
    assert c._evaluate_expression(first, draw) == c._evaluate_expression(second, draw)


@pytest.mark.parametrize(
    "boundary", ["before_effect", "after_effect_record", "after_completion"]
)
def test_recovery_at_submission_boundaries(tmp_path, monkeypatch, boundary):
    c, instance, item, backend, _ = setup_ledger(tmp_path)
    attempt = c.store.start_attempt(item, lease_seconds=300)
    if boundary == "before_effect":
        original = backend.apply

        def fail(*args):
            raise RuntimeError("injected crash")

        target, method = backend, "apply"
    else:
        method = "effect_applied" if boundary == "after_effect_record" else "complete"
        target = c.store
        original = getattr(target, method)

        def fail(*args):
            original(*args)
            raise RuntimeError("injected crash")

    monkeypatch.setattr(target, method, fail)
    with pytest.raises(RuntimeError, match="injected crash"):
        c.submit(
            item,
            {"reply": "accepted"},
            idempotency_key="accepted",
            attempt_id=attempt["id"],
        )
    monkeypatch.setattr(target, method, original)
    c.recover(instance)
    assert c.store.item_answers(item) == {"reply": "accepted"}
    assert c.store.pending_effects(item) == []
    assert len(backend.history()) == 1
    assert c.store.attempts(item)[0]["status"] == "succeeded"
    assert (
        c.store.rows("SELECT status FROM workflow_instances WHERE id = ?", (instance,))[
            0
        ]["status"]
        == "completed"
    )


def test_partial_multi_effect_submission_is_recoverable(tmp_path, monkeypatch):
    _, _, _, backend, ledger = setup_ledger(tmp_path)
    builder = Workflow("two effects")
    q = question()
    builder.step(
        "respond",
        Survey([q]),
        writes=(
            ledger.add(actor="first", value=q.answer),
            ledger.add(actor="second", value=q.answer),
        ),
    )
    c = WorkflowCoordinator(
        builder.compile(),
        SQLiteWorkflowStore(tmp_path / "multi.sqlite"),
        state_backends={backend.state_map.state_id: backend},
    )
    instance = c.launch([Agent(name="person")])
    item = c.store.items(instance)[0]["id"]
    original = backend.apply

    def fail_second(operation):
        if operation.inputs["actor"] == "second":
            raise RuntimeError("second effect unavailable")
        return original(operation)

    monkeypatch.setattr(backend, "apply", fail_second)
    with pytest.raises(RuntimeError, match="second effect"):
        c.submit(item, {"reply": "accepted"}, idempotency_key="request")
    assert c.store.item_answers(item) is None
    assert len(c.store.pending_effects(item)) == 1
    monkeypatch.setattr(backend, "apply", original)
    c.recover(instance)
    assert backend.snapshot("study").state["collection"]["items"] == [
        {"actor": "first", "value": "accepted"},
        {"actor": "second", "value": "accepted"},
    ]


def test_duplicate_concurrent_submissions_have_one_effect(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    c, _, item, backend, _ = setup_ledger(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(c.submit, item, {"reply": "same"}, idempotency_key="same")
            for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=10)
    assert len(backend.history()) == 1
    assert len(c.store.rows("SELECT * FROM workflow_submissions")) == 1


def test_own_projection_does_not_release_other_fields_or_people(tmp_path):
    builder = Workflow("private payoffs")
    private = builder.step(
        "private",
        Survey([QuestionNumerical(question_name="bid", question_text="Bid")]),
        visible_to=role("facilitator"),
    )
    each = private.submissions.each("bid")
    outcome = builder.derive(
        "outcome", own=each.map(each.value), mean=private.outputs("bid").mean()
    )
    builder.step(
        "observe",
        Survey(
            [
                question(
                    text=outcome.field("own").for_participant()
                    + " Context: {{ workflow }}"
                )
            ]
        ),
        after=private,
    )
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "own.sqlite")
    )
    instance = c.launch([Agent(name="a"), Agent(name="b")])
    for item in c.store.items(instance, step_name="private"):
        c.submit(
            item["id"],
            {"bid": 12345 if item["participant_id"] == "a" else 54321},
            idempotency_key=item["id"],
        )
    item = next(
        row
        for row in c.store.items(instance, step_name="observe")
        if row["participant_id"] == "a"
    )
    text = c.open(item["id"]).survey.questions[0].question_text
    assert "12345" in text
    assert "54321" not in text
    assert "mean" not in text
    assert "33333" not in text


def test_projection_is_not_a_blanket_visibility_exemption():
    builder = Workflow("private statistic")
    private = builder.step(
        "private", Survey([question()]), visible_to=role("facilitator")
    )
    each = private.submissions.each("reply")
    outcome = builder.derive(
        "secret",
        own=each.map(each.value),
        count=private.outputs("reply").count_value("yes"),
    )
    builder.step(
        "observe",
        Survey(
            [
                question(
                    text=outcome.field("own").for_participant()
                    + outcome.field("count").template
                )
            ]
        ),
        after=private,
    )
    with pytest.raises(ValueError, match="output visibility"):
        builder.compile()


def test_compilation_detaches_from_mutable_authoring_objects():
    q = question()
    builder = Workflow("snapshot")
    builder.step("respond", Survey([q]))
    compiled = builder.compile()
    before = compiled.to_dict()
    q.question_text = "Changed later"
    builder.metadata["later"] = "added"
    assert compiled.to_dict() == before


def test_executor_resolution_is_pinned(tmp_path):
    c, _, item, _, _ = setup_ledger(tmp_path)
    c.store.record_executor(item, "llm", {"model": "first"})
    c.store.record_executor(item, "llm", {"model": "first"})
    with pytest.raises(ValueError, match="executor changed"):
        c.store.record_executor(item, "llm", {"model": "replacement"})
    assert c.store.executor(item) == {"kind": "llm", "options": {"model": "first"}}


def test_concrete_model_configuration_is_saved_and_pinned(tmp_path):
    from edsl import Model
    from edsl.workflows import EDSLAgentAnswerer

    c, instance, item, _, _ = setup_ledger(tmp_path)
    model = Model("test", canned_response="saved")
    WorkflowSimulation(
        c, {"person": Agent(name="person")}, EDSLAgentAnswerer(model)
    ).run(instance)
    assert c.store.model(item) == model.to_dict()
    with pytest.raises(ValueError, match="model changed"):
        c.store.record_model(item, Model("test", canned_response="changed").to_dict())


def test_backend_definition_must_match_the_workflow(tmp_path):
    c, _, _, backend, _ = setup_ledger(tmp_path)
    changed = Collection("different-state")
    replacement = SQLiteStateBackend(changed, tmp_path / "different.sqlite")
    with pytest.raises(ValueError, match="different definitions"):
        WorkflowCoordinator(
            c.workflow,
            c.store,
            state_backends={backend.state_map.state_id: replacement},
        )


def test_failed_assignment_validation_does_not_create_half_a_run(tmp_path):
    builder = Workflow("invalid roster")
    builder.step("respond", Survey([question()]), assigned_to=role("missing"))
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "missing.sqlite")
    )
    with pytest.raises(ValueError, match="no matching participant"):
        c.launch([Agent(name="person")])
    assert c.store.rows("SELECT * FROM workflow_instances") == []


def test_dynamic_aliases_cannot_read_private_derived_data(tmp_path):
    template = "{% set values = workflow.derived %}{{ values.get('secret', {}).get('mean', 'redacted') }}"
    test_private_derived_values_are_absent_from_runtime_context(tmp_path, template)


def test_simulation_only_consumes_its_instances_outbox(tmp_path):
    builder = Workflow("two runs")
    builder.step("respond", Survey([question()]))
    c = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "two.sqlite")
    )
    first = c.launch([Agent(name="first")])
    second = c.launch([Agent(name="second")])

    class FixedAnswer:
        def answer(self, agent, opened):
            return {"reply": "ok"}

    WorkflowSimulation(c, {"first": Agent(name="first")}, FixedAnswer()).run(first)
    assert c.store.items(second)[0]["status"] == "ready"
    assert len(c.store.pending_outbox(second)) == 1


def test_workflow_expressions_reject_python_booleans_and_invalid_arity():
    from edsl.workflows.definition import WorkflowExpression

    with pytest.raises(TypeError, match="truth value"):
        bool(seeded_uniform(key="draw"))
    with pytest.raises(TypeError, match="truth value"):
        bool(seeded_uniform(key="draw").at_most(0.5))
    with pytest.raises(ValueError, match="expects 2 arguments"):
        WorkflowExpression("add", (1,))


def test_version_one_definitions_import_but_cannot_silently_resume(tmp_path):
    builder = Workflow("old version")
    builder.step("respond", Survey([question()]))
    legacy = {**builder.compile().to_dict(), "version": 1}
    current = HumanWorkflow.from_dict(legacy)
    assert current.to_dict()["version"] == 2
    store = SQLiteWorkflowStore(tmp_path / "old.sqlite")
    store.create_instance("old", legacy, [("person", Agent(name="person").to_dict())])
    with pytest.raises(ValueError, match="definition changed"):
        WorkflowCoordinator(current, store).recover("old")


def test_humanize_poll_drains_a_superseded_external_task(tmp_path):
    from edsl.workflows import HumanizeDeliveryAdapter

    builder = Workflow("external quorum")
    builder.step(
        "vote", Survey([question()]), assigned_to=role("voter"), completion=quorum(1)
    )
    store = SQLiteWorkflowStore(tmp_path / "external.sqlite")
    coordinator = WorkflowCoordinator(builder.compile(), store)
    instance = coordinator.launch(
        [
            Agent(name="first", traits={"role": "voter"}),
            Agent(name="late", traits={"role": "voter"}),
        ]
    )
    first, late = store.items(instance)
    store.record_external_task(
        provider="humanize", work_item_id=late["id"], resource_id="late-survey"
    )
    coordinator.submit(
        first["id"], {"reply": "enough"}, idempotency_key="first-response"
    )

    class MustNotPoll:
        def get_human_survey(self, resource_id):
            pytest.fail("superseded external work must not be polled")

    assert HumanizeDeliveryAdapter(coordinator, MustNotPoll()).poll_completed() == 0
    assert (
        store.external_tasks("humanize", status="cancelled")[0]["work_item_id"]
        == late["id"]
    )
