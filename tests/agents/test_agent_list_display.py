from edsl import Agent, AgentList

# Create an agent with optional parameters like in the example
a = Agent(
    name="Robin",
    traits={"age": 46},
    instruction="Be honest.",
    traits_presentation_template="You are {{ name }}. You are {{ age }} years old.",
)

print("Single Agent Display:")
print(a)
print()

# Create an AgentList with the agent
al = AgentList([a])
print("AgentList Display (should show optional params):")
print(al)
print()

# Test with additional optional parameters
a2 = Agent(
    name="Taylor",
    traits={"age": 30, "occupation": "engineer"},
    instruction="Be helpful and concise.",
    traits_presentation_template="I am {{ name }}, a {{ age }}-year-old {{ occupation }}.",
    codebook={"age": "Age in years", "occupation": "Profession"},
)

al2 = AgentList([a, a2])
print("AgentList with Multiple Agents and Various Optional Params:")
print(al2)
