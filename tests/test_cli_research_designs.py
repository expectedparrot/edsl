import json
import shlex
from collections import Counter

from click.testing import CliRunner

from edsl import AgentList, Model, QuestionMultipleChoice, Results, Scenario, Survey
from edsl.__main__ import app


def invoke(*args, code=0):
    res = CliRunner().invoke(app, list(map(str, args)))
    assert res.exit_code == code, res.output
    return json.loads(res.stdout)


def test_generate_panel_from_exact_counts_and_reread_source(tmp_path):
    source = tmp_path / "margins.csv"
    dest = tmp_path / "agents.ep"
    source.write_text(
        "field,category,count\nage,Older,6\nage,Younger,4\nmode,001,7\nmode,002,3\n"
    )
    command = (
        "agents",
        "from-margins",
        source,
        "--seed",
        "41",
        "--id-field",
        "person",
        "-o",
        dest,
    )
    summary = invoke(*command)["data"]
    assert summary["agent_count"] == 10
    assert invoke(*shlex.split(summary["tally_command"])[1:])["data"]["agent_count"] == 10
    agents = AgentList.git.load(dest, sync_coop=False)
    assert len({a.traits["person"] for a in agents}) == 10
    assert Counter(a.traits["mode"] for a in agents) == {"001": 7, "002": 3}
    assert Counter(a.traits["age"] for a in agents) == {"Older": 6, "Younger": 4}
    assert agents == AgentList.from_margins(
        {"age": {"Older": 6, "Younger": 4}, "mode": {"001": 7, "002": 3}},
        seed=41,
        id_field="person",
    )
    tally = invoke("agents", "tally", dest, "--trait", "age", "--trait", "mode")["data"]
    assert tally["agent_count"] == 10
    assert {
        (g["values"]["age"], g["values"]["mode"]): g["count"] for g in tally["groups"]
    } == Counter((a.traits["age"], a.traits["mode"]) for a in agents)
    assert (
        invoke("agents", "tally", dest, "--trait", "missing", code=5)["error"]["code"]
        == "AGENTS_TALLY_ERROR"
    )
    existing = dest.read_bytes()
    source.write_text(source.read_text().replace("Younger,4", "Younger,2"))
    assert "total" in invoke(*command, code=5)["error"]["message"]
    source.write_text("field,category,count\nage,Older,1\nage,Older,2\n")
    assert "Duplicate" in invoke(*command, code=5)["error"]["message"]
    assert dest.read_bytes() == existing


def test_distinct_scripted_rows_roundtrip_and_bad_inputs_are_atomic(tmp_path):
    q = QuestionMultipleChoice(
        question_name="choose",
        question_text="Which in {{city}}?",
        question_options=["A", "B"],
    )
    job = (
        Survey([q]).by(Scenario(city="here"), Scenario(city="there")).by(Model("test"))
    )
    path = tmp_path / "design.ep"
    job.git.save(path, sync_coop=False)
    rows = tmp_path / "replies.json"
    rows.write_text('[{"choose":"A"},{"choose":"B"}]')
    output = tmp_path / "pilot.ep"
    cmd = ("jobs", "test-case", path, "--all", "--response-rows", rows, "-o", output)
    assert invoke(*cmd)["data"]["tested_interviews"] == 2
    loaded = Results.git.load(output, sync_coop=False)
    assert [(r.scenario["city"], r.answer["choose"]) for r in loaded] == [
        ("here", "A"),
        ("there", "B"),
    ]
    rows.write_text('[{"choose":"ZZZ"},{"choose":"YYY"}]')
    rejected = invoke(*cmd[:-2], "--expect-rejection", "choose")
    assert (
        rejected["data"]["tested_interviews"] == 2
        and rejected["data"]["validation_rejected"]
    )
    saved = output.read_bytes()
    for invalid in ("[]", '[{"choose":"A"},null]', '[{},{"typo":"A"}]'):
        rows.write_text(invalid)
        assert invoke(*cmd, code=2)["status"] == "error"
        assert output.read_bytes() == saved


def test_imported_staff_notes_raise_render_warning(tmp_path):
    q = QuestionMultipleChoice(
        question_name="transport",
        question_text="How did you travel?",
        question_options=["Bus", "Walk"],
        question_presentation="Read the card.",
    )
    s = Survey([q])
    survey_file = tmp_path / "survey.ep"
    s.git.save(survey_file, sync_coop=False)
    assert "check-wording" in invoke("surveys", "questions", survey_file)["warnings"][0]
    data = invoke("surveys", "preview-prompt", survey_file, "transport")
    assert "Read the card." in data["data"]["user_prompt"]
    assert any(
        "omits the authored question text" in warning for warning in data["warnings"]
    )
    jobs_file = tmp_path / "jobs.ep"
    s.by(Model("test")).git.save(jobs_file, sync_coop=False)
    assert (
        invoke("jobs", "preview-prompt", jobs_file, "transport")["warnings"]
        == data["warnings"]
    )


def test_check_wording_collects_violations_and_exercises_prior_answers(tmp_path):
    from edsl import QuestionFreeText

    survey = Survey(
        [
            QuestionFreeText(
                question_name="before",
                question_text="Where?",
                question_presentation="INTERVIEWER ONLY",
            ),
            QuestionFreeText(
                question_name="after",
                question_text="Why {{ before.answer }} in {{ place }}?",
            ),
        ]
    )
    path = tmp_path / "wording.ep"
    survey.git.save(path, sync_coop=False)
    cmd = ("surveys", "check-wording", path)
    assert invoke(*cmd, code=2)["error"]["code"] == "USAGE_ERROR"
    inputs = ("--answers", '{"before":"walk"}', "--scenario", '{"place":"Boston"}')
    expected = ("--expected", '{"before":"Where?","after":"Why walk in Boston?"}')
    failures = invoke(
        *cmd, *inputs, *expected, "--forbid-text", "INTERVIEWER ONLY", code=5
    )["error"]["details"]
    assert len(failures) == 1
    failed = failures[0]
    assert failed["question"] == "before" and failed["missing_wording"] == "Where?"
    assert failed["forbidden_text_found"] == ["INTERVIEWER ONLY"]
    invoke(*shlex.split(failed["restore_default_presentation"])[1:])
    assert invoke(*cmd, *inputs, *expected, "--forbid-text", "INTERVIEWER ONLY")[
        "data"
    ]["checked_questions"] == ["before", "after"]
    bad_order = ("--expected", '{"before":"Where?","after":["Boston?","Why walk"]}')
    assert (
        invoke(*cmd, *inputs, *bad_order, code=5)["error"]["details"][0]["question"]
        == "after"
    )
