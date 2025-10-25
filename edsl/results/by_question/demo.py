"""Quick demo of ByQuestionAnswers functionality."""

from edsl.questions import QuestionMultipleChoice, QuestionNumerical, QuestionLinearScale
from by_question_answers import ByQuestionAnswers
import numpy as np


def demo_multiple_choice():
    """Demo multiple choice analysis."""
    print("=" * 70)
    print("DEMO 1: Multiple Choice Question")
    print("=" * 70)

    q = QuestionMultipleChoice(
        question_name="favorite_season",
        question_text="What is your favorite season?",
        question_options=["Spring", "Summer", "Fall", "Winter"]
    )

    # Simulate responses (Summer is most popular)
    answers = [
        "Summer", "Summer", "Spring", "Summer",
        "Fall", "Summer", "Winter", "Spring", "Summer"
    ]

    analyzer = ByQuestionAnswers.create(q, answers)
    analyzer.show()


def demo_numerical():
    """Demo numerical analysis."""
    print("\n" + "=" * 70)
    print("DEMO 2: Numerical Question")
    print("=" * 70)

    q = QuestionNumerical(
        question_name="hours_sleep",
        question_text="How many hours did you sleep last night?"
    )

    # Simulate responses (normally distributed around 7 hours)
    np.random.seed(123)
    answers = list(np.random.normal(7, 1.5, 30).round(1))

    analyzer = ByQuestionAnswers.create(q, answers)
    analyzer.show()


def demo_linear_scale():
    """Demo linear scale analysis."""
    print("\n" + "=" * 70)
    print("DEMO 3: Linear Scale Question")
    print("=" * 70)

    q = QuestionLinearScale(
        question_name="recommend",
        question_text="How likely are you to recommend us? (1-10)",
        question_options=list(range(1, 11)),
        option_labels={1: "Not at all likely", 10: "Extremely likely"}
    )

    # Simulate responses (skewed positive - mostly promoters)
    answers = [9, 10, 8, 9, 10, 7, 9, 10, 8, 9, 10, 10]

    analyzer = ByQuestionAnswers.create(q, answers)
    analyzer.show()


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "ByQuestionAnswers Demo" + " " * 31 + "║")
    print("║" + " " * 10 + "Analyzing Answer Distributions by Question" + " " * 15 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    demo_multiple_choice()
    demo_numerical()
    demo_linear_scale()

    print("\n" + "=" * 70)
    print("Demo complete! Try running by_question_answers_example.py for more.")
    print("=" * 70)
