"""Build the literature-based cognitive judgment task surveys."""

from edsl import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)


# Tversky & Kahneman (1983), direct-transparent Linda test, p. 299.
# The original study counterbalanced these alternatives. The two surveys below
# implement an exact 100/100 split per model; do not randomize the options.
LINDA_PROFILE = (
    "Linda is 31 years old, single, outspoken and very bright. She majored in "
    "philosophy. As a student, she was deeply concerned with issues of "
    "discrimination and social justice, and also participated in anti-nuclear "
    "demonstrations."
)
LINDA_BANK_TELLER = "Linda is a bank teller."
LINDA_CONJUNCTION = (
    "Linda is a bank teller and is active in the feminist movement."
)


def make_linda_survey(options: list[str]) -> Survey:
    return Survey(
        [
            QuestionMultipleChoice(
                question_name="linda_choice",
                question_text=(
                    f"{LINDA_PROFILE} Which of the following two statements is "
                    "more probable?"
                ),
                question_options=options,
                include_comment=False,
            )
        ]
    )


# Kahneman & Tversky (1973), engineer/lawyer prior manipulation, pp. 54–56.
# Only Jack, Dick, and the no-information item are available in the source
# text; this is intentionally labeled a partial replication.
JACK_PROFILE = (
    "Jack is a 45-year-old man. He is married and has four children. He is "
    "generally conservative, careful, and ambitious. He shows no interest in "
    "political and social issues and spends most of his free time on his many "
    "hobbies which include home carpentry, sailing, and mathematical puzzles."
)
DICK_PROFILE = (
    "Dick is a 30-year-old man. He is married with no children. A man of high "
    "ability and high motivation, he promises to be quite successful in his "
    "field. He is well liked by his colleagues."
)
NULL_PROFILE = (
    "Suppose now that you are given no information whatsoever about an "
    "individual chosen at random from the sample."
)


def engineer_question(name: str, profile: str) -> QuestionNumerical:
    return QuestionNumerical(
        question_name=name,
        question_text=(
            "A panel of psychologists interviewed and administered personality "
            "tests to 100 successful professionals. The sample contains "
            "{{ scenario.engineer_count }} engineers and "
            "{{ scenario.lawyer_count }} lawyers. "
            f"{profile} The probability that this person is one of the "
            "{{ scenario.target_count }} {{ scenario.target_occupation }} in "
            "the sample of 100 is ___%."
        ),
        min_value=0,
        max_value=100,
    )


survey = make_linda_survey([LINDA_BANK_TELLER, LINDA_CONJUNCTION])
linda_reverse_survey = make_linda_survey([LINDA_CONJUNCTION, LINDA_BANK_TELLER])

engineer_lawyer_survey = Survey(
    [
        engineer_question("jack_probability", JACK_PROFILE),
        engineer_question("dick_probability", DICK_PROFILE),
        engineer_question("null_probability", NULL_PROFILE),
    ]
)

# Frederick (2005) CRT bat-and-ball item; Oechssler et al. (2009) report the
# human response distribution. Keep the original open-response format.
bat_ball_survey = Survey(
    [
        QuestionFreeText(
            question_name="bat_ball_answer",
            question_text=(
                "A bat and a ball cost $1.10 in total. The bat costs $1.00 more "
                "than the ball. How much does the ball cost?"
            ),
        )
    ]
)


def save_objects() -> None:
    survey.git.save("survey_linda_order_a.ep")
    linda_reverse_survey.git.save("survey_linda_order_b.ep")
    engineer_lawyer_survey.git.save("survey_engineer_lawyer.ep")
    bat_ball_survey.git.save("survey_bat_ball.ep")


if __name__ == "__main__":
    save_objects()
