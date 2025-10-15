from edsl.macros import Macro
from edsl.macros import OutputFormatter

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionEDSLObject
from edsl.agents import Agent, AgentList

initial_survey = Survey([
    QuestionEDSLObject(
        question_name="agent_list",
        question_text="Provide the agent list to ask the panel",
        expected_object_type="AgentList",
    ), 
    QuestionFreeText(
        question_name="new_trait_field",
        question_text="What new trait field do you want to add to the agent list (python identifier)?",
    ),
    QuestionFreeText(
        question_name="new_trait_value",
        question_text="What question/instruction to you want to give to the agent to create the new trait field?",
    )
])

q_new_value = QuestionFreeText(
    question_name="new_persona_field",
    question_text="You are being asekd, based on your current traits, to write this about yourself: {{ scenario.new_trait_value }}",
)

jobs_object = Survey([q_new_value]).to_jobs()

agent_list = (OutputFormatter(description="Panel Reaction", output_type="edsl_object")
.then('augment_agents', field_name='new_persona_field', new_field_name='{{params.new_trait_field}}')
)

agent_list_markdown_table = (agent_list.copy().set_output_type("markdown").table(tablefmt = "github").to_string())

agent_list_table = (agent_list.copy().set_output_type("table").table())

macro = Macro(
    application_name="enrich_agent_list",
    display_name="Enrich Agent List",
    short_description="Enrich an agent list with a new trait field.",
    long_description="""
    This application collects reactions from a panel of agents with different perspectives.
    Users provide a survey, and the macro runs it across multiple agents (like cheese lovers and cheese haters)
    to capture diverse viewpoints.""",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={"agent_list": agent_list, "agent_list_table": agent_list_table, "agent_list_markdown_table": agent_list_markdown_table},
    default_formatter_name="agent_list",
)

if __name__ == "__main__":
    al = AgentList([
        Agent(name = "cheese_hater", traits = {'persona': "You hate cheese."}),
        Agent(name = "cheese_lover", traits = {'persona': "You love cheese."})
    ])
    output = macro.output(params={'agent_list': al,
    'new_trait_field': 'persona',
    'new_trait_value': "Tell me about your most favorite meal"}
    )