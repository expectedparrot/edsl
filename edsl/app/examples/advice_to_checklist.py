import textwrap

from edsl.app import App
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText, QuestionYesNo
from edsl.app import OutputFormatter
from edsl import Scenario

initial_survey = Survey([
    QuestionFreeText(
        question_name="advice_text",
        question_text="What advice would you like to convert into a checklist?",
    ),
    QuestionYesNo(
        question_name="include_moustache",
        question_text="Append {{ scenario.item }} to each checklist question?",
        question_options=["No", "Yes"],
    ),
])

# Generate checklist items from the advice
checklist_question = QuestionList(
    question_name="checklist_items",
    question_text=textwrap.dedent(
        """
        You are converting the following advice into a checklist: {{ scenario.advice_text }}.

        Please break down this advice into specific, actionable checklist items.
        Each item should be something that can be answered with yes or no.
        Make each item clear, specific, and verifiable.

        For example, if the advice is "Make sure your code is well-tested and documented",
        the checklist items could be:
        - Does the code have unit tests
        - Does the code have integration tests
        - Does the code have inline comments explaining complex logic
        - Does the code have README documentation

        Return a list of checklist items (just the items, no yes/no).
        """
    ),
)

s = Scenario({"advice_text": "Make sure your website is accessible"})
jobs_object = (
    Survey([checklist_question]).by(s)
)

checklist_formatter = (OutputFormatter(description="Checklist Survey", output_type="edsl_object")
    .select('scenario.advice_text', 'answer.checklist_items')
    .expand('answer.checklist_items')
    .select('answer.checklist_items')
    .rename({'answer.checklist_items': 'question_text'})
    .to_scenario_list()
    .when("{{ params.include_moustache }}").then()
        .string_cat("question_text", ": {{ scenario.item }}")
    .end()
    .add_value('question_type', 'yes_no')
).to_survey()

# Markdown formatter that displays the survey as a table
markdown_formatter = (
    OutputFormatter(description="Checklist Preview (Markdown)", output_type="markdown")
    .select('scenario.advice_text', 'answer.checklist_items')
    .expand('answer.checklist_items')
    .select('answer.checklist_items')
    .rename({'answer.checklist_items': 'question_text'})
    .to_scenario_list()
    .when("{{ params.include_moustache }}").then()
        .string_cat("question_text", ": {{ scenario.item }}")
    .end()
    .add_value('question_type', 'yes_no')
    .table(tablefmt="github")
    .to_string()
)

app = App(
    initial_survey=initial_survey,
    description=textwrap.dedent("""
    An advice-to-checklist converter.

    This app takes a block of textual advice and converts it into a checklist of yes/no questions.
    Each question can be applied to a specific item by using {{ scenario.item }} in the question text.

    For example, if you provide advice like "Make sure your code is well-tested", it will generate questions like:
    - Does the code have unit tests: {{ scenario.item }}
    - Does the code have integration tests: {{ scenario.item }}

    This allows you to apply the same checklist to multiple items by creating scenarios with different values for 'item'.
    """),
    application_name="advice_to_checklist",
    jobs_object=jobs_object,
    output_formatters={"checklist": checklist_formatter, "markdown": markdown_formatter},
    default_formatter_name="checklist",
    default_params={"include_moustache": "No"},
)


if __name__ == "__main__":
    checklist_survey = app.output({'advice_text': "Make sure your API is secure and well-documented", 
                                   "include_moustache": "Yes"})
    print(checklist_survey.table())