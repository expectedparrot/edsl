import json

import pytest

from edsl import (
    Agent,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    QuestionYesNo,
    Survey,
)
from edsl.sharedstate import SQLiteStateBackend, current
from edsl.workflows import (
    Artifact,
    Collection,
    HumanWorkflow,
    SQLiteWorkflowStore,
    Workflow,
    WorkflowCoordinator,
    WorkflowExpression,
    WorkflowSimulation,
    ExecutionPlan,
    all_of,
    any_of,
    chance,
    not_,
    quorum,
    role,
    human,
    llm,
    choose,
    match,
)


class EditorialAnswers:
    def answer(self, agent, opened):
        if opened.step_name == "draft":
            return {"copy": "The garden opens Saturday."}
        if opened.step_name == "review":
            assert (
                "The garden opens Saturday." in opened.survey.questions[0].question_text
            )
            return {"approved": "No"}
        if opened.step_name == "revision":
            return {"copy_2": "Families are warmly invited to the garden Saturday."}
        assert opened.step_name == "publish"
        assert "Families are warmly invited" in opened.survey.questions[0].question_text
        return {"publication": "Published"}


class ApprovedEditorialAnswers:
    def answer(self, agent, opened):
        if opened.step_name == "draft":
            return {"copy": "Families are invited to the garden Saturday."}
        if opened.step_name == "review":
            return {"approved": "Yes"}
        assert opened.step_name == "publish"
        assert "Families are invited" in opened.survey.questions[0].question_text
        return {"publication": "Published original"}


def build_typed_editorial_workflow():
    builder = Workflow("Typed editorial")
    draft_question = QuestionFreeText(
        question_name="copy", question_text="Draft the announcement."
    )
    draft = builder.step("draft", Survey([draft_question]), assigned_to=role("writer"))
    approval = QuestionYesNo(
        question_name="approved",
        question_text=f"Approve this copy? {draft.answer(draft_question).template}",
    )
    review = builder.step(
        "review", Survey([approval]), assigned_to=role("editor"), after=draft
    )
    revised_copy = QuestionFreeText(
        question_name="copy_2",
        question_text=f"Revise this copy: {draft.answer('copy').template}",
    )
    revision = builder.step(
        "revision",
        Survey([revised_copy]),
        assigned_to=role("writer"),
        when=review.answer(approval).equals("No"),
    )
    publication = QuestionFreeText(
        question_name="publication",
        question_text=(
            "Publish the accepted copy: "
            f"{revision.answer('copy_2').template_or(draft.answer('copy'))}"
        ),
    )
    builder.step(
        "publish",
        Survey([publication]),
        assigned_to=role("publisher"),
        when=any_of(
            review.answer("approved").equals("Yes"),
            revision.completed,
        ),
    )
    return builder.compile()


