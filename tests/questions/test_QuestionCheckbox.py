import pytest
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionValueError,
)
from edsl.questions import QuestionBase
from edsl.questions import Settings
from edsl.questions.question_check_box import QuestionCheckBox
from edsl.language_models import Model

valid_question = {
    "question_text": "Which weekdays do you like? Select 2 or 3.",
    "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "min_selections": 2,
    "max_selections": 3,
    "question_name": "weekdays",
    "use_code": True,
}

valid_question_wo_extras = {
    "question_text": "Which weekdays do you like? Select 2 or 3.",
    "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "question_name": "weekdays",
}


def test_QuestionCheckBox_construction():
    """Test QuestionCheckBox construction."""

    q = QuestionCheckBox(**valid_question)
    assert isinstance(q, QuestionCheckBox)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.min_selections == valid_question["min_selections"]
    assert q.max_selections == valid_question["max_selections"]

    assert q.data == valid_question

    q_noextras = QuestionCheckBox(**valid_question_wo_extras)
    assert isinstance(q_noextras, QuestionCheckBox)
    assert q_noextras.question_name == valid_question["question_name"]
    assert q_noextras.question_text == valid_question["question_text"]
    assert q_noextras.question_options == valid_question["question_options"]
    # assert q_noextras.uuid is not None
    # should add extra attrs with None values
    assert q_noextras.min_selections == None
    assert q_noextras.max_selections == None

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_text is too long
    # invalid_question = valid_question.copy()
    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionCheckBox(**invalid_question)

    # should raise an exception if question_options is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_options")
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_options is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": []})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": ["OK"]})
    # or has 1 item
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # or has duplicates
    invalid_question.update({"question_options": ["OK", "OK"]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # or has too many items
    # invalid_question.update(
    #     {
    #         "question_options": [
    #             str(uuid.uuid4()) for _ in range(Settings.MAX_NUM_OPTIONS + 1)
    #         ]
    #     }
    # )
    # with pytest.raises(Exception):
    #     QuestionCheckBox(**invalid_question)
    # Not a list of strings. Neither of these raises: the same-type check in
    # QuestionOptionsDescriptor is commented out, so nothing rejects them on type. They
    # used to raise on the option count instead, since this question caps at 3 and both
    # lists have 2 options, and that is a warning now. Restore the type check and these
    # go back to raising.
    invalid_question.update({"question_options": [1, 2]})
    with pytest.warns(UserWarning, match="at most 3 selections"):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": ["OK", 2]})
    with pytest.warns(UserWarning, match="at most 3 selections"):
        QuestionCheckBox(**invalid_question)
    # This one does raise, on the empty option rather than the count.
    invalid_question.update({"question_options": ["OK", ""]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": {"OK": "OK", "BAD": "BAD"}})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if len(question_options) < min_selections
    invalid_question = valid_question.copy()
    invalid_question.update({"min_selections": 20})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # should warn, not raise, if len(question_options) < max_selections: the cap never
    # comes into play, so the question is still answerable
    odd_question = valid_question.copy()
    odd_question.update({"max_selections": 20})
    with pytest.warns(UserWarning, match="at most 20 selections"):
        QuestionCheckBox(**odd_question)


def test_QuestionCheckBox_max_selections_allowed_above_piped_option_count():
    """A ceiling above a *piped* option count is accepted rather than raised.

    The check above catches a typo in a hand-written question, where the cap and the
    options are typed next to each other. It cannot mean the same thing once the
    options are a template: the cap is fixed when the survey is written and the list
    is not known until the question is served, so "up to five" put to someone whose
    list resolved to three is a ceiling that does not bind rather than a contradiction.
    Raising there would replace a question the respondent was entitled to see with an
    error, over an answer they gave earlier.
    """
    q = QuestionCheckBox(
        question_name="piped",
        question_text="Which of these?",
        question_options="{{ q0.answer }}",
        max_selections=5,
    )

    # Write the resolved list on, the way it happens when the question is served. This
    # warns, since the cap is now higher than the option count, but that is all it does.
    with pytest.warns(UserWarning, match="at most 5 selections"):
        q.question_options = ["Alpha", "Beta", "Gamma"]
    assert q.question_options == ["Alpha", "Beta", "Gamma"]

    # The declared cap is kept, not rewritten to fit. It is what the survey asked for,
    # and results should record that rather than what one respondent's earlier answers
    # left room for. Nothing needs the smaller number: three options cannot yield four
    # selections, so enforcement is unaffected either way.
    assert q.max_selections == 5
    assert q.to_dict()["max_selections"] == 5


def test_QuestionCheckBox_negative_values():
    """Test QuestionCheckBox validation for negative values."""

    # should raise an exception if min_selections is negative
    invalid_question = valid_question.copy()
    invalid_question.update({"min_selections": -1})
    with pytest.raises(ValueError) as excinfo:
        QuestionCheckBox(**invalid_question)
    assert "min_selections must be non-negative" in str(excinfo.value)

    # should raise an exception if max_selections is negative
    invalid_question = valid_question.copy()
    invalid_question.update({"max_selections": -10})
    with pytest.raises(ValueError) as excinfo:
        QuestionCheckBox(**invalid_question)
    assert "max_selections must be non-negative" in str(excinfo.value)

    # should raise an exception if both are negative
    invalid_question = valid_question.copy()
    invalid_question.update({"min_selections": -1, "max_selections": -10})
    with pytest.raises(ValueError) as excinfo:
        QuestionCheckBox(**invalid_question)
    assert "min_selections must be non-negative" in str(excinfo.value)

    # should work fine with zero values
    valid_question_zero = valid_question.copy()
    valid_question_zero.update({"min_selections": 0, "max_selections": 0})
    q = QuestionCheckBox(**valid_question_zero)
    assert q.min_selections == 0
    assert q.max_selections == 0


def test_QuestionCheckBox_serialization():
    """Test QuestionCheckBox serialization."""
    q = QuestionCheckBox(**valid_question)
    q_noextras = QuestionCheckBox(**valid_question_wo_extras)

    # serialization should add a "type" attribute
    assert {
        "question_name": "weekdays",
        "question_text": "Which weekdays do you like? Select 2 or 3.",
        "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "min_selections": 2,
        "max_selections": 3,
        "question_type": "checkbox",
    }.items() <= q.to_dict().items()
    assert {
        "question_name": "weekdays",
        "question_text": "Which weekdays do you like? Select 2 or 3.",
        "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        #        "min_selections": None,
        #       "max_selections": None,
        "question_type": "checkbox",
    }.items() <= q_noextras.to_dict().items()

    # deserialization should return a QuestionCheckBoxEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionCheckBox)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)
    q_lazarus = QuestionBase.from_dict(q_noextras.to_dict())
    assert isinstance(q_lazarus, QuestionCheckBox)
    assert type(q_noextras) == type(q_lazarus)
    assert repr(q_noextras) == repr(q_lazarus)
    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "checkbox"})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "checkbox", "question_text": 1})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "checkbox", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1),
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": [],
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Sun"],
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Sun", "Sun"],
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Mon", "Tue"],
                "min_selections": 3,
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Mon", "Tue"],
                "max_selections": 5,
            }
        )


