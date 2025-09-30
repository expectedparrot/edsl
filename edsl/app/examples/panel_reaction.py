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

output_formatter = OutputFormatter(name = "Panel Reaction").select('agent_name', 'answer.*').table()

app = App(
    initial_survey = initial_survey,
    jobs_object = jobs_object,
    description = "A panel reaction to a question about cheese.",
    application_name = "panel_reaction",
    output_formatters = [output_formatter]
    )

if __name__ == "__main__":
    output = app.output(params={
        'input_survey': QuestionFreeText(
            question_name = "cheese_reaction",
            question_text = "How do you feel about cheese?"
        ).to_survey()
    })
    print(output)