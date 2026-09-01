import pytest

from edsl import Agent, QuestionFreeText, QuestionMultipleChoice, QuestionYesNo, Survey
from edsl.sharedstate import SQLiteStateBackend, current
from edsl.workflows import (
    Artifact,
    Collection,
    HumanWorkflow,
    SQLiteWorkflowStore,
    Workflow,
    WorkflowCoordinator,
    WorkflowSimulation,
    all_of,
    any_of,
    not_,
    quorum,
    role,
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
