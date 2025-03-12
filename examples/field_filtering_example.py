"""
Example demonstrating the new pandas-like filtering syntax with Field objects.

This example shows how to use the Field class to create more expressive and
type-safe filtering expressions for AgentList, ScenarioList, and Dataset objects.
"""

import random
from edsl import Agent, AgentList, Scenario, ScenarioList, Dataset
from edsl.utilities.query_utils import Field

# Create some test data
def create_test_agents(n=10):
    """Create a test AgentList with random data."""
    agents = []
    for i in range(n):
        agents.append(
            Agent(
                traits={
                    "age": random.randint(18, 65),
                    "income": random.randint(30000, 150000),
                    "name": random.choice(["Alice", "Bob", "Charlie", "David", "Emma"]),
                    "is_active": random.choice([True, False]),
                    "location": random.choice(["New York", "London", "Tokyo", "Paris", "Sydney"]),
                }
            )
        )
    return AgentList(agents)

# Create test data
agent_list = create_test_agents(20)
print("Original AgentList:")
for agent in agent_list[:3]:  # Just print a few for brevity
    print(f"  {agent.traits}")
print(f"  ... (total: {len(agent_list)} agents)")
print()

# Traditional string-based filtering
print("Using traditional string-based filtering:")
filtered_traditional = agent_list.filter("age > 30 and income > 100000")
print(f"Agents with age > 30 and income > 100000: {len(filtered_traditional)}")
for agent in filtered_traditional[:3]:  # Just print a few for brevity
    print(f"  {agent.traits}")
if len(filtered_traditional) > 3:
    print(f"  ... (total: {len(filtered_traditional)} agents)")
print()

# New Field-based filtering
print("Using new Field-based filtering:")
# Filter by age greater than 30 and income greater than 100000
filtered_field = agent_list.filter((Field('age') > 30) & (Field('income') > 100000))
print(f"Agents with age > 30 and income > 100000: {len(filtered_field)}")
for agent in filtered_field[:3]:  # Just print a few for brevity
    print(f"  {agent.traits}")
if len(filtered_field) > 3:
    print(f"  ... (total: {len(filtered_field)} agents)")
print()

# More complex Field-based filtering
print("More complex Field-based filtering examples:")

# Filter by name starting with 'A' or 'B'
name_filter = (Field('name').startswith('A') | Field('name').startswith('B'))
filtered_name = agent_list.filter(name_filter)
print(f"Agents with names starting with 'A' or 'B': {len(filtered_name)}")
for agent in filtered_name[:3]:
    print(f"  {agent.traits}")
if len(filtered_name) > 3:
    print(f"  ... (total: {len(filtered_name)} agents)")
print()

# Filter by location containing 'o'
location_filter = Field('location').contains('o')
filtered_location = agent_list.filter(location_filter)
print(f"Agents with 'o' in location: {len(filtered_location)}")
for agent in filtered_location[:3]:
    print(f"  {agent.traits}")
if len(filtered_location) > 3:
    print(f"  ... (total: {len(filtered_location)} agents)")
print()

# Filter by a complex condition
complex_filter = (
    (Field('age') > 25) & 
    (Field('income') > 50000) & 
    (Field('is_active') == True) & 
    (Field('location').contains('o') | Field('location').endswith('k'))
)
filtered_complex = agent_list.filter(complex_filter)
print(f"Agents matching complex filter: {len(filtered_complex)}")
for agent in filtered_complex[:3]:
    print(f"  {agent.traits}")
if len(filtered_complex) > 3:
    print(f"  ... (total: {len(filtered_complex)} agents)")
print()

# Convert to ScenarioList and filter
scenario_list = agent_list.to_scenario_list()
filtered_scenarios = scenario_list.filter(Field('age') < 25)
print(f"Scenarios with age < 25: {len(filtered_scenarios)}")
for scenario in filtered_scenarios[:3]:
    print(f"  {scenario}")
if len(filtered_scenarios) > 3:
    print(f"  ... (total: {len(filtered_scenarios)} scenarios)")
print()

# Convert to Dataset and filter
dataset = agent_list.to_dataset()
filtered_dataset = dataset.filter(Field('income') > 100000)
print(f"Dataset filtered to income > 100000")
print(filtered_dataset)