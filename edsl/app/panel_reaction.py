from .app import App 
from .output_formatter import OutputFormatter, OutputFormatters

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.agents import Agent, AgentList

initial_survey = None


al = AgentList([
    Agent(name = "cheese_hater", traits = {'persona': "You hate cheese."}),
    Agent(name = "cheese_lover", traits = {'persona': "You love cheese."})
    ])

# dummy survey which will be replaced by the survey in the app.output call
jobs_object = Survey.example().to_jobs().by(al)

output_formatter = OutputFormatter(name = "Panel Reaction").select('agent_name', 'answer.*').table()

a = App(
    initial_survey = initial_survey, 
    jobs_object = jobs_object, 
    application_type = "give_to_agents",
    output_formatters = OutputFormatters([output_formatter])
    )

if __name__ == "__main__":
    output = a.output(
        answers = QuestionFreeText(question_name = "cheese_reaction", 
        question_text = "How do you feel about cheese?").to_survey()
    )
    print(output)