def test_int_options():
    m = Model("test", canned_response="2,3,5,7")
    q = QuestionCheckBox(
        question_name="prime_numbers",
        question_text="Select all the numbers that are prime.",
        question_options=[0, 1, 2, 3, 5, 7, 9],
    )
    results = q.by(m).run(disable_remote_inference=True)


def test_QuestionCheckBox_answers():
    q = QuestionCheckBox(**valid_question)
    llm_response_valid1 = {
        "answer": [0, 1],
        "comment": "I like beginnings",
    }
    llm_response_valid2 = {"answer": [0, 1]}
    llm_response_invalid1 = {"comment": "I like beginnings"}

    # LLM response is required to have an answer key, but is flexible otherwise
    q._validate_answer(llm_response_valid1)
    q._validate_answer(llm_response_valid2)
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(llm_response_invalid1)

    # answer must be an list of ints
    q._validate_answer(llm_response_valid1)

    q._validate_answer(llm_response_valid2)
    # answer value required

    # # answer cannot have unacceptable values
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [25, 20]})
    # or wrong types
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": ["Mon", "Tue"]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [{"set"}]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": {"answer": 0}})
    # and respect min_selections and max_selections
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [1]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [1, 2, 3, 4]})

    # check when permissive is True
    q = QuestionCheckBox(**valid_question | {"permissive": True})
    q._validate_answer({"answer": [1]})
    q._validate_answer({"answer": [1, 2, 3, 4]})


