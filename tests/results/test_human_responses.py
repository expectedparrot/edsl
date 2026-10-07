"""Results.from_human_responses: building Results from stored human survey responses."""

import json

import pytest
from pydantic import ValidationError

from edsl import Instruction, QuestionFreeText, QuestionMultipleChoice, Survey
from edsl.results import Results
from edsl.results.exceptions import ResultsError
from edsl.results.human_responses import HumanResponseEntry, HumanResponseRow
from edsl.runner.models import _encode_answer_value
from edsl.scenarios import FileStore


def make_survey():
    return Survey(
        [
            Instruction(name="intro", text="Welcome."),
            QuestionFreeText(question_name="name", question_text="Your name?"),
            QuestionMultipleChoice(
                question_name="color",
                question_text="Favorite color?",
                question_options=["red", "blue", "green"],
            ),
        ]
    ).add_skip_rule("color", "{{ name.answer }} == 'skip'")


def make_row(response_uuid="r1", entries=None, traits=None, scenario=None):
    return {
        "response_uuid": response_uuid,
        "response_json_string": json.dumps(entries or {}),
        "agent_traits_json_string": json.dumps(traits or {}),
        "scenario_json_string": json.dumps(scenario) if scenario is not None else None,
    }


ANSWERED = {
    "intro": {"answer": None, "comment": None, "started_at": "t0"},
    "name": {
        "answer": "Ada",
        "comment": "first",
        "started_at": "t1",
        "answered_at": "t2",
        "question_presented": True,
        "question_options": None,
    },
    "color": {
        "answer": "blue",
        "comment": None,
        "started_at": "t3",
        "answered_at": "t4",
        "question_presented": True,
        "question_options": ["green", "blue", "red"],
    },
}


def test_answers_comments_and_agent_come_from_the_row():
    results = Results.from_human_responses(
        make_survey(),
        [make_row(entries=ANSWERED, traits={"respondent_uuid": "p1", "age": 40})],
    )
    row = results.select(
        "agent.agent_name",
        "agent.respondent_uuid",
        "agent.age",
        "answer.name",
        "answer.color",
        "comment.name_comment",
    ).to_dicts(remove_prefix=False)[0]
    assert row == {
        "agent.agent_name": "r1",
        "agent.respondent_uuid": "p1",
        "agent.age": 40,
        "answer.name": "Ada",
        "answer.color": "blue",
        "comment.name_comment": "first",
    }


def test_per_question_fields_land_in_raw_model_response():
    results = Results.from_human_responses(make_survey(), [make_row(entries=ANSWERED)])
    rmr = results[0]["raw_model_response"]
    assert rmr["name_started_at"] == "t1"
    assert rmr["name_answered_at"] == "t2"
    assert rmr["name_question_presented"] is True
    assert rmr["color_answered_at"] == "t4"


def test_instructions_get_no_columns():
    results = Results.from_human_responses(make_survey(), [make_row(entries=ANSWERED)])
    assert not any("intro" in column for column in results.columns)


def test_stored_options_replace_the_survey_definition():
    results = Results.from_human_responses(make_survey(), [make_row(entries=ANSWERED)])
    attributes = results[0]["question_to_attributes"]
    assert attributes["color"]["question_options"] == ["green", "blue", "red"]
    # No stored options: the definition's are kept.
    assert attributes["name"]["question_options"] is None


def test_skipped_question_keeps_what_was_recorded():
    # Survey logic isn't re-run: the stored skip is what the Results shows.
    entries = {
        **ANSWERED,
        "name": {**ANSWERED["name"], "answer": "skip"},
        "color": {
            "answer": None,
            "comment": None,
            "started_at": None,
            "answered_at": None,
            "question_presented": False,
            "question_options": ["red", "blue", "green"],
        },
    }
    results = Results.from_human_responses(make_survey(), [make_row(entries=entries)])
    assert results[0]["answer"]["color"] is None
    assert results[0]["raw_model_response"]["color_question_presented"] is False


def test_question_without_an_entry_reads_none():
    results = Results.from_human_responses(
        make_survey(), [make_row(entries={"name": ANSWERED["name"]})]
    )
    assert results[0]["answer"]["color"] is None
    assert results[0]["comments_dict"]["color_comment"] is None
    assert results[0]["raw_model_response"]["color_started_at"] is None


def test_agent_index_trait_is_not_overwritten():
    rows = [
        make_row("r1", ANSWERED, {"agent_index": 7}),
        make_row("r2", ANSWERED, {"agent_index": None}),
    ]
    results = Results.from_human_responses(make_survey(), rows)
    assert results.select("agent.agent_index").to_list() == [7, None]


