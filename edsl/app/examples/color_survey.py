"""
Color Survey App

A simple EDSL app that collects information about favorite colors through a survey
and returns the results in various formats.
"""

import textwrap
from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionCheckBox, QuestionNumerical
from edsl.agents import Agent


# 1. Initial Survey - Collect user parameters for the color survey
initial_survey = Survey([
    QuestionFreeText(
        question_name="survey_context",
        question_text="What is the context or purpose of this color preference survey? (e.g., 'interior design preferences', 'brand color selection', 'art project')"
    ),
    QuestionMultipleChoice(
        question_name="survey_style",
        question_text="What style of questions would you prefer?",
        question_options=["casual and fun", "professional and formal", "creative and artistic"]
    ),
    QuestionNumerical(
        question_name="number_of_questions",
        question_text="How many color preference questions should be included?",
        min_value=3,
        max_value=10
    )
])


# 2. Processing Agent - Specialized agent for color survey creation
survey_creator_agent = Agent(
    name="color_survey_expert",
    traits={
        "expertise": "survey design and color psychology",
        "persona": textwrap.dedent("""
            You are an expert in survey design and color psychology. You understand how to craft
            engaging questions about color preferences that yield meaningful insights. You can
            adapt your questioning style to different contexts and audiences.
        """)
    }
)


# 3. Survey Generation Question
generate_survey_question = QuestionFreeText(
    question_name="color_survey_questions",
    question_text=textwrap.dedent("""
        Create {{ scenario.number_of_questions }} survey questions about favorite colors for this context: {{ scenario.survey_context }}.

        Use a {{ scenario.survey_style }} tone and style.

        Include a variety of question types such as:
        - Questions about favorite colors in general
        - Questions about color preferences for specific items/contexts
        - Questions about color associations or meanings
        - Questions about color combinations

        Format each question as a numbered list item with the question text.
        Make the questions engaging and relevant to the context provided.
    """)
)


# 4. Analysis Question
analyze_colors_question = QuestionFreeText(
    question_name="color_analysis",
    question_text=textwrap.dedent("""
        Based on the color survey questions you generated:
        {{ color_survey_questions.answer }}

        Provide insights about what these questions might reveal about color preferences in the context of: {{ scenario.survey_context }}

        Include:
        - What psychological aspects of color preference these questions explore
        - How the results might be useful for the given context
        - Any interesting patterns or themes in the color questions
    """)
)


# 5. Jobs Pipeline
color_survey_pipeline = Survey([
    generate_survey_question,
    analyze_colors_question
]).by(survey_creator_agent)


# 6. Output Formatters

# Markdown formatter for viewing the results
markdown_output = (
    OutputFormatter(description="Color Survey Results")
    .select("answer.color_survey_questions", "answer.color_analysis")
    .to_markdown()
    .view()
)

# Scenario list formatter for further processing
survey_data_output = (
    OutputFormatter(description="Survey Data")
    .select(
        "scenario.survey_context",
        "scenario.survey_style",
        "scenario.number_of_questions",
        "answer.color_survey_questions",
        "answer.color_analysis"
    )
    .to_scenario_list()
)

# Raw results formatter
raw_output = (
    OutputFormatter(description="Raw Results")
    .select("scenario.*", "answer.*")
    .table()
)


# 7. Complete App Instance
app = App(
    application_name="color_survey",
    description="Create a customized survey about favorite colors with insights and analysis",
    initial_survey=initial_survey,
    jobs_object=color_survey_pipeline,
    output_formatters={
        "markdown": markdown_output,
        "data": survey_data_output,
        "raw": raw_output,
    },
    default_formatter_name="markdown",
)


# 8. Test Example
if __name__ == "__main__":
    # Test the app with sample parameters
    print("Running Color Survey App...")

    results = app.output(
        params={
            "survey_context": "interior design preferences for a new home",
            "survey_style": "casual and fun",
            "number_of_questions": 5
        },
        verbose=True
    )

    print("\n" + "="*50)
    print("COLOR SURVEY APP RESULTS")
    print("="*50)
    print(results)