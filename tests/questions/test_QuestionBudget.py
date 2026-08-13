import pytest
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions import QuestionBudget
from edsl.questions.question_budget import QuestionBudget


# def test_QuestionBudget_main():
#    main()


valid_question = {
    "question_text": "How would you allocate $100?",
    "question_options": ["Pizza", "Ice Cream", "Burgers", "Salad"],
    "budget_sum": 100,
    "question_name": "food_budget",
}

valid_question_w_extras = {
    "question_text": "How would you allocate $100?",
    "question_options": ["Pizza", "Ice Cream", "Burgers", "Salad"],
    "budget_sum": 100,
    "question_name": "food_budget",
}


def test_QuestionBudget_construction():
    """Test QuestionBudget construction."""

    q = QuestionBudget(**valid_question)
    assert isinstance(q, QuestionBudget)
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]

    q = QuestionBudget(**valid_question_w_extras)
    assert isinstance(q, QuestionBudget)
    assert q.question_name == valid_question_w_extras["question_name"]
    assert q.data == valid_question_w_extras

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    # or if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    # or if question_text is too long
    invalid_question = valid_question.copy()

    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionBudget(**invalid_question)

    # should raise an exception if question_options is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_options")
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    # or if question_options is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": []})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    # a single option is valid
    single_option_question = valid_question.copy()
    single_option_question.update({"question_options": ["OK"]})
    assert QuestionBudget(**single_option_question).question_options == ["OK"]
    # or has duplicates
    invalid_question.update({"question_options": ["OK", "OK"]})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    # or too many items
    # invalid_question.update(
    #     {
    #         "question_options": [
    #             str(uuid.uuid4()) for _ in range(Settings.MAX_NUM_OPTIONS + 1)
    #         ]
    #     }
    # )
    # with pytest.raises(Exception):
    #     QuestionBudget(**invalid_question)
    # # or not of type list of strings
    invalid_question.update({"question_options": [1, 2]})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    invalid_question.update({"question_options": ["OK", 2]})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    invalid_question.update({"question_options": ["OK", ""]})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)
    invalid_question.update({"question_options": {"OK": "OK", "BAD": "BAD"}})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)

    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionBudget(**invalid_question)


def test_QuestionBudget_answers():
    # valid_answer = {"answer": {"0": 25, "1": 25, "2": 25, "3": 25}, "comment": "Yum!"}
    valid_answer = {"answer": [25, 25, 25, 25], "comment": "Yum!"}
    q = QuestionBudget(**valid_question)
    # answer must be an integer or interpretable as integer
    q._validate_answer(valid_answer)
    # answer value required
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": None})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": None})
    # all options must be present
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": {0: 50, 1: 25, 2: 25}})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)
    # answer must be in range of question_options
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": {0: 25, 1: 25, 2: 25, 3: 0, 4: 25}})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)
    # answers must sum to budget_sum
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": {0: 25, 1: 25, 2: 25, 3: 26}})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)
    # answers cannot be negative
    invalid_answer = valid_answer.copy()
    invalid_answer.update({"answer": {0: -1, 1: 25, 2: 25, 3: 51}})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(invalid_answer)


def test_QuestionBudget_repairs_labeled_mapping_in_question_order():
    q = QuestionBudget(**valid_question)

    validated = q.response_validator.validate(
        {
            "answer": {
                "Salad": 10,
                "Pizza": 40,
                "Burgers": 20,
                "Ice Cream": 30,
            }
        }
    )

    assert validated["answer"] == [40, 30, 20, 10]


def test_QuestionBudget_repairs_small_rounding_residual():
    q = QuestionBudget(**valid_question)

    validated = q.response_validator.validate({"answer": [33.3, 33.3, 33.3, 0]})

    assert sum(validated["answer"]) == q.budget_sum
    assert validated["answer"] == pytest.approx([33.4, 33.3, 33.3, 0])


def test_QuestionBudget_repairs_single_labeled_allocation_string():
    q = QuestionBudget(
        question_name="revenue_split",
        question_text="Allocate revenue.",
        question_options=["Product revenue %", "Advertising revenue %"],
        budget_sum=100,
    )

    validated = q.response_validator.validate(
        {"answer": ["Product revenue %: 50, Advertising revenue %: 50"]}
    )

    assert validated["answer"] == [50, 50]


def test_QuestionBudget_rejects_partial_labeled_allocation_string():
    q = QuestionBudget(
        question_name="revenue_split",
        question_text="Allocate revenue.",
        question_options=["Product revenue %", "Advertising revenue %"],
        budget_sum=100,
    )

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate({"answer": ["Product revenue %: 100"]})


@pytest.mark.parametrize(
    "answer",
    [
        [30, 30, 30, 0],  # discrepancy is too large to be rounding
        [40, 30, -1, 31],  # repair must not mask a negative allocation
        {"Pizza": 50, "unknown": 50},  # labels do not identify every option
    ],
)
def test_QuestionBudget_does_not_repair_unsafe_answers(answer):
    q = QuestionBudget(**valid_question)

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate({"answer": answer})


def test_QuestionBudget_regex_repair_preserves_negative_sign():
    q = QuestionBudget(**valid_question)

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate({"answer": "40, 30, -1, 31"})


def test_QuestionBudget_extras():
    """Test QuestionBudget's extra functionalities."""
    q = QuestionBudget(**valid_question)
    # instructions
    # translate
    assert q._translate_answer_code_to_answer([25, 25, 25, 25], {}) == [
        {"Pizza": 25},
        {"Ice Cream": 25},
        {"Burgers": 25},
        {"Salad": 25},
    ]
    # _simulate_answer
    # assert q._simulate_answer().keys() == q._simulate_answer(human_readable=True).keys()
    # simulated_answer = q._simulate_answer(human_readable=False)
    # assert isinstance(simulated_answer, dict)
    # assert "answer" in simulated_answer
    # assert "comment" in simulated_answer
    # assert isinstance(simulated_answer["answer"], dict)
    # assert all(
    #     [type(k) == int and k in range(len(q.question_options))]
    #     for k in simulated_answer["answer"].keys()
    # )
    # assert round(sum(simulated_answer["answer"].values())) == q.budget_sum
    # assert list(q._simulate_answer(human_readable=False)["answer"].keys()) == list(
    #     range(len(q.question_options))
    # )
    # # form elements
