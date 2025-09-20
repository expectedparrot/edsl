from edsl import Agent, AgentList, Scenario, QuestionList
from edsl import Agent, AgentList, QuestionList

# OK 
a = AgentList(Agent(traits = {"persona":p}) for p in ["botanist"])
q = QuestionList(
    question_name = "q",
    question_text = "Name some colors that another {{ agent.persona }} like you is likely to enjoy.",
)
job = q.by(a)
job.prompts().select("user_prompt")


# FAILS
a = AgentList(Agent(traits = {"persona":p}) for p in ["botanist"])
s = Scenario({"topic":"colors"})

q = QuestionList(
    question_name = "q",
    question_text = "Name some {{ scenario.topic }} that another {{ agent.persona }} like you is likely to enjoy.",
)

job = q.by(a).by(s)
job.prompts().select("user_prompt")