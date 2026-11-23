"""Define the neutral respondent used for repeated model interviews."""

from edsl import Agent, AgentList


# The original human experiments did not define demographic personas. A single
# empty-trait respondent is repeated with `n` to sample model response variation.
agent_list = AgentList([Agent(name="Respondent", traits={})])


if __name__ == "__main__":
    agent_list.git.save("agent_list.ep")