def test_typed_branch_join_routes_revision_into_one_publisher_step(tmp_path):
    workflow = HumanWorkflow.from_dict(build_typed_editorial_workflow().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [
        Agent(name="writer", traits={"role": "writer"}),
        Agent(name="editor", traits={"role": "editor"}),
        Agent(name="publisher", traits={"role": "publisher"}),
    ]
    instance_id = coordinator.launch(agents)
    simulation = WorkflowSimulation(
        coordinator, {agent.name: agent for agent in agents}, EditorialAnswers()
    )

    simulation.run(instance_id)

    assert [item["step_name"] for item in store.items(instance_id)] == [
        "draft",
        "review",
        "revision",
        "publish",
    ]
    assert all(item["status"] == "completed" for item in store.items(instance_id))


def test_typed_branch_join_uses_original_when_revision_is_skipped(tmp_path):
    workflow = build_typed_editorial_workflow()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [
        Agent(name="writer", traits={"role": "writer"}),
        Agent(name="editor", traits={"role": "editor"}),
        Agent(name="publisher", traits={"role": "publisher"}),
    ]
    instance_id = coordinator.launch(agents)
    WorkflowSimulation(
        coordinator,
        {agent.name: agent for agent in agents},
        ApprovedEditorialAnswers(),
    ).run(instance_id)

    statuses = {item["step_name"]: item["status"] for item in store.items(instance_id)}
    assert statuses == {
        "draft": "completed",
        "review": "completed",
        "revision": "skipped",
        "publish": "completed",
    }


def test_condition_combinators_round_trip():
    workflow = build_typed_editorial_workflow()
    condition = workflow.step("publish").enabled_when
    restored = HumanWorkflow.from_dict(workflow.to_dict()).step("publish").enabled_when
    assert restored == condition
    assert all_of(condition, not_(workflow.step("revision").enabled_when)).dependencies


def test_settled_dependency_waits_without_propagating_skip(tmp_path):
    builder = Workflow("Optional review")
    first_q = QuestionYesNo(question_name="needed", question_text="Review needed?")
    first = builder.step("first", Survey([first_q]), assigned_to=role("author"))
    review_q = QuestionFreeText(question_name="review", question_text="Review.")
    review = builder.step(
        "review", Survey([review_q]), assigned_to=role("reviewer"),
        after=first, when=first.answer(first_q).equals("Yes"),
    )
    final_q = QuestionFreeText(question_name="final", question_text="Finish.")
    builder.step(
        "final", Survey([final_q]), assigned_to=role("author"),
        after_settled=review,
    )
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    assert workflow.step("final").settled_after == ("review",)
    store = SQLiteWorkflowStore(tmp_path / "settled.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [Agent(name="a", traits={"role": "author"}), Agent(name="r", traits={"role": "reviewer"})]

    class Answers:
        def answer(self, agent, opened):
            return {"needed": "No"} if opened.step_name == "first" else {"final": "done"}

    instance = coordinator.launch(agents)
    WorkflowSimulation(coordinator, {a.name: a for a in agents}, Answers()).run(instance)
    assert {i["step_name"]: i["status"] for i in store.items(instance)} == {
        "first": "completed", "review": "skipped", "final": "completed"
    }


def test_execution_plan_round_trip_and_resolves_one_executor():
    plan = (ExecutionPlan()
            .bind(role("researcher"), human(channel="email"))
            .bind(role("coder"), llm(model_policy="coding")))
    restored = ExecutionPlan.from_dict(plan.to_dict())
    assert restored.resolve({"role": "researcher"}).kind == "human"
    assert restored.resolve({"role": "coder"}).options == {"model_policy": "coding"}


def test_piecewise_single_answer_expression_round_trips_and_evaluates(tmp_path):
    builder = Workflow("Payoff")
    q = QuestionNumerical(question_name="offer", question_text="Offer", min_value=0, max_value=10)
    offer = builder.step("offer", Survey([q]), assigned_to=role("player"))
    accepted_q = QuestionYesNo(question_name="accepted", question_text="Accept?")
    accepted = builder.step("accept", Survey([accepted_q]), assigned_to=role("judge"), after=offer)
    payoff = builder.derive("payoff", value=choose(accepted.answer("accepted").value.compare_equals("Yes"), 10 - offer.answer("offer").value, 0))
    report = QuestionFreeText(question_name="report", question_text=payoff.field("value").template)
    builder.step("report", Survey([report]), assigned_to=role("judge"), after=accepted)
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "payoff.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [Agent(name="p", traits={"role": "player"}), Agent(name="j", traits={"role": "judge"})]
    class Answers:
        def answer(self, agent, opened):
            return {"offer": 4} if opened.step_name == "offer" else ({"accepted": "Yes"} if opened.step_name == "accept" else {"report": "6"})
    instance = coordinator.launch(agents)
    WorkflowSimulation(coordinator, {a.name: a for a in agents}, Answers()).run(instance)
    rendered = store.rendered_item(store.items(instance, step_name="report")[0]["id"])
    assert rendered["survey"]["questions"][0]["question_text"] == "6"


def test_matching_plan_round_trip_and_groups_by_stable_identity():
    agents = [Agent(name=name, traits={"role": "player"}) for name in ("d", "b", "a", "c")]
    plan = match(role("player"), size=2)
    restored = type(plan).from_dict(plan.to_dict())
    assert [[a.name for a in group] for group in restored.groups(agents)] == [["a", "b"], ["c", "d"]]


def test_dynamic_answer_bound_is_enforced(tmp_path):
    builder = Workflow("Bounds")
    sent_q = QuestionNumerical(question_name="sent", question_text="Sent", min_value=0, max_value=10)
    sent = builder.step("sent", Survey([sent_q]), assigned_to=role("sender"))
    returned_q = QuestionNumerical(question_name="returned", question_text="Return", min_value=0, max_value=30)
    builder.step("returned", Survey([returned_q]), assigned_to=role("receiver"), after=sent, answer_bounds={returned_q: (0, sent.answer("sent").value * 3)})
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "bounds.sqlite"); coordinator = WorkflowCoordinator(workflow, store)
    agents = [Agent(name="s", traits={"role": "sender"}), Agent(name="r", traits={"role": "receiver"})]
    instance = coordinator.launch(agents); first = store.items(instance, step_name="sent")[0]
    coordinator.open(first["id"]); coordinator.submit(first["id"], {"sent": 2}, idempotency_key="sent")
    second = store.items(instance, step_name="returned")[0]; coordinator.open(second["id"])
    with pytest.raises(ValueError, match="outside dynamic bounds"):
        coordinator.submit(second["id"], {"returned": 7}, idempotency_key="too-much")


def test_payoff_matrix_explicit_action_codes_resolve_label_collision(tmp_path):
    builder = Workflow("Chicken")
    action = QuestionMultipleChoice(
        question_name="action",
        question_text="Choose.",
        question_options=["Swerve", "Straight"],
    )
    choices = builder.step("choose", Survey([action]), assigned_to=role("player"))
    payoffs = builder.derive(
        "payoffs",
        values=choices.submissions.payoff_matrix(
            "action",
            {"WW": (2, 2), "WT": (1, 3), "TW": (3, 1), "TT": (0, 0)},
            action_codes={"Swerve": "W", "Straight": "T"},
        ),
    )
    report = QuestionFreeText(
        question_name="report", question_text=payoffs.field("values").template
    )
    builder.step("report", Survey([report]), assigned_to=role("settler"), after=choices)
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "matrix.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [
        Agent(name="a", traits={"role": "player"}),
        Agent(name="b", traits={"role": "player"}),
        Agent(name="s", traits={"role": "settler"}),
    ]

    class Answers:
        def answer(self, agent, opened):
            if opened.step_name == "choose":
                return {"action": "Swerve" if agent.name == "a" else "Straight"}
            return {"report": "recorded"}

    instance = coordinator.launch(agents)
    WorkflowSimulation(coordinator, {a.name: a for a in agents}, Answers()).run(instance)
    rendered = store.rendered_item(store.items(instance, step_name="report")[0]["id"])
    assert rendered["survey"]["questions"][0]["question_text"] == "{'a': 1, 'b': 3}"


