"""Local runner coverage for with-other validator repair recursion."""

from edsl import Model, QuestionMultipleChoiceWithOther


def test_long_option_with_trailing_punctuation_repairs_locally():
    long_option = (
        "Share complete data with the selected partner and limited data with "
        "the other non-selected partners"
    )
    question = QuestionMultipleChoiceWithOther(
        question_name="sharing_policy",
        question_text="Choose a sharing policy.",
        question_options=["Do not share data", long_option, "Not sure"],
    )
    model = Model("test", canned_response=f"{long_option}.")

    results = question.by(model).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    assert results.select("answer.sharing_policy").to_list() == [long_option]

