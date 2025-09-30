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
    OutputFormatter(name = "Typo Checker")
    .select('scenario.question_text', 'answer.typos')
    .table()
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
    initial_survey = initial_survey, 
    jobs_object = jobs_object, 
    application_name = "Typo Checker",
    description = "Check for typos in the question text",
    output_formatters = output_formatter,
    attachment_formatters = [
        # Convert the provided Survey into scenarios at the head
        SurveyAttachmentFormatter(name="Survey->ScenarioList").to_scenario_list()
    ]
)

if __name__ == "__main__":
    output = app.output(params = {
        'input_survey': Survey.example()
    })
    print(output)


