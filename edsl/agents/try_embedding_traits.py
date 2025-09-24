from edsl import Agent 


def f(self, question): 
    if question.question_name == "q1":
        return {"trait1": "value1", "trait2": "value2"}
    else:
        return {"trait1": "value3", "trait2": "value4"}

agent = Agent(traits={"trait1": "value1", "trait2": "value2"})
agent.traits_manager.initialize_dynamic_function(f)
print(agent.traits)