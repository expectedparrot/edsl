import json
import subprocess
import sys

import pytest

from edsl import Agent, Model, QuestionFreeText, Survey
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.surveys.exceptions import SurveyError


def make_survey():
    return Survey(
        [
            QuestionFreeText(question_name=name, question_text=f"{name}?")
            for name in ("intro", "q1", "q2", "q3", "q4", "end")
        ]
    )


def test_question_sampling_policy_round_trips_json_jsonl_and_ep(tmp_path):
    survey = make_survey().sample_questions(
        ["q1", "q2", "q3", "q4"], sample_size=2, required_questions=["q1"]
    )
    expected = {
        "version": 1,
        "eligible_questions": ["q1", "q2", "q3", "q4"],
        "sample_size": 2,
        "required_questions": ["q1"],
        "method": "uniform_without_replacement",
    }

    assert survey.question_sampling == expected
    assert Survey.from_dict(survey.to_dict()).question_sampling == expected
    assert Survey.from_jsonl(survey.to_jsonl()).question_sampling == expected
    package_path = tmp_path / "sampling.ep"
    survey.git.save(package_path)
    assert Survey.git.load(package_path).question_sampling == expected


def test_sampling_validates_exact_count_and_required_boundaries():
    eligible = ["q1", "q2", "q3"]
    for sample_size in (0, -1, 4, True, 1.5):
        with pytest.raises(SurveyError):
            make_survey().sample_questions(eligible, sample_size)
    with pytest.raises(SurveyError, match="required"):
        make_survey().sample_questions(eligible, 1, required_questions=["q1", "q2"])
    with pytest.raises(SurveyError, match="unknown"):
        make_survey().sample_questions(["missing", "q1"], 1)
    with pytest.raises(SurveyError, match="duplicate"):
        make_survey().sample_questions(["q1", "q1"], 1)
    assert (
        make_survey()
        .sample_questions(eligible, 1, required_questions=["q1"])
        .question_sampling["sample_size"]
        == 1
    )
    assert make_survey().sample_questions(eligible, len(eligible)).question_sampling[
        "sample_size"
    ] == len(eligible)


def test_sampling_rejects_dependencies_that_cannot_be_guaranteed():
    survey = Survey(
        [
            QuestionFreeText(question_name="prerequisite", question_text="Prior?"),
            QuestionFreeText(
                question_name="dependent",
                question_text="You said {{ prerequisite.answer }}. Follow-up?",
            ),
            QuestionFreeText(question_name="other", question_text="Other?"),
        ]
    )
    with pytest.raises(SurveyError, match="prerequisite"):
        survey.sample_questions(["prerequisite", "dependent", "other"], 2)

    # A required prerequisite makes the dependent question safe to include.
    configured = survey.sample_questions(
        ["prerequisite", "dependent", "other"],
        2,
        required_questions=["prerequisite"],
    )
    assert configured.question_sampling["required_questions"] == ["prerequisite"]


def test_survey_subset_and_rename_preserve_or_reject_sampling_policy():
    survey = make_survey().sample_questions(["q1", "q2", "q3"], sample_size=2)
    with pytest.raises(SurveyError, match="part of the question-sampling pool"):
        survey.subset("intro", "q1", "q2")
    retained = survey.subset("intro", "q1", "q2", "q3", "end")
    assert retained.question_sampling == survey.question_sampling
    renamed = survey.rename({"q2": "renamed_q2"})
    assert "renamed_q2" in renamed.question_sampling["eligible_questions"]


def test_realized_selection_is_exact_shared_across_models_and_queryable(tmp_path):
    survey = make_survey().sample_questions(
        ["q1", "q2", "q3", "q4"], sample_size=2, required_questions=["q1"]
    )
    job = survey.by(Agent()).by(
        [Model("test", temperature=0.1), Model("test", temperature=0.9)]
    )
    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="question-sampling")
    job_definition = service.jobs.get_definition(job_id)
    definitions = service.interviews.get_definitions_batch(
        job_id, job_definition.interview_ids
    )

    assert (
        len(
            {tuple(definition.sampled_questions) for definition in definitions.values()}
        )
        == 1
    )
    sampled = next(iter(definitions.values())).sampled_questions
    assert len(sampled) == 2
    assert "q1" in sampled
    for definition in definitions.values():
        assert set(definition.sampled_questions).isdisjoint(
            definition.unselected_questions
        )
        assert set(definition.sampled_questions) | set(
            definition.unselected_questions
        ) == {
            "q1",
            "q2",
            "q3",
            "q4",
        }
        restored = type(definition).from_dict(
            definition.interview_id, job_id, definition.to_dict()
        )
        assert restored.sampled_questions == definition.sampled_questions
        assert restored.unselected_questions == definition.unselected_questions
        assert restored.question_sampling_seed == definition.question_sampling_seed

        for task_id in definition.task_ids:
            service.on_task_completed(
                job_id, definition.interview_id, task_id, "answer"
            )

    results = service.build_edsl_results(job_id)
    assert len(results) == 2
    assert len({result["randomization"]["assignment_id"] for result in results}) == 1
    for result in results:
        provenance = result["randomization"]
        assert len(provenance["sampled_questions"]) == 2
        assert (
            provenance["unselected_questions"]
            == next(iter(definitions.values())).unselected_questions
        )
        assert set(provenance["not_presented_questions"]) == set(
            provenance["unselected_questions"]
        )
        assert all(
            provenance["exposure_events"][name]["presented"] is False
            for name in provenance["unselected_questions"]
        )
        assert all(
            result.answer[name] is None for name in provenance["unselected_questions"]
        )

    restored = type(results).from_dict(results.to_dict())
    assert [r["randomization"] for r in restored] == [
        r["randomization"] for r in results
    ]
    package_path = tmp_path / "sampled-results.ep"
    results.git.save(package_path)
    package_restored = type(results).git.load(package_path)
    assert [r["randomization"] for r in package_restored] == [
        r["randomization"] for r in results
    ]

    columns = subprocess.run(
        [
            sys.executable,
            "-m",
            "edsl",
            "results",
            "columns",
            "--file",
            str(package_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    column_data = json.loads(columns.stdout)
    assert column_data["status"] == "ok"
    assert "randomization.unselected_questions" in column_data["data"]["columns"]
    selected = subprocess.run(
        [
            sys.executable,
            "-m",
            "edsl",
            "results",
            "select",
            "--file",
            str(package_path),
            "--column",
            "randomization.sampled_questions",
            "--column",
            "randomization.unselected_questions",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    selected_data = json.loads(selected.stdout)
    assert selected_data["status"] == "ok"
    assert len(selected_data["data"]["data"]) == 2

    csv_path = tmp_path / "sample-omissions.csv"
    exported = subprocess.run(
        [
            sys.executable,
            "-m",
            "edsl",
            "results",
            "export",
            str(package_path),
            "--column",
            "randomization.unselected_questions",
            "--output",
            str(csv_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(exported.stdout)["status"] == "ok"
    assert csv_path.exists()
