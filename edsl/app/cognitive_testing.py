from .app import SurveyInputApp 
from .output_formatter import OutputFormatter, OutputFormatters

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
initial_survey = None

jobs_object = Survey([QuestionFreeText(
    question_name = "typos", 
    question_text = "Are there any typos in {{ scenario.question_text }}?")]).to_jobs()

output_formatter = OutputFormatter(name = "Typo Checker").select('scenario.question_text', 'answer.typos').table()

a = SurveyInputApp(
    initial_survey = initial_survey, 
    jobs_object = jobs_object, 
    output_formatters = OutputFormatters([output_formatter])
    )

if __name__ == "__main__":
    output = a.output(params = Survey.example())
    print(output)


