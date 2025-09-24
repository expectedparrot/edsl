from edsl.app.app import DataLabelingApp 
from edsl.app import OutputFormatter

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.agents import Agent, AgentList

from edsl.scenarios.handlers.xlsx_file_store import XlsxMethods


from edsl.questions import QuestionYesNo

labeling_question = QuestionYesNo(
    question_name = "in_asia", 
    question_text = "Is this city in Asia? {{ scenario.City }}")

from edsl.jobs import Jobs

of = OutputFormatter(name = "Data Labeling").select('City','answer.*', 'generated_tokens.*').table()

app = DataLabelingApp(
    initial_survey = None, 
    description = "A data labeling app.",
    application_name = "data_labeling",
    jobs_object = Survey.example().to_jobs(),
    output_formatters = [of]
    )

if __name__ == "__main__":
    from edsl import FileStore
    example_fs = FileStore(path = XlsxMethods().example())
    output = app.output(params = {'labeling_question': labeling_question, 'file_path': example_fs.path})
    print(output)