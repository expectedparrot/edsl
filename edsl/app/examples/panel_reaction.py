from edsl.app import App
from edsl.app import OutputFormatter

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionEDSLObject
from edsl.agents import Agent, AgentList

initial_survey = Survey([
    QuestionEDSLObject(
        question_name="input_survey",
        question_text="Provide the Survey to ask the panel",
        expected_object_type="Survey",
    )
])

al = AgentList([
    Agent(name = "cheese_hater", traits = {'persona': "You hate cheese."}),
    Agent(name = "cheese_lover", traits = {'persona': "You love cheese."})
    ])

# Minimal jobs survey; will be replaced by the provided survey via head attachment
jobs_object = Survey([]).to_jobs().by(al)

output_formatter = OutputFormatter(description="Panel Reaction", output_type="table").select('agent_name', 'answer.*').table()

app = App(
    application_name="panel_reaction",
    display_name="Panel Reaction",
    short_description="A panel reaction application.",
    long_description="This application collects reactions from a panel of agents with different perspectives. Users provide a survey, and the app runs it across multiple agents (like cheese lovers and cheese haters) to capture diverse viewpoints.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={"panel_reaction": output_formatter},
    default_formatter_name="panel_reaction",
)

if __name__ == "__main__":
    output = app.output(params={
        'input_survey': QuestionFreeText(
            question_name = "cheese_reaction",
            question_text = "How do you feel about cheese?"
        ).to_survey()
    })
    print(output)