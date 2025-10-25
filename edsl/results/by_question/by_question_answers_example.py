"""Example usage of ByQuestionAnswers for analyzing answer distributions.

This script demonstrates how to use the ByQuestionAnswers class to analyze
and visualize answer distributions for different question types.
"""

from by_question_answers import ByQuestionAnswers

# Example 1: Analyze from a Results object
def example_from_results():
    """Example using actual Results object."""
    from edsl.results import Results

    # Get example results
    results = Results.example()

    # Analyze a question
    question_name = list(results.question_names)[0]
    analyzer = ByQuestionAnswers.from_results(results, question_name)

    # Show analysis
    print("=" * 60)
    print("EXAMPLE 1: Analysis from Results")
    print("=" * 60)
    analyzer.show()


# Example 2: Create analyzer directly for multiple choice
def example_multiple_choice():
    """Example with multiple choice question."""
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name="favorite_color",
        question_text="What is your favorite color?",
        question_options=["Red", "Blue", "Green", "Yellow"]
    )

    # Simulate responses
    answers = ["Red", "Blue", "Red", "Green", "Red", "Blue", "Yellow", "Red"]

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multiple Choice Analysis")
    print("=" * 60)
    analyzer.show()


# Example 3: Numerical question
def example_numerical():
    """Example with numerical question."""
    from edsl.questions import QuestionNumerical

    q = QuestionNumerical(
        question_name="age",
        question_text="What is your age?"
    )

    # Simulate responses
    import numpy as np
    np.random.seed(42)
    answers = list(np.random.normal(35, 10, 50).astype(int))

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 3: Numerical Analysis")
    print("=" * 60)
    analyzer.show()


# Example 4: Linear scale question
def example_linear_scale():
    """Example with linear scale question."""
    from edsl.questions import QuestionLinearScale

    q = QuestionLinearScale(
        question_name="satisfaction",
        question_text="How satisfied are you with our service?",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Very Unsatisfied", 5: "Very Satisfied"}
    )

    # Simulate responses (skewed positive)
    answers = [5, 4, 5, 3, 4, 5, 5, 4, 3, 5, 4, 4]

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 4: Linear Scale Analysis")
    print("=" * 60)
    analyzer.show()


# Example 5: Checkbox question
def example_checkbox():
    """Example with checkbox question (multiple selections)."""
    from edsl.questions import QuestionCheckBox

    q = QuestionCheckBox(
        question_name="interests",
        question_text="What are your interests? (select all that apply)",
        question_options=["Sports", "Music", "Reading", "Travel", "Cooking"]
    )

    # Simulate responses (lists of selections)
    answers = [
        ["Sports", "Music"],
        ["Reading", "Travel"],
        ["Music", "Cooking"],
        ["Sports", "Travel", "Cooking"],
        ["Reading"],
        ["Sports", "Music", "Travel"],
    ]

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 5: Checkbox Analysis")
    print("=" * 60)
    analyzer.show()


# Example 6: Free text question
def example_free_text():
    """Example with free text question."""
    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name="feedback",
        question_text="What suggestions do you have for improvement?"
    )

    # Simulate responses of varying lengths
    answers = [
        "Great service!",
        "Could be faster",
        "I really appreciate the attention to detail and the quality of work",
        "Good",
        "Would recommend to friends",
        "The process was smooth and efficient. Very pleased with the results.",
    ]

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 6: Free Text Analysis")
    print("=" * 60)
    analyzer.show()


# Example 7: Rank question
def example_rank():
    """Example with rank question."""
    from edsl.questions import QuestionRank

    q = QuestionRank(
        question_name="priorities",
        question_text="Rank these priorities from most to least important",
        question_options=["Cost", "Quality", "Speed", "Support"]
    )

    # Simulate responses (rankings)
    answers = [
        ["Quality", "Cost", "Speed", "Support"],
        ["Cost", "Speed", "Quality", "Support"],
        ["Quality", "Support", "Cost", "Speed"],
        ["Quality", "Speed", "Support", "Cost"],
    ]

    analyzer = ByQuestionAnswers.create(q, answers)

    print("\n" + "=" * 60)
    print("EXAMPLE 7: Rank Analysis")
    print("=" * 60)
    analyzer.show()


if __name__ == "__main__":
    # Run all examples
    try:
        example_from_results()
    except Exception as e:
        print(f"Skipping Results example: {e}")

    example_multiple_choice()
    example_numerical()
    example_linear_scale()
    example_checkbox()
    example_free_text()
    example_rank()