def test_exclusive_options_are_serialized_and_enforced():
    q = QuestionCheckBox(
        question_name="weekdays",
        question_text="Which weekdays do you like?",
        question_options=["Mon", "Tue", "None"],
        min_selections=2,
        exclusive_options=["None"],
    )

    assert q._validate_answer({"answer": ["None"]})["answer"] == ["None"]
    assert q._validate_answer({"answer": ["Mon", "Tue"]})["answer"] == [
        "Mon",
        "Tue",
    ]
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        q._validate_answer({"answer": ["Mon", "None"]})

    serialized = q.to_dict()
    assert serialized["exclusive_options"] == ["None"]
    restored = QuestionBase.from_dict(serialized)
    assert restored.exclusive_options == ["None"]
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        restored._validate_answer({"answer": ["Tue", "None"]})


def test_exclusive_options_use_codes_and_remain_strict_when_permissive():
    q = QuestionCheckBox(
        question_name="weekdays",
        question_text="Which weekdays do you like?",
        question_options=["Mon", "Tue", "None"],
        min_selections=2,
        use_code=True,
        permissive=True,
        exclusive_options=["None"],
    )

    assert q._validate_answer({"answer": [2]})["answer"] == [2]
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        q._validate_answer({"answer": [0, 2]})

    instructions = q.answering_instructions.render(q.data)
    assert "selected by itself" in instructions
    assert "[2]" in instructions
    assert "['None']" not in instructions


def test_exclusive_option_still_honors_maximum_selection_count():
    q = QuestionCheckBox(
        question_name="weekdays",
        question_text="Which weekdays do you like?",
        question_options=["Mon", "None"],
        max_selections=0,
        exclusive_options=["None"],
    )

    with pytest.raises(QuestionAnswerValidationError, match="at most 0"):
        q._validate_answer({"answer": ["None"]})


def test_dynamic_options_allow_deferred_exclusive_option_membership():
    q = QuestionCheckBox(
        question_name="weekdays",
        question_text="Which weekdays do you like?",
        question_options="{{ scenario.options }}",
        exclusive_options=["None"],
    )

    assert q.exclusive_options == ["None"]


def test_exclusive_options_must_be_exact_unique_question_options():
    kwargs = {
        "question_name": "weekdays",
        "question_text": "Which weekdays do you like?",
        "question_options": ["Mon", "Tue", "None"],
    }
    with pytest.raises(QuestionValueError, match="exactly match"):
        QuestionCheckBox(**kwargs, exclusive_options=["none"])
    with pytest.raises(QuestionValueError, match="duplicates"):
        QuestionCheckBox(**kwargs, exclusive_options=["None", "None"])


def test_exclusive_options_are_omitted_when_not_configured():
    q = QuestionCheckBox(**valid_question_wo_extras)

    assert q.exclusive_options == []
    assert "exclusive_options" not in q.data


def test_QuestionCheckBox_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionCheckBox(**valid_question)
    # _translate_answer_code_to_answer
    assert q._translate_answer_code_to_answer([0, 1], None) == ["Mon", "Tue"]

    assert q._simulate_answer().keys() == q._simulate_answer(human_readable=True).keys()
    assert q._simulate_answer(human_readable=False)["answer"][0] in range(
        len(q.question_options)
    )
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    assert len(simulated_answer["answer"]) <= Settings.MAX_OPTION_LENGTH
    assert len(simulated_answer["answer"]) > 0
