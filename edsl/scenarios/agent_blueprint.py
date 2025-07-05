from .scenario_list import ScenarioList

class AgentBlueprint:

    def __init__(self, scenario_list: ScenarioList):
        for scenario in scenario_list:
            assert 'dimension' in scenario, "Scenario must have a dimension field"
            assert 'dimension_values' in scenario, "Scenario must have a dimension_values field"

        print("Passed in scenario list:")
        print(scenario_list)

        self.scenario_list = scenario_list

    def generate_agent(self):
        """This is a generator function that yields agents one at a time by randomly sampling a value from each dimension_values field"""
        from ..agents import Agent, AgentList
        import random
        while True:
            traits = {}
            for scenario in self.scenario_list:
                dimension = scenario['dimension']
                value = random.choice(scenario['dimension_values'][0])
                traits[dimension] = value
            
            if 'name' in traits:
                agent_name = traits.pop('name')
            else:
                agent_name = None
            yield Agent(traits, name = agent_name)

    def create_agent_list(self, n: int = 10):
        """Create a list of agents by randomly sampling a value from each dimension_values field"""
        from ..agents import Agent, AgentList
        generator = self.generate_agent()
        return AgentList([next(generator) for _ in range(n)])
