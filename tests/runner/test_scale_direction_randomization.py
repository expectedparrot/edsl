import random
import json

import pytest
from click.testing import CliRunner

from edsl import Model, ModelList, QuestionLinearScale, QuestionMultipleChoice, Survey
from edsl.__main__ import app
from edsl.jobs.exceptions import JobsRunError
from edsl.runner.models import InterviewDefinition
from edsl.surveys.exceptions import SurveyError


def test_scale_direction_policy_round_trips_with_survey():
    question = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it.",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Low", 5: "High"},
    )
    survey = Survey([question]).randomize_scale_direction("rating")

    restored = Survey.from_dict(survey.to_dict())
    jsonl_restored = Survey.from_jsonl(survey.to_jsonl())

    assert restored.scale_direction_randomization == {
        "version": 1,
        "questions": ["rating"],
        "method": "uniform_forward_reverse",
        "assignment_unit": "agent_scenario_iteration",
        "balance": "none",
    }
    assert (
        jsonl_restored.scale_direction_randomization
        == restored.scale_direction_randomization
    )
    restored.clear_scale_direction_randomization()
    assert restored.scale_direction_randomization is None


@pytest.mark.parametrize("bad_name", ["missing"])
def test_scale_direction_rejects_unknown_question(bad_name):
    survey = Survey(
        [
            QuestionLinearScale(
                question_name="rating",
                question_text="Rate it.",
                question_options=[1, 2],
            )
        ]
    )
    with pytest.raises(SurveyError, match="unknown questions"):
        survey.randomize_scale_direction(bad_name)


def test_scale_direction_rejects_non_scales_duplicate_targets_and_conflicts():
    choice = QuestionMultipleChoice(
        question_name="choice",
        question_text="Pick one.",
        question_options=["A", "B"],
    )
    with pytest.raises(SurveyError, match="only supports QuestionLinearScale"):
        Survey([choice]).randomize_scale_direction("choice")

    scale = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it.",
        question_options=[1, 2, 3],
    )
    with pytest.raises(SurveyError, match="cannot contain duplicates"):
        Survey([scale]).randomize_scale_direction("rating", "rating")
    with pytest.raises(SurveyError, match="ordinary option shuffling"):
        Survey([scale], questions_to_randomize=["rating"]).randomize_scale_direction(
            "rating"
        )


def test_scale_direction_policy_tracks_survey_edits():
    rating = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it.",
        question_options=[1, 2, 3],
    )
    other = QuestionLinearScale(
        question_name="other",
        question_text="Rate something else.",
        question_options=[1, 2, 3],
    )
    survey = Survey([rating, other]).randomize_scale_direction("rating")

    moved = survey.move_question("rating", 1)
    assert moved.scale_direction_randomization["questions"] == ["rating"]
    assert moved.subset("rating").scale_direction_randomization["questions"] == [
        "rating"
    ]
    assert moved.drop("rating").scale_direction_randomization is None
    assert moved.delete_question("rating").scale_direction_randomization is None


def test_scale_direction_local_inference_records_order_and_preserves_values(
    monkeypatch,
):
    # Seed zero deterministically selects reverse; all calls stay on local test inference.
    monkeypatch.setattr(random, "getrandbits", lambda bits: 0)
    prompts = []

    def answer_with_low_value(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return "1"

    question = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it.",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Low", 5: "High"},
    )
    survey = Survey([question]).randomize_scale_direction("rating")
    result = survey.by(Model("test", func=answer_with_low_value)).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )

    assert len(prompts) == 1
    assert prompts[0].index("High") < prompts[0].index("Low")
    assert result.select("question_options.rating").to_list() == [[5, 4, 3, 2, 1]]
    assert result.select("randomization.option_orders").to_list() == [
        {"rating": [5, 4, 3, 2, 1]}
    ]
    # Numeric scale codes remain the declared values when the presentation reverses.
    assert result.select("answer.rating").to_list() == [1]
    assert result.select("randomization.scale_directions").to_list() == [
        {"rating": "reverse"}
    ]
    assert result.select("randomization.scale_direction_seeds").to_list() == [
        {"rating": 0}
    ]
    assert question.option_labels == {1: "Low", 5: "High"}


def test_direction_assignment_is_shared_across_model_variants(monkeypatch):
    monkeypatch.setattr(random, "getrandbits", lambda bits: 1)
    question = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it.",
        question_options=[1, 2, 3, 4, 5],
    )
    survey = Survey([question]).randomize_scale_direction("rating")

    def response(user_prompt, system_prompt, files_list):
        return "1"

    models = ModelList([Model("test", func=response), Model("test", func=response)])

    results = survey.by(models).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exception=True,
    )

    assert results.select("randomization.scale_directions").to_list() == [
        {"rating": "forward"},
        {"rating": "forward"},
    ]
    assert results.select("randomization.scale_direction_seeds").to_list() == [
        {"rating": 1},
        {"rating": 1},
    ]
    assert results.select("randomization.option_orders").to_list() == [
        {"rating": [1, 2, 3, 4, 5]},
        {"rating": [1, 2, 3, 4, 5]},
    ]
    assignment_ids = results.select(
        "randomization.scale_direction_assignment_id"
    ).to_list()
    assert assignment_ids[0] == assignment_ids[1]


def test_full_remote_offload_rejects_unsupported_scale_policy_before_launch():
    survey = Survey(
        [
            QuestionLinearScale(
                question_name="rating",
                question_text="Rate it.",
                question_options=[1, 2, 3],
            )
        ]
    ).randomize_scale_direction("rating")

    with pytest.raises(JobsRunError, match="not supported by full remote job offload"):
        survey.by(Model("test")).run(offload_execution=True)


def test_interview_definition_persists_scale_assignment():
    definition = InterviewDefinition(
        interview_id="interview",
        job_id="job",
        scenario_id="scenario",
        agent_id="agent",
        model_id="model",
        total_tasks=0,
        task_ids=[],
        scale_directions={"rating": "reverse"},
        scale_direction_seeds={"rating": 42},
        scale_direction_assignment_id="assignment",
    )

    restored = InterviewDefinition.from_dict("interview", "job", definition.to_dict())

    assert restored.scale_directions == {"rating": "reverse"}
    assert restored.scale_direction_seeds == {"rating": 42}
    assert restored.scale_direction_assignment_id == "assignment"


def test_cli_sets_and_clears_scale_direction_policy(tmp_path):
    survey = Survey(
        [
            QuestionLinearScale(
                question_name="rating",
                question_text="Rate it.",
                question_options=[1, 2, 3],
            )
        ]
    )
    survey_path = tmp_path / "survey.json"
    survey_path.write_text(json.dumps(survey.to_dict()))
    runner = CliRunner()

    configured = runner.invoke(
        app,
        [
            "surveys",
            "set-scale-direction-randomization",
            str(survey_path),
            "--question",
            "rating",
        ],
    )

    assert configured.exit_code == 0, configured.output
    assert Survey.from_dict(
        json.loads(survey_path.read_text())
    ).scale_direction_randomization

    validated = runner.invoke(app, ["validate", "--file", str(survey_path)])
    assert validated.exit_code == 0, validated.output

    cleared = runner.invoke(
        app,
        [
            "surveys",
            "set-scale-direction-randomization",
            str(survey_path),
            "--clear",
        ],
    )

    assert cleared.exit_code == 0, cleared.output
    assert (
        Survey.from_dict(
            json.loads(survey_path.read_text())
        ).scale_direction_randomization
        is None
    )