def test_payoff_matrix_rejects_ambiguous_action_codes():
    builder = Workflow("Invalid matrix codes")
    question = QuestionMultipleChoice(
        question_name="action", question_text="Choose.", question_options=["A", "B"]
    )
    choices = builder.step("choose", Survey([question]), assigned_to=role("player"))
    with pytest.raises(ValueError, match="must be unique"):
        choices.submissions.payoff_matrix(
            "action", {"XX": (0, 0)}, action_codes={"A": "X", "B": "X"}
        )


def test_standard_artifact_and_collection_resources_execute(tmp_path):
    artifact = Artifact("typed-artifact", field_name="text")
    collection = Collection("typed-comments", field_name="comments")
    document = artifact.by("document").artifact
    comments = collection.by("document").collection
    draft = QuestionFreeText(question_name="draft", question_text="Draft.")
    comment = QuestionFreeText(
        question_name="comment",
        question_text="Comment on {{ shared_state.artifact.text }}",
    )
    builder = Workflow("Resources")
    submitted = builder.step(
        "submit",
        Survey([draft]),
        assigned_to=role("author"),
        writes=(document.submit(value=draft.answer),),
    )
    builder.step(
        "comment",
        Survey([comment]),
        assigned_to=role("reviewer"),
        after=submitted,
        reads=(document.read(),),
        writes=(comments.add(actor=current.agent.name, value=comment.answer),),
    )
    workflow = builder.compile()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow,
        store,
        state_backends={
            artifact.state_id: SQLiteStateBackend(
                artifact, tmp_path / "artifact.sqlite"
            ),
            collection.state_id: SQLiteStateBackend(
                collection, tmp_path / "collection.sqlite"
            ),
        },
    )
    assert coordinator.workflow.name == "Resources"


