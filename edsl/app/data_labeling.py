from .app import DataLabelingApp 
from .output_formatter import OutputFormatter, OutputFormatters

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.agents import Agent, AgentList


from edsl.scenarios.handlers.xlsx_file_store import XlsxMethods

from edsl import FileStore
example_fs = FileStore(path = XlsxMethods().example())

from edsl.questions import QuestionYesNo

labeling_question = QuestionYesNo(
    question_name = "in_asia", 
    question_text = "Is this city in Asia? {{ scenario.City }}")

from edsl.jobs import Jobs

app = DataLabelingApp(
    initial_survey = None, 
    jobs_object = Jobs.example(),
    output_formatters = OutputFormatters([OutputFormatter(name = "Data Labeling").select('City','answer.*').table()])
    )

if __name__ == "__main__":
    output = app.output(params = {'labeling_question': labeling_question, 'file_path': example_fs.path})
    print(output)