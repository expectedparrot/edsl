from edsl import Agent, AgentList, Survey, QuestionFreeText

a_alice = Agent(name="Alice", traits={'hometown': 'Boston', 'food': 'beans'})
a_bob = Agent(name="Bob", traits={'hometown': 'SF', 'food': 'sushi'})
al = AgentList([a_alice, a_bob])

q_to_traits = {'geo': 'hometown', 'cuisine': 'food'}

for agent in al:
    base = dict(agent.traits)  # snapshot static traits before setting dynamic function
    def f(question, base_traits=base, qmap=q_to_traits):
        key = qmap[question.question_name]
        return {key: base_traits[key]}
    agent.dynamic_traits_function = f

q1 = QuestionFreeText(question_name="geo", question_text="What is your hometown?")
q2 = QuestionFreeText(question_name="cuisine", question_text="What is your favorite food?")
survey = Survey([q1, q2])
print(survey.by(al).show_prompts())