class FanoutAnswers:
    def answer(self, agent, opened):
        if opened.step_name == "suggest":
            return {"idea": f"Idea from {agent.name}"}
        text = opened.survey.questions[0].question_text
        assert "Idea from person-a" in text and "Idea from person-b" in text
        return {"choice": "Idea from person-a"}


def test_typed_outputs_render_all_fanout_submissions(tmp_path):
    builder = Workflow("Typed outputs")
    idea = QuestionFreeText(question_name="idea", question_text="Suggest.")
    suggestions = builder.step("suggest", Survey([idea]), assigned_to=role("person"))
    choice = QuestionFreeText(
        question_name="choice",
        question_text=f"Choose from {suggestions.outputs(idea).template}",
    )
    builder.step(
        "choose", Survey([choice]), assigned_to=role("chair"), after=suggestions
    )
    workflow = builder.compile()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [
        Agent(name="person-a", traits={"role": "person"}),
        Agent(name="person-b", traits={"role": "person"}),
        Agent(name="chair", traits={"role": "chair"}),
    ]
    instance_id = coordinator.launch(agents)

    WorkflowSimulation(
        coordinator, {agent.name: agent for agent in agents}, FanoutAnswers()
    ).run(instance_id)

    assert store.step_answers(instance_id, "choose") == [
        {"choice": "Idea from person-a"}
    ]


def test_identity_preserving_submissions_render_for_authorized_consumer(tmp_path):
    builder = Workflow("Identity-preserving submissions")
    report_question = QuestionFreeText(question_name="report", question_text="Report")
    reports = builder.step(
        "report",
        Survey([report_question]),
        assigned_to=role("respondent"),
        visible_to=role("scorer"),
    )
    score_question = QuestionFreeText(
        question_name="score",
        question_text=f"Score {reports.submissions.template}",
    )
    builder.step(
        "score",
        Survey([score_question]),
        assigned_to=role("scorer"),
        after=reports,
    )
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(builder.compile(), store)
    agents = [
        Agent(name="respondent-a", traits={"role": "respondent"}),
        Agent(name="respondent-b", traits={"role": "respondent"}),
        Agent(name="scorer", traits={"role": "scorer"}),
    ]
    instance_id = coordinator.launch(agents)
    for item in store.items(instance_id, step_name="report"):
        coordinator.open(item["id"])
        coordinator.submit(
            item["id"],
            {"report": item["participant_id"]},
            idempotency_key=f"submission:{item['id']}",
        )
    score_item = store.items(instance_id, step_name="score")[0]
    rendered = coordinator.open(score_item["id"]).survey.questions[0].question_text

    assert "participant_id" in rendered
    assert "respondent-a" in rendered
    assert "respondent-b" in rendered


class QuorumAnswers:
    def __init__(self):
        self.voters = []

    def answer(self, agent, opened):
        if opened.step_name == "vote":
            self.voters.append(agent.name)
            return {"label": "Remove" if len(self.voters) == 1 else "Warn"}
        assert "Remove" in opened.survey.questions[0].question_text
        assert "Warn" in opened.survey.questions[0].question_text
        return {"decision": "Remove"}


def test_quorum_supersedes_remaining_work_and_enables_disagreement_review(tmp_path):
    builder = Workflow("Moderation quorum")
    label = QuestionMultipleChoice(
        question_name="label",
        question_text="Choose a label.",
        question_options=["Allow", "Warn", "Remove"],
    )
    vote = builder.step(
        "vote",
        Survey([label]),
        assigned_to=role("moderator"),
        completion=quorum(2),
        visible_to=role("lead"),
    )
    decision = QuestionFreeText(
        question_name="decision",
        question_text=f"Resolve these votes: {vote.outputs(label).template}",
    )
    builder.step(
        "adjudicate",
        Survey([decision]),
        assigned_to=role("lead"),
        after=vote,
        when=vote.outputs(label).has_disagreement,
    )
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agents = [
        Agent(name=f"moderator-{index}", traits={"role": "moderator"})
        for index in range(3)
    ] + [Agent(name="lead", traits={"role": "lead"})]
    answerer = QuorumAnswers()
    instance_id = coordinator.launch(agents)

    WorkflowSimulation(
        coordinator, {agent.name: agent for agent in agents}, answerer
    ).run(instance_id)

    statuses = [item["status"] for item in store.items(instance_id, step_name="vote")]
    assert statuses.count("completed") == 2
    assert statuses.count("skipped") == 1
    assert len(answerer.voters) == 2
    assert store.step_answers(instance_id, "adjudicate") == [{"decision": "Remove"}]


