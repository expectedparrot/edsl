from edsl.app import App 
from edsl.app.output_formatter import OutputFormatter, SurveyAttachmentFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionEDSLObject

jobs_object = Survey([
    QuestionFreeText(
        question_name = "typos", 
        question_text = "Are there any typos in {{ scenario.question_text }}?"
    )
]).to_jobs()

output_formatter = (
    OutputFormatter(description = "Typo Checker", output_type="markdown")
    .select('scenario.question_text', 'answer.typos')
    .table(tablefmt = "github")
    .to_string()
)

# Initial survey: accept a Survey as input to turn into scenarios
initial_survey = Survey([
    QuestionEDSLObject(
        question_name="input_survey",
        question_text="Provide the Survey whose questions should be typo-checked",
        expected_object_type="Survey",
    )
])

app = App(
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    application_name={
        "name": "Cognitive Testing (Typo Checker)",
        "alias": "cognitive_testing"
    },
    description={
        "short": "Check for typos in survey question text.",
        "long": "This application performs cognitive testing on survey questions by checking for typos and language issues. It analyzes each question in a provided survey and identifies potential typos or grammatical errors that could affect respondent comprehension."
    },
    output_formatters={'table': output_formatter},
    default_formatter_name='table',
    attachment_formatters=[
        # Convert the provided Survey into scenarios at the head
        SurveyAttachmentFormatter(name="Survey->ScenarioList").to_scenario_list()
    ]
)

if __name__ == "__main__":
    output = app.output(params = {
        'input_survey': Survey.example()
    })
    #print(output)

    info = app.deploy(owner="johnhorton")
    print(info)


