"""Exercise named placement, per-item inference and prompt inspection on disk."""

import json
from click.testing import CliRunner
import pytest

from edsl import Instruction, QuestionMultipleChoice, Survey
from edsl.__main__ import app


def invoke(*args, ok=True):
    proc = CliRunner().invoke(app, ["surveys", *map(str, args)])
    assert (proc.exit_code == 0) == ok, proc.output
    envelope = json.loads(proc.output)
    assert envelope["status"] == ("ok" if ok else "error")
    return envelope.get("data", envelope.get("error"))


def choice(name, text):
    return QuestionMultipleChoice(
        question_name=name, question_text=text, question_options=["A", "B"]
    )


def test_insert_into_existing_group(tmp_path):
    path = tmp_path / "survey.ep"
    s = Survey(
        [
            choice("mode", "Mode?"),
            Instruction("units", "Report dollars."),
            choice("fare", "Fare?"),
            choice("tip", "Tip?"),
        ]
    )
    s.add_question_group("mode", "mode", "travel")
    s.add_question_group("fare", "tip", "cost")
    s.set_full_memory_mode()
    s.add_stop_rule("tip", "{{ tip.answer }} == 'A'")
    head = s.git.save(path)["commit"]
    args = [
        "add-instruction",
        path,
        "--name",
        "direction",
        "--text",
        "Use the most recent trip.",
        "--before",
        "fare",
    ]
    invoke(*args)
    assert invoke("show", path)["item_order"] == [
        "mode",
        "units",
        "direction",
        "fare",
        "tip",
    ]
    edited = Survey.git.load(path, sync_coop=False)
    page = edited.next_group(current_group="travel", answers={"mode.answer": "A"})
    assert [item.name for item in page["items"]] == [
        "units",
        "direction",
        "fare",
        "tip",
    ]
    assert edited.rule_collection.to_dict() == s.rule_collection.to_dict()
    assert edited.memory_plan.to_dict() == s.memory_plan.to_dict()
    assert (
        "direction"
        not in Survey.git.load(
            path, ref=head, sync_coop=False
        )._instruction_names_to_instructions
    )
    saved = path.read_bytes()
    invoke(*args, ok=False)
    invoke(
        "add-instruction",
        path,
        "--name",
        "new",
        "--text",
        "x",
        "--before",
        "missing",
        ok=False,
    )
    assert path.read_bytes() == saved


@pytest.mark.parametrize("extension", ["ep", "json"])
def test_independent_model_preview_and_clear(tmp_path, extension):
    path = tmp_path / ("survey." + extension)
    s = Survey(
        [
            choice("delivery", "Which speed?"),
            choice("audit", "Review {{ delivery.answer }} for {{ region }}."),
        ]
    )
    if extension == "ep":
        s.git.save(path)
    else:
        path.write_text(json.dumps(s.to_dict()))
    args = [
        "set-question-model",
        path,
        "audit",
        "--model",
        "gpt-4o-mini",
        "--service",
        "openai",
        "--system-prompt",
        "Independent auditor.",
    ]
    invoke(*args)
    info = invoke("questions", path)["questions"][1]
    assert info["question_options"] == ["A", "B"]
    assert info["model_override"] == {
        "model": "gpt-4o-mini",
        "service": "openai",
        "system_prompt": "Independent auditor.",
    }
    for answer in ["overnight", "standard"]:
        p = invoke(
            "preview-prompt",
            path,
            "audit",
            "--answers",
            json.dumps({"delivery": answer}),
            "--traits",
            '{"role":"SHOPPER"}',
            "--scenario",
            '{"region":"Iceland"}',
        )
        assert p["system_prompt"] == "Independent auditor."
        assert answer in p["user_prompt"] and "Iceland" in p["user_prompt"]
        assert p["model_override"] == info["model_override"]
    before = path.read_bytes()
    invoke("preview-prompt", path, "audit", "--answers", '{"audit":"future"}', ok=False)
    invoke("set-question-model", path, "audit", "--model", "test", ok=False)
    assert path.read_bytes() == before
    invoke("set-question-model", path, "audit", "--clear")
    assert "model_override" not in invoke("questions", path)["questions"][1]
    assert invoke("preview-prompt", path, "audit")["model_override"] is None


def test_preview_includes_only_configured_memory(tmp_path):
    path = tmp_path / "recall.ep"
    survey = Survey([choice("prior", "Choose."), choice("review", "Evaluate it.")])
    survey.git.save(path)
    args = ("preview-prompt", path, "review", "--answers", '{"prior":"SAMPLE_ANSWER"}')
    assert "SAMPLE_ANSWER" not in invoke(*args)["user_prompt"]
    invoke("set-memory", path, "--target", "review=prior")
    assert "SAMPLE_ANSWER" in invoke(*args)["user_prompt"]


def test_instruction_order_with_existing_change_instruction(tmp_path):
    from edsl.instructions import ChangeInstruction

    path = tmp_path / "directions.ep"
    survey = Survey(
        [
            Instruction("intro", "First part."),
            choice("first", "First?"),
            ChangeInstruction(drop=["intro"]),
            choice("second", "Second?"),
        ]
    )
    survey.git.save(path)
    invoke(
        "add-instruction",
        path,
        "--name",
        "extra",
        "--text",
        "Context.",
        "--before",
        "second",
    )
    details = invoke("show", path)
    assert details["item_order"][-2:] == ["extra", "second"]
    assert any(entry.get("drop") == ["intro"] for entry in details["instructions"])