def test_output_aggregate_predicates_are_serializable():
    builder = Workflow("Aggregates")
    question = QuestionFreeText(question_name="choice", question_text="Choose.")
    source = builder.step("source", Survey([question]), assigned_to=role("panel"))
    predicates = (
        source.outputs(question).count("A").at_least(2),
        source.outputs(question).has_disagreement,
        source.outputs(question).majority_is("A"),
        source.outputs(question).range_at_most(5),
    )
    for index, predicate in enumerate(predicates):
        builder.step(
            f"consumer-{index}",
            Survey([QuestionFreeText(question_name=f"q{index}", question_text="Go")]),
            assigned_to=role("lead"),
            after=source,
            when=predicate,
        )
    restored = HumanWorkflow.from_dict(builder.compile().to_dict())
    assert [step.enabled_when.to_dict() for step in restored.steps[1:]] == [
        predicate.to_dict() for predicate in predicates
    ]


def test_derived_statistics_round_trip_render_and_control_branching(tmp_path):
    builder = Workflow("Serializable statistics")
    estimate = QuestionNumerical(
        question_name="estimate",
        question_text="Estimate.",
        min_value=0,
        max_value=100,
        include_comment=False,
    )
    forecasts = builder.step("forecast", Survey([estimate]), assigned_to=role("expert"))
    stats = builder.derive(
        "forecast-stats",
        mean=forecasts.outputs(estimate).mean(),
        median=forecasts.outputs(estimate).median(),
        spread=forecasts.outputs(estimate).range(),
    )
    converged = stats.field("spread").at_most(20)
    report = QuestionFreeText(
        question_name="report",
        question_text=(
            f"Mean {stats.field('mean').template}; median "
            f"{stats.field('median').template}; spread "
            f"{stats.field('spread').template}."
        ),
    )
    builder.step(
        "report",
        Survey([report]),
        assigned_to=role("facilitator"),
        after=forecasts,
        when=converged,
    )
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    assert workflow.to_dict() == builder.compile().to_dict()

    class Answers:
        def answer(self, agent, opened):
            if opened.step_name == "forecast":
                return {
                    "estimate": {"expert-1": 10, "expert-2": 20, "expert-3": 30}[
                        agent.name
                    ]
                }
            text = opened.survey.questions[0].question_text
            assert "Mean 20.0; median 20.0; spread 20.0" in text
            return {"report": text}

    agents = [
        Agent(name=f"expert-{index}", traits={"role": "expert"})
        for index in range(1, 4)
    ] + [Agent(name="facilitator", traits={"role": "facilitator"})]
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    instance_id = coordinator.launch(agents)
    WorkflowSimulation(
        coordinator, {agent.name: agent for agent in agents}, Answers()
    ).run(instance_id)
    assert store.step_answers(instance_id, "report")


def test_derived_values_reject_raw_python():
    builder = Workflow("No executable callbacks")
    with pytest.raises(TypeError, match="serializable workflow expressions"):
        builder.derive("unsafe", result=lambda values: sum(values))


def test_derived_values_preserve_source_visibility():
    builder = Workflow("Private derived value")
    estimate = QuestionNumerical(
        question_name="estimate", question_text="Estimate.", min_value=0, max_value=100
    )
    source = builder.step(
        "private",
        Survey([estimate]),
        assigned_to=role("expert"),
        visible_to=role("facilitator"),
    )
    stats = builder.derive("private-stats", mean=source.outputs(estimate).mean())
    builder.step(
        "leak",
        Survey(
            [
                QuestionFreeText(
                    question_name="result",
                    question_text=f"Private mean: {stats.field('mean').template}",
                )
            ]
        ),
        assigned_to=role("analyst"),
        after=source,
    )
    with pytest.raises(ValueError, match="output visibility"):
        builder.compile()


