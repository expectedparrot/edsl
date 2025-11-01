import textwrap

from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText
from edsl.agents import Agent

# Initial survey to collect the problematic survey options
initial_survey = Survey(
    [
        QuestionList(
            question_name="raw_options",
            question_text="What are the survey options that need to be cleaned and ordered? (Paste them as a list)",
        ),
        QuestionFreeText(
            question_name="option_context",
            question_text="What do these options represent? (e.g., 'income bands', 'age ranges', 'satisfaction levels', 'numerical ratings')",
        ),
    ]
)

# Create a specialized agent for survey design and data analysis
survey_expert = Agent(
    name="survey_methodologist",
    traits={
        "expertise": "survey methodology, data analysis, and questionnaire design",
        "attention_to_detail": "meticulous about proper ordering and completeness of survey options",
    },
)

# Stage 1: Identify missing values and gaps
missing_values_question = QuestionList(
    question_name="missing_values",
    question_text=textwrap.dedent(
        """
    Analyze these survey options for {{ scenario.option_context }}:

    Options: {{ scenario.raw_options }}

    Identify any missing values or gaps in the sequence. For example:
    - If these are numerical ratings like 1,2,3,5,7 - what numbers are missing?
    - If these are ranges like "18-24, 25-34, 45-54" - what ranges are missing?
    - If these are ordinal categories, what logical steps are skipped?

    Return a list of the missing values/options that should be included to make this a complete set.
    If no values are missing, return an empty list.
    """
    ),
)

# Stage 2: Create properly ordered and complete option list
ordered_options_question = QuestionList(
    question_name="ordered_complete_options",
    question_text=textwrap.dedent(
        """
    Now create the final, properly ordered list of survey options.

    Original options: {{ scenario.raw_options }}
    Context: {{ scenario.option_context }}
    Missing values identified: {{ scenario.missing_values }}

    Create a complete, properly ordered list that:
    1. Includes the original options
    2. Adds any missing values identified in the previous step
    3. Orders them logically (numerical order, chronological order, intensity order, etc.)
    4. Uses consistent formatting

    For example:
    - Numerical ratings should be in ascending order: 1, 2, 3, 4, 5
    - Income bands should be in ascending order: "$0-25k", "$25k-50k", "$50k-75k", etc.
    - Age ranges should be chronological: "18-24", "25-34", "35-44", etc.
    - Satisfaction levels should follow logical progression: "Very Dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very Satisfied"

    Return only the final ordered list of options.
    """
    ),
)

# Create explanation question for the logic used
explanation_question = QuestionFreeText(
    question_name="ordering_explanation",
    question_text=textwrap.dedent(
        """
    Explain the logic you used to order these options and any missing values you added.

    Original: {{ scenario.raw_options }}
    Final: {{ ordered_complete_options.answer }}
    Missing added: {{ scenario.missing_values }}

    Provide a brief explanation of:
    1. What ordering principle you applied (numerical, chronological, intensity, etc.)
    2. Why you added the specific missing values
    3. Any assumptions you made about the survey context
    """
    ),
)

# Build the two-stage jobs pipeline
jobs_object = (
    # Stage 1: Identify missing values
    Survey([missing_values_question])
    .to_jobs()
    .select("scenario.raw_options", "scenario.option_context", "answer.missing_values")
    .to_scenario_list()
    # Stage 2: Create ordered complete options and explanation
    .to(Survey([ordered_options_question, explanation_question]))
)

# Output formatter for the clean option list
clean_options_formatter = (
    OutputFormatter(description="Clean Survey Options", output_type="ScenarioList")
    .select("answer.ordered_complete_options", "answer.ordering_explanation")
    .to_scenario_list()
    .rename(
        {
            "ordered_complete_options": "final_options",
            "ordering_explanation": "methodology",
        }
    )
)

# Output formatter for detailed analysis
analysis_formatter = (
    OutputFormatter(description="Option Analysis Report", output_type="markdown")
    .select(
        "scenario.raw_options",
        "scenario.option_context",
        "answer.missing_values",
        "answer.ordered_complete_options",
        "answer.ordering_explanation",
    )
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# Output formatter that creates a survey-ready format
survey_ready_formatter = (
    OutputFormatter(description="Survey Ready Options", output_type="ScenarioList")
    .select("answer.ordered_complete_options")
    .expand("answer.ordered_complete_options")
    .select("answer.ordered_complete_options")
    .to_scenario_list()
    .rename({"ordered_complete_options": "option"})
)

# Create the complete macro
macro = Macro(
    application_name="survey_option_inference",
    display_name="Survey Option Inference",
    short_description="Infer survey answer options automatically.",
    long_description="This application automatically infers appropriate answer options for survey questions based on question text and context, helping to design better structured surveys.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "clean": clean_options_formatter,
        "analysis": analysis_formatter,
        "survey_ready": survey_ready_formatter,
    },
    default_formatter_name="clean",
)

if __name__ == "__main__":
    # Test with income bands example
    result = macro.output(
        params={
            "raw_options": [
                "$25,000-$49,999",
                "$75,000-$99,999",
                "$0-$24,999",
                "$100,000+",
            ],
            "option_context": "household income ranges",
        },
        verbose=True,
    )

    print("=== Clean Options Results ===")
    print(result)

    # Test with satisfaction ratings with gaps
    result2 = macro.output(
        params={
            "raw_options": ["Very Satisfied", "Satisfied", "Very Dissatisfied"],
            "option_context": "customer satisfaction levels",
        },
        verbose=True,
    )

    print("\n=== Satisfaction Ratings Results ===")
    print(result2)

    # Test with numerical ratings with missing values
    result3 = macro.output(
        params={
            "raw_options": [1, 2, 3, 5, 7, 10],
            "option_context": "quality ratings from 1 to 10",
        },
        verbose=True,
    )

    print("\n=== Numerical Ratings Results ===")
    print(result3)
