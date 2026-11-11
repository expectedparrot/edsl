import pytest

pytest.importorskip("docx")

from docx import Document

from edsl import QuestionFreeText, QuestionLinearScale, QuestionMultipleChoice, Survey
from edsl.instructions import ChangeInstruction, Instruction


def _roundtrip(survey, tmp_path):
    path = tmp_path / "survey.docx"
    survey.to_docx(str(path))
    return Survey.from_docx(str(path)), path


def test_rules_roundtrip_boolean_text_and_scale_comparisons(tmp_path):
    choice = QuestionMultipleChoice(
        question_name="choice", question_text="Choose.", question_options=["No", "Yes"]
    )
    text = QuestionFreeText(question_name="why", question_text="Why?")
    end = QuestionFreeText(question_name="end", question_text="Anything else?")
    survey = Survey([choice, text, end])
    survey.add_skip_rule("why", "{{ choice.answer }} == 'No'")
    survey.add_skip_rule("end", "True")

    imported, _ = _roundtrip(survey, tmp_path)
    rules = imported.rule_collection.non_default_rules
    assert {rule.expression for rule in rules} == {"{{ choice.answer }} == 'No'", "True"}

    free_text = QuestionFreeText(question_name="free_text", question_text="Say a word.")
    followup = QuestionFreeText(question_name="followup", question_text="Continue?")
    survey = Survey([free_text, followup])
    survey.add_skip_rule("followup", "{{ free_text.answer }} == 'exact phrase'")
    imported, _ = _roundtrip(survey, tmp_path)
    assert imported.rule_collection.non_default_rules[0].expression == (
        "{{ free_text.answer }} == 'exact phrase'"
    )

    score = QuestionLinearScale(
        question_name="score", question_text="Score?", question_options=[0, 5, 10]
    )
    survey = Survey([score, QuestionFreeText(question_name="next", question_text="Next?")])
    survey.add_skip_rule("next", "{{ score.answer }} >= 5")
    imported, path = _roundtrip(survey, tmp_path)
    rule = imported.rule_collection.non_default_rules[0]
    assert rule.expression == "{{ score.answer }} >= 5"
    exported = Document(path)
    assert any("Q_score >= 2" in paragraph.text for paragraph in exported.paragraphs)


def test_change_instruction_roundtrips(tmp_path):
    survey = Survey(
        [
            Instruction(name="intro", text="Preface."),
            ChangeInstruction(drop=["intro"]),
            QuestionFreeText(question_name="q0", question_text="Question?"),
        ]
    )
    imported, _ = _roundtrip(survey, tmp_path)
    change = next(
        item for item in imported.recombined_questions_and_instructions()
        if isinstance(item, ChangeInstruction)
    )
    assert change.drop == ["intro"]
    assert imported._instruction_names_to_instructions["intro"].text == "Preface."


def test_dynamic_choice_templates_roundtrip_without_becoming_literals(tmp_path):
    string_options = QuestionMultipleChoice(
        question_name="dynamic_string", question_text="Pick.",
        question_options="{{ dynamic_options }}",
    )
    dict_options = QuestionMultipleChoice(
        question_name="dynamic_dict", question_text="Pick.",
        question_options={"from": "{{ prior.answer }}", "add": ["Other"]},
    )
    imported, _ = _roundtrip(Survey([string_options, dict_options]), tmp_path)
    assert imported.questions[0].question_options == "{{ dynamic_options }}"
    assert imported.questions[1].question_options == {
        "from": "{{ prior.answer }}", "add": ["Other"]
    }


def test_wording_and_negative_scale_labels_roundtrip(tmp_path):
    wording = "Response format: explain.\n1 = strongly disagree; explain.\nSecond paragraph."
    question = QuestionFreeText(question_name="open", question_text=wording)
    scale = QuestionLinearScale(
        question_name="scale", question_text="Scale?", question_options=[-2, -1, 0, 1, 2],
        option_labels={-2: "Low", 2: "High"},
    )
    imported, _ = _roundtrip(Survey([question, scale]), tmp_path)
    assert imported.questions[0].question_text == wording
    assert imported.questions[1].option_labels == {-2: "Low", 2: "High"}


def test_reordered_choice_lines_keep_codes_attached_to_options(tmp_path):
    choice = QuestionMultipleChoice(
        question_name="choice", question_text="Choose.", question_options=["No", "Yes"]
    )
    followup = QuestionFreeText(question_name="followup", question_text="Why?")
    survey = Survey([choice, followup])
    survey.add_skip_rule("followup", "{{ choice.answer }} == 'No'")
    _, path = _roundtrip(survey, tmp_path)

    document = Document(path)
    option_lines = [paragraph for paragraph in document.paragraphs if paragraph.text in {'1 = "No"', '2 = "Yes"'}]
    assert len(option_lines) == 2
    option_lines[0]._p.addprevious(option_lines[1]._p)
    document.save(path)

    imported = Survey.from_docx(str(path))
    assert imported.questions[0].question_options == ["No", "Yes"]
    assert imported.rule_collection.non_default_rules[0].expression == "{{ choice.answer }} == 'No'"


def test_logo_watermark_uses_packaged_asset(tmp_path):
    _, path = _roundtrip(Survey([QuestionFreeText(question_name="q0", question_text="Question?")]), tmp_path)
    assert Document(path).sections[0].header._element.xpath(".//a:blip")