def test_expression_deserialization_rejects_unknown_operator():
    with pytest.raises(ValueError, match="unsupported workflow expression operator"):
        WorkflowExpression.from_dict(
            {"type": "workflow_expression", "op": "run_python", "args": []}
        )


def test_repeat_block_round_trips_and_stops_future_iterations(tmp_path):
    builder = Workflow("Bounded repeat")

    def build_iteration(iteration):
        done = QuestionYesNo(
            question_name="done",
            question_text=f"Iteration {iteration.number}: are we done?",
        )
        step = iteration.step("round", Survey([done]), assigned_to=role("participant"))
        iteration.stop_when(step.answer(done).equals("Yes"))

    result = builder.repeat("rounds", max_iterations=3, build=build_iteration)
    compiled = builder.compile()
    encoded = json.loads(json.dumps(compiled.to_dict()))
    restored = HumanWorkflow.from_dict(encoded)
    assert restored.to_dict() == compiled.to_dict()
    assert result.block.iterations[1].step_names == ("round-2",)
    assert restored.repeat_blocks[0].max_iterations == 3

    class Answers:
        def answer(self, agent, opened):
            return {"done": "Yes" if opened.step_name == "round-2" else "No"}

    agent = Agent(name="person", traits={"role": "participant"})
    store = SQLiteWorkflowStore(tmp_path / "repeat.sqlite")
    coordinator = WorkflowCoordinator(restored, store)
    instance_id = coordinator.launch([agent])
    WorkflowSimulation(coordinator, {agent.name: agent}, Answers()).run(instance_id)
    assert [item["status"] for item in store.items(instance_id)] == [
        "completed",
        "completed",
        "skipped",
    ]
    skipped = [
        event
        for event in store.events(instance_id)
        if event["kind"] == "work_item.skipped"
    ]
    assert skipped[0]["reason"] == "repeat 'rounds' terminated before iteration 3"


def test_output_visibility_rejects_unauthorized_typed_reference():
    builder = Workflow("Private output")
    secret = QuestionFreeText(question_name="secret", question_text="Secret?")
    source = builder.step(
        "source",
        Survey([secret]),
        assigned_to=role("author"),
        visible_to=role("lead"),
    )
    builder.step(
        "consume",
        Survey(
            [
                QuestionFreeText(
                    question_name="use",
                    question_text=f"Use {source.answer(secret).template}",
                )
            ]
        ),
        assigned_to=role("analyst"),
        after=source,
    )
    with pytest.raises(ValueError, match="output visibility"):
        builder.compile()


def test_launch_rejects_impossible_quorum(tmp_path):
    builder = Workflow("Impossible")
    builder.step(
        "vote",
        Survey([QuestionFreeText(question_name="vote", question_text="Vote")]),
        assigned_to=role("voter"),
        completion=quorum(2),
    )
    coordinator = WorkflowCoordinator(
        builder.compile(), SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    )
    with pytest.raises(ValueError, match="requires quorum 2"):
        coordinator.launch([Agent(name="one", traits={"role": "voter"})])


def test_chance_condition_is_stable_serializable_and_can_end_rounds(tmp_path):
    builder = Workflow("Certain stop")
    first_question = QuestionFreeText(question_name="value", question_text="First")
    first = builder.step("first", Survey([first_question]), assigned_to=role("player"))
    builder.step(
        "second",
        Survey([QuestionFreeText(question_name="value", question_text="Second")]),
        assigned_to=role("player"),
        after=first,
        when=all_of(first.completed, chance(0, key="stop-after-first")),
    )
    workflow = HumanWorkflow.from_dict(builder.compile().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="player", traits={"role": "player"})
    instance_id = coordinator.launch([agent])
    first_item = store.items(instance_id, step_name="first")[0]
    coordinator.open(first_item["id"])
    coordinator.submit(
        first_item["id"], {"value": "done"}, idempotency_key="first-response"
    )

    assert store.items(instance_id, step_name="second")[0]["status"] == "skipped"
    condition = workflow.steps[1].enabled_when.conditions[1]
    assert condition.to_dict() == {
        "type": "chance",
        "probability": 0,
        "key": "stop-after-first",
    }
