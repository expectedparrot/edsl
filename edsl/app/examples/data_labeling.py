from edsl.app import App 
from edsl.app import OutputFormatter

from edsl.surveys import Survey
from edsl.questions import QuestionEDSLObject

from edsl.scenarios.handlers.xlsx_file_store import XlsxMethods


from edsl.questions import QuestionYesNo

labeling_question = QuestionYesNo(
    question_name = "in_asia", 
    question_text = "Is this city in Asia? {{ scenario.City }}")

of = OutputFormatter(description = "Data Labeling").select('City','answer.*', 'generated_tokens.*').table()

# initial_survey collects the items to label and the labeling survey
initial_survey = Survey([
    QuestionEDSLObject(
        question_name="input_items",
        question_text="Provide the items to label as a ScenarioList",
        expected_object_type="ScenarioList",
    ),
    QuestionEDSLObject(
        question_name="labeling_survey",
        question_text="Provide the labeling Survey",
        expected_object_type="Survey",
    ),
])

# Minimal jobs object; survey and scenarios come from initial_survey answers
jobs_object = Survey([]).to_jobs()

app = App(
    initial_survey = initial_survey, 
    description = "A data labeling app.",
    application_name = "data_labeling",
    jobs_object = jobs_object,
    output_formatters = {"labeling": of},
    default_formatter_name = "labeling"
    )

if __name__ == "__main__":
    from edsl import FileStore
    example_fs = FileStore(path = XlsxMethods().example())
    sl = example_fs.to_scenario_list()
    output = app.output(params = {
        'input_items': sl,
        'labeling_survey': labeling_question.to_survey(),
    })
    print(output)