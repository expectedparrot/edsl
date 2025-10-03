from edsl.app import App
from edsl.app.output_formatter import OutputFormatter, ObjectFormatter, ScenarioAttachmentFormatter
from edsl.questions import QuestionFreeText, QuestionList
from edsl.surveys import Survey
from edsl import Scenario, ScenarioList

# Default modification instructions
DEFAULT_MODIFICATIONS = [
    "Make it more detailed",
    "Make it more concise",
    "Make it edgier",
    "Make it more futuristic",
    "Make it more formal",
    "Make it more casual",
    "Make it more technical",
    "Make it more accessible to beginners",
    "Make it funnier",
    "Make it more poetic",
    "Make it more dramatic",
    "Make it more serious",
    "Make it more lighthearted",
    "Make it more philosophical",
    "Make it more technical",
    "Make if more dollars-and-cents",
    "Make it more inspirational",
    "Make it more motivational",
    "Make it more informative",
    "Make it more persuasive",
    "Make it more engaging",
    "Make it more interesting",
]

initial_survey = Survey([
    QuestionFreeText(
        question_name="original_text",
        question_text="What is the text you want to create variants of?",
    ),
    QuestionList(
        question_name="modifications",
        question_text="What modification instructions do you want to apply? (Leave empty to use default set)",
    ),
])

q_variant = QuestionFreeText(
    question_name="variant_text",
    question_text="""Take this original text:
<original>
{{ scenario.original_text }}
</original>

Apply this modification instruction: {{ scenario.modifications }}

Return only the modified text, no other commentary.""",
)

# Build the jobs pipeline
jobs_object = q_variant.by(Scenario.example())


# Output formatter to create scenario list with variants
output_formatter = (
    OutputFormatter(description="Variant List")
    .select("scenario.modifications", "answer.variant_text")
    .to_scenario_list()
)

from edsl.scenarios import ScenarioList, Scenario 


attachment_formatter = (
    ScenarioAttachmentFormatter()
    .replace_value('modifications', DEFAULT_MODIFICATIONS)
    .to_scenario_list()
    .expand('modifications')
)

app = App(
    description="Create multiple variants of a text based on modification instructions.",
    application_name="variant_creator",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={"variant_list": output_formatter},
    default_formatter_name="variant_list",
    attachment_formatters=[attachment_formatter],
)

if __name__ == "__main__":
    # Example with custom modifications
    output = app.output(params={
        'original_text': 'Expected Parrot is making Open Source tools for AI Simulation.',
        'modifications': [],
    })
    print(output.table())

    # Example with default modifications
    # output = app.output(params={
    #     'original_text': 'The quick brown fox jumps over the lazy dog.',
    #     'modifications': [],
    # })
    # print(output)