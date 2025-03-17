

def test_example():
    from edsl.questions import (
        QuestionMultipleChoice,
        QuestionNumerical,
        QuestionFreeText,
    )
    from edsl import Survey

    q1 = QuestionMultipleChoice(
        question_name="best_pet",
        question_text="What is the best kind of pet?",
        question_options=["Dog", "Fish", "Lizard", "Parrot"],
    )
    q2 = QuestionNumerical(
        question_name="ideal_fish",
        question_text="What is the ideal number of fish to own?",
    )
    q3 = QuestionFreeText(
        question_name="parrots", question_text="What are parrots known for?"
    )
    survey = Survey([q1, q2, q3]).add_rule(q1, "best_pet == 'Dog'", q3)
    results = survey.run()
    # breakpoint()
    assert results.select("best_pet") is not None
    assert results.select("ideal_fish") is None
    assert results.select("parrots") is not None
    # results.select("best_pet", "ideal_fish", "parrots").print(format="rich")
    # assert results.select("ideal_fish", "parrots") == {"best_pet": "Dog", "ideal_fish": None, "parrots": "talking"}
