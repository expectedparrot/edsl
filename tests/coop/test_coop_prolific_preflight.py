"""Publication guards use current deployed content and never spend on failure."""

from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from edsl import Coop, QuestionFreeText, Survey
from edsl.__main__ import app
from edsl.coop.exceptions import CoopValueError


@pytest.fixture
def coop():
    client = object.__new__(Coop)
    survey = Survey([QuestionFreeText(question_name="prolific_id", question_text="Your participant ID?")])
    client.get_prolific_study = Mock(return_value={
        "study_id": "study", "status": "UNPUBLISHED", "num_participants": 10,
        "participant_payment_cents": 200, "estimated_completion_time_minutes": 10,
        "key_source": "ep",
    })
    client.get_human_survey = Mock(return_value={"survey_uuid": "deployed-survey"})
    client.get = Mock(return_value=survey)
    client.calculate_prolific_study_cost = Mock(return_value={"cost_credits": 3000, "is_underpayment": False})
    client.get_balance = Mock(return_value={"credits": 5000})
    client._send_server_request = Mock(return_value=Mock(json=lambda: {"status": "ACTIVE"}))
    client._resolve_server_response = Mock()
    return client


def test_preflight_reads_deployed_content_without_publishing(coop):
    check = coop.preflight_prolific_study("human", "study", required_questions=["prolific_id"],
                                         expected_survey=coop.get.return_value, required_credits=4000)
    assert check["ready"]
    assert check["cost_scope"] == "caller_supplied_total"
    coop.get.assert_called_once_with("deployed-survey", expected_object_type="survey")
    coop._send_server_request.assert_not_called()


@pytest.mark.parametrize("problem", ["missing_id", "changed_wording", "low_balance", "underquote", "underpayment", "active", "no_survey", "bad_balance"])
def test_failed_publication_never_sends_publish(coop, problem):
    expected = Survey.from_dict(coop.get.return_value.to_dict())
    if problem == "missing_id":
        coop.get.return_value = Survey([])
    elif problem == "changed_wording":
        coop.get.return_value.questions[0].question_text = "Different wording"
    elif problem == "low_balance":
        coop.get_balance.return_value = {"credits": 2999}
    elif problem == "underquote":
        coop.calculate_prolific_study_cost.return_value["cost_credits"] = 4001
    elif problem == "underpayment":
        coop.calculate_prolific_study_cost.return_value["is_underpayment"] = True
    elif problem == "active":
        coop.get_prolific_study.return_value["status"] = "ACTIVE"
    elif problem == "no_survey":
        coop.get_human_survey.return_value = {}
    else:
        coop.get_balance.return_value = {"credits": float("nan")}
    with pytest.raises(CoopValueError):
        coop.publish_prolific_study("human", "study", expected_survey=expected,
                                   required_questions=["prolific_id"], required_credits=4000)
    coop._send_server_request.assert_not_called()


def test_own_key_study_is_not_charged_for_recruitment(coop):
    coop.get_prolific_study.return_value["key_source"] = "user_key"
    coop.get_balance.return_value = {"credits": 0}
    check = coop.preflight_prolific_study("human", "study")
    assert check["ready"], check["blockers"]
    assert check["recruitment_credits"] == 0
    assert check["key_source"] == "user_key"

    # AI work is still paid in credits on an own-key study.
    check = coop.preflight_prolific_study("human", "study", required_credits=10)
    assert not check["ready"]
    assert any("Insufficient credits" in blocker for blocker in check["blockers"])


def test_study_without_a_reported_key_is_costed_as_expected_parrots(coop):
    del coop.get_prolific_study.return_value["key_source"]
    coop.get_balance.return_value = {"credits": 2999}
    check = coop.preflight_prolific_study("human", "study")
    assert check["key_source"] == "ep" and check["recruitment_credits"] == 3000
    assert not check["ready"]


def test_publish_rechecks_after_successful_preflight(coop):
    assert coop.preflight_prolific_study("human", "study")["ready"]
    coop.get_balance.return_value = {"credits": 0}
    with pytest.raises(CoopValueError, match="Insufficient credits"):
        coop.publish_prolific_study("human", "study")
    assert coop.get_balance.call_count == 2
    coop._send_server_request.assert_not_called()


def test_valid_publication_sends_one_post(coop):
    assert coop.publish_prolific_study("human", "study") == {"status": "ACTIVE"}
    coop._send_server_request.assert_called_once_with(
        uri="api/v0/human-surveys/human/prolific-studies/study/status",
        method="POST", payload={"action": "PUBLISH"},
    )


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1, True, "4000"])
def test_invalid_required_credits_fail_closed(coop, amount):
    with pytest.raises(CoopValueError):
        coop.publish_prolific_study("human", "study", required_credits=amount)
    coop._send_server_request.assert_not_called()


def test_cli_preflight_and_publish_preserve_question_contract(coop, monkeypatch, tmp_path):
    import edsl.coop

    monkeypatch.setattr(edsl.coop, "Coop", lambda: coop)
    path = tmp_path / "survey.ep"
    coop.get.return_value.git.save(str(path))
    flags = ["--survey", str(path), "--require-question", "prolific_id", "--required-credits", "4000"]
    runner = CliRunner()
    good = runner.invoke(app, ["humanize", "prolific", "preflight", "human", "study", *flags])
    assert good.exit_code == 0, good.output
    coop.get.return_value = Survey([])
    blocked = runner.invoke(app, ["humanize", "prolific", "preflight", "human", "study", *flags])
    assert blocked.exit_code != 0
    assert "prolific_id" in blocked.output
    published = runner.invoke(app, ["humanize", "prolific", "publish", "human", "study", *flags])
    assert published.exit_code != 0
    coop._send_server_request.assert_not_called()
