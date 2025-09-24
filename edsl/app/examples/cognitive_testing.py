from edsl.app import SurveyInputApp 
from edsl.app import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText

jobs_object = Survey([QuestionFreeText(
    question_name = "typos", 
    question_text = "Are there any typos in {{ scenario.question_text }}?")]).to_jobs()

output_formatter = (
    OutputFormatter(name = "Typo Checker")
    .select('scenario.question_text', 'answer.typos')
    .table()
)

a = SurveyInputApp(
    initial_survey = None, 
    jobs_object = jobs_object, 
    application_name = "Typo Checker",
    description = "Check for typos in the question text",
    output_formatters = output_formatter)

if __name__ == "__main__":
    output = a.output(params = Survey.example())
    print(output)


