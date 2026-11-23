import pytest

from edsl import Agent, Model, QuestionFreeText, QuestionMultipleChoice, Survey
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.instructions import Instruction
from edsl.surveys.exceptions import SurveyError


def make_survey():
    return Survey(
        [
            QuestionFreeText(question_name="intro", question_text="Intro?"),
            QuestionFreeText(question_name="trust", question_text="Trust?"),
            QuestionFreeText(question_name="fairness", question_text="Fair?"),
            QuestionFreeText(question_name="satisfaction", question_text="Satisfied?"),
            QuestionFreeText(question_name="age", question_text="Age?"),
        ]
    )


def test_named_order_blocks_validate_and_round_trip_json_jsonl_and_ep(tmp_path):
    survey = make_survey().randomize_question_order(
        "attitudes", ["trust", "fairness", "satisfaction"]
    )

    assert survey.question_order == {
        "version": 1,
        "blocks": [
            {
                "name": "attitudes",
                "questions": ["trust", "fairness", "satisfaction"],
                "method": "permute",
            }
        ],
        "memory": {"mode": "preserve"},
    }
    assert Survey.from_dict(survey.to_dict()).question_order == survey.question_order
    assert Survey.from_jsonl(survey.to_jsonl()).question_order == survey.question_order
    package_path = tmp_path / "survey.ep"
    survey.git.save(package_path)
    assert Survey.git.load(package_path).question_order == survey.question_order


def test_order_blocks_must_be_disjoint_and_contiguous():
    survey = make_survey().randomize_question_order("one", ["trust", "fairness"])
    with pytest.raises(SurveyError, match="disjoint"):
        survey.randomize_question_order("two", ["fairness", "satisfaction"])
    with pytest.raises(SurveyError, match="contiguous"):
        make_survey().randomize_question_order("split", ["intro", "fairness"])


def test_subsets_preserve_whole_blocks_and_reject_partial_blocks():
    survey = make_survey().randomize_question_order(
        "attitudes", ["trust", "fairness", "satisfaction"]
    )
    with pytest.raises(SurveyError, match="only part"):
        survey.subset("trust", "fairness")
    assert survey.subset("trust", "fairness", "satisfaction").question_order == (
        survey.question_order
    )
    assert survey.subset("intro", "age").question_order["blocks"] == []


def test_rename_updates_order_block_references():
    survey = make_survey().randomize_question_order(
        "attitudes", ["trust", "fairness", "satisfaction"]
    )
    renamed = survey.rename({"fairness": "equity"})
    assert renamed.question_order["blocks"][0]["questions"] == [
        "trust",
        "equity",
        "satisfaction",
    ]


def test_question_order_does_not_change_answer_option_randomization():
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name=name,
                question_text=f"{name}?",
                question_options=["yes", "no"],
            )
            for name in ("q1", "q2")
        ],
        questions_to_randomize=["q1"],
    ).randomize_question_order("block", ["q1", "q2"])

    assert survey.questions_to_randomize == ["q1"]


def test_order_blocks_reject_internal_piping_dependencies_and_instructions():
    dependent = Survey(
        [
            QuestionFreeText(question_name="trust", question_text="Trust?"),
            QuestionFreeText(
                question_name="fairness",
                question_text="You said {{ trust.answer }}. Fair?",
            ),
        ]
    )
    with pytest.raises(SurveyError, match="depends on"):
        dependent.randomize_question_order("attitudes", ["trust", "fairness"])

    with_instruction = Survey(
        [
            QuestionFreeText(question_name="trust", question_text="Trust?"),
            Instruction(name="boundary", text="Pause."),
            QuestionFreeText(question_name="fairness", question_text="Fair?"),
        ]
    )
    with pytest.raises(SurveyError, match="contiguous"):
        with_instruction.randomize_question_order("attitudes", ["trust", "fairness"])

    memory_dependent = Survey(
        [
            QuestionFreeText(question_name="trust", question_text="Trust?"),
            QuestionFreeText(question_name="fairness", question_text="Fair?"),
        ]
    ).add_targeted_memory("fairness", "trust")
    with pytest.raises(SurveyError, match="depends on"):
        memory_dependent.randomize_question_order("attitudes", ["trust", "fairness"])

    branched = make_survey().add_skip_rule("fairness", "{{ trust.answer }} == 'skip'")
    with pytest.raises(SurveyError, match="custom skip"):
        branched.randomize_question_order(
            "attitudes", ["trust", "fairness", "satisfaction"]
        )


def test_multiple_blocks_keep_their_fixed_positions_and_have_independent_seeds():
    survey = Survey(
        [
            QuestionFreeText(question_name=name, question_text=f"{name}?")
            for name in ("fixed_start", "a1", "a2", "middle", "b1", "b2", "fixed_end")
        ]
    )
    survey.randomize_question_order("first", ["a1", "a2"])
    survey.randomize_question_order("second", ["b1", "b2"])
    service = JobService(InMemoryStorage())
    order, seeds = service._realize_question_order(
        survey, survey.questions, {}, (0, 0, 0)
    )

    assert order[0] == "fixed_start"
    assert set(order[1:3]) == {"a1", "a2"}
    assert order[3] == "middle"
    assert set(order[4:6]) == {"b1", "b2"}
    assert order[6] == "fixed_end"
    assert seeds.keys() == {"first", "second"}
    assert len(set(seeds.values())) == 2


def test_realized_order_is_persisted_and_shared_across_models():
    survey = make_survey().randomize_question_order(
        "attitudes", ["trust", "fairness", "satisfaction"]
    )
    job = survey.by(Agent()).by(
        [Model("test", temperature=0.1), Model("test", temperature=0.9)]
    )
    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="question-order")
    definitions = service.interviews.get_definitions_batch(
        job_id, service.jobs.get_definition(job_id).interview_ids
    )

    orders = {tuple(definition.question_order) for definition in definitions.values()}
    assert len(orders) == 1
    assignment_ids = {
        definition.randomization_assignment_id for definition in definitions.values()
    }
    assert len(assignment_ids) == 1
    order = next(iter(orders))
    assert order[0] == "intro"
    assert set(order[1:4]) == {"trust", "fairness", "satisfaction"}
    assert order[4] == "age"
    assert all(
        definition.question_order_seeds.keys() == {"attitudes"}
        for definition in definitions.values()
    )

    serialized = next(iter(definitions.values())).to_dict()
    restored = type(next(iter(definitions.values()))).from_dict(
        next(iter(definitions.values())).interview_id, job_id, serialized
    )
    assert restored.question_order == list(order)
    assert (
        restored.question_order_seeds
        == next(iter(definitions.values())).question_order_seeds
    )

    for interview_id, definition in definitions.items():
        task_definitions = service.tasks.get_definitions_batch(
            job_id, interview_id, definition.task_ids
        )
        task_by_question = {
            task.question_name: task for task in task_definitions.values()
        }
        for previous, current in zip(
            definition.question_order, definition.question_order[1:]
        ):
            assert (
                task_by_question[previous].task_id
                in task_by_question[current].depends_on
            )
        for question_name in definition.question_order:
            task = task_by_question[question_name]
            service.on_task_completed(job_id, interview_id, task.task_id, "answer")

    results = service.build_edsl_results(job_id)
    assert len(results) == 2
    assert len({result["randomization"]["assignment_id"] for result in results}) == 1
    assert all(
        result["randomization"]["planned_question_order"] == list(order)
        for result in results
    )