def test_agent_instruction_is_empty():
    results = Results.from_human_responses(make_survey(), [make_row(entries=ANSWERED)])
    assert results.select("agent.agent_instruction").to_list() == [""]


def test_scenario_comes_from_the_row():
    results = Results.from_human_responses(
        make_survey(), [make_row(entries=ANSWERED, scenario={"city": "Paris"})]
    )
    assert results.select("scenario.city").to_list() == ["Paris"]


def test_file_upload_answers_decode_unless_asked_not_to(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello")
    stored = _encode_answer_value(FileStore(str(path)))
    entries = {**ANSWERED, "name": {**ANSWERED["name"], "answer": stored}}
    rows = [make_row(entries=entries)]

    decoded = Results.from_human_responses(make_survey(), rows)
    assert isinstance(decoded[0]["answer"]["name"], FileStore)

    raw = Results.from_human_responses(make_survey(), rows, decode_files=False)
    assert raw[0]["answer"]["name"] == stored


def test_scenario_files_decode_unless_asked_not_to(tmp_path):
    path = tmp_path / "photo.txt"
    path.write_text("hello")
    stored = FileStore(str(path)).to_dict()
    rows = [make_row(entries=ANSWERED, scenario={"city": "Paris", "photo": stored})]

    decoded = Results.from_human_responses(make_survey(), rows)
    assert isinstance(decoded[0]["scenario"]["photo"], FileStore)

    raw = Results.from_human_responses(make_survey(), rows, decode_files=False)
    assert raw[0]["scenario"]["photo"] == stored
    assert raw[0]["scenario"]["city"] == "Paris"
    json.dumps(dict(raw[0]["scenario"]))


def test_rows_keep_their_order():
    rows = [make_row(f"r{i}", ANSWERED) for i in range(3)]
    results = Results.from_human_responses(make_survey(), rows)
    assert results.select("agent.agent_name").to_list() == ["r0", "r1", "r2"]


def test_round_trips_through_to_dict():
    results = Results.from_human_responses(
        make_survey(), [make_row(entries=ANSWERED, traits={"agent_index": 3})]
    )
    restored = Results.from_dict(results.to_dict())
    assert restored.select("answer.color").to_list() == ["blue"]
    assert restored.select("agent.agent_index").to_list() == [3]
    assert restored[0]["raw_model_response"]["name_answered_at"] == "t2"
    assert restored[0]["question_to_attributes"]["color"]["question_options"] == [
        "green",
        "blue",
        "red",
    ]


def test_missing_response_uuid_raises():
    row = make_row(entries=ANSWERED)
    row["response_uuid"] = None
    with pytest.raises(ResultsError):
        Results.from_human_responses(make_survey(), [row])


def test_no_responses_gives_empty_results():
    results = Results.from_human_responses(make_survey(), [])
    assert len(results) == 0


def test_typed_rows_are_accepted():
    row = HumanResponseRow(
        response_uuid="r1",
        response_json_string=json.dumps(ANSWERED),
        agent_traits_json_string=json.dumps({"age": 40}),
    )
    results = Results.from_human_responses(make_survey(), [row])
    assert results.select("answer.name").to_list() == ["Ada"]
    assert results.select("agent.age").to_list() == [40]


def test_unknown_keys_are_ignored():
    # A newer server's extra fields must not break an older client.
    entries = {**ANSWERED, "name": {**ANSWERED["name"], "shown_text": "Your name?"}}
    row = {**make_row(entries=entries), "response_status": "complete"}
    results = Results.from_human_responses(make_survey(), [row])
    assert results[0]["answer"]["name"] == "Ada"


@pytest.mark.parametrize(
    "options",
    [[0.5, 1.5, 2.5], [1, "2", 3.5], [["a", "b"], ["c"]]],
    ids=["fractional", "mixed", "nested"],
)
def test_any_supported_options_are_kept_as_is(options):
    # Matrix questions allow fractional options, and multiple choice and dropdown allow
    # lists; a response that recorded them must still build, unchanged.
    entries = {**ANSWERED, "color": {**ANSWERED["color"], "question_options": options}}
    results = Results.from_human_responses(make_survey(), [make_row(entries=entries)])
    assert results[0]["question_to_attributes"]["color"]["question_options"] == options


def test_malformed_entry_is_a_validation_error():
    entries = {**ANSWERED, "color": {**ANSWERED["color"], "question_presented": "maybe"}}
    with pytest.raises(ValidationError, match="question_presented"):
        Results.from_human_responses(make_survey(), [make_row(entries=entries)])


def test_row_parses_its_entries():
    row = HumanResponseRow.coerce(make_row(entries={"name": {"answer": "Ada"}}))
    assert row.entries() == {"name": HumanResponseEntry(answer="Ada")}
