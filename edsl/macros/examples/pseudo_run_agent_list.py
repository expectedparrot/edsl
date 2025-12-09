"""Demo macro showing the pseudo_run feature with agent sampling.

This macro demonstrates how to use pseudo_run to create a Results object
with a survey, scenarios, and agent_list attached without running actual interviews.
The user specifies how many agents to sample from the full list of 10 agents.
"""

from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.agents import AgentList, Agent
from edsl import QuestionFreeText
from edsl.surveys import Survey
from edsl.questions import QuestionNumerical


# Create an agent list with 10 agents with different traits
agent_list = AgentList(
    [
        Agent(name="Alice", traits={"age": 25, "role": "Engineer"}),
        Agent(name="Bob", traits={"age": 30, "role": "Designer"}),
        Agent(name="Carol", traits={"age": 35, "role": "Manager"}),
        Agent(name="David", traits={"age": 28, "role": "Developer"}),
        Agent(name="Eve", traits={"age": 32, "role": "Analyst"}),
        Agent(name="Frank", traits={"age": 27, "role": "Researcher"}),
        Agent(name="Grace", traits={"age": 29, "role": "Consultant"}),
        Agent(name="Henry", traits={"age": 31, "role": "Architect"}),
        Agent(name="Iris", traits={"age": 26, "role": "Scientist"}),
        Agent(name="Jack", traits={"age": 33, "role": "Director"}),
    ]
)

# Create a simple survey question that references scenario fields
# This is required to pass the scenario compatibility check
q = QuestionFreeText(
    question_name="sample_question",
    question_text="This is a sample question for {{ scenario.num_agents }} agents with minimum age {{ scenario.min_age }}.",
)

# Create jobs object with the agent list
jobs = q.to_jobs().by(agent_list)

# Initial survey to collect the number of agents to sample
initial_survey = Survey(
    [
        QuestionNumerical(
            question_name="num_agents",
            question_text="How many agents would you like to sample from the list of 10?",
            min_value=1,
            max_value=10,
        ),
        QuestionNumerical(
            question_name="min_age",
            question_text="What is the minimum age of the agents you would like to sample? ",
        ),
    ]
)


# Create an output formatter that extracts agents and samples them
# The {{ params.num_agents }} template will be replaced with the integer value from initial_survey
# Note: params are nested under "params" key when passed to formatter
agent_formatter = (
    OutputFormatter(description="Sampled Agents", output_type="AgentList")
    .agents()
    .sample("{{ params.num_agents }}")
    .filter("age > {{ params.min_age }}")
)

# Create the macro with pseudo_run=True
macro = Macro(
    application_name="pseudo_run_agent_list2",
    display_name="Pseudo Run Agent List Demo2",
    short_description="Demo of pseudo_run feature with agent sampling.",
    long_description="This macro demonstrates how to use the pseudo_run feature to create a Results object with a survey and agent_list attached (but without running actual interviews). The user specifies how many agents to sample from the full list of 10 agents.",
    initial_survey=initial_survey,
    jobs_object=jobs,
    default_params={"min_age": 25},
    output_formatters={"agents": agent_formatter},
    default_formatter_name="agents",
    pseudo_run=True,  # This is the key parameter that enables pseudo_run
)


if __name__ == "__main__":
    # Example: Sample 5 agents from the list with default min_age (25)
    print("=" * 60)
    print("Demo: Sampling 5 agents with age > 25")
    print("=" * 60)

    # Run the macro with num_agents parameter
    # The formatter will automatically extract agents, sample, and filter by age
    result = macro.output(params={"num_agents": 5})
    sampled_agents = result.agents

    print(f"Sampled {len(sampled_agents)} agents:")
    for agent in sampled_agents:
        print(f"  - {agent.name}: {agent.traits}")
    print("=" * 60)

    # Example: Sample agents with custom min_age
    print("\nDemo: Sampling 10 agents with age > 30")
    print("=" * 60)
    result = macro.output(params={"num_agents": 10, "min_age": 30})
    filtered_agents = result.agents

    print(f"Sampled {len(filtered_agents)} agents:")
    for agent in filtered_agents:
        print(f"  - {agent.name}: {agent.traits}")
    print("=" * 60)
