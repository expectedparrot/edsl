from edsl.app.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.agents import AgentList, Agent
from edsl import QuestionYesNo

al = AgentList([
    Agent(traits = {'age':12, 'employment_status':'Retired'}),
    Agent(traits = {'age':27, 'employment_status':'Employed'})
])

q = QuestionYesNo(
    question_name = "eligible", 
    question_text = """This is a constructed agent. 
It is randomly collected from a population.
Is the agent eligible to participate in the study?""")

jobs = q.to_jobs()
of = OutputFormatter(name="Eligible Agents").select('answer.eligible').to_list(

)
app = App(jobs_object = jobs, 
    application_name = "Eligible Agents",
    description = "This is a constructed agent. It is randomly collected from a population. Is the agent eligible to participate in the study?",
    output_formatters = [of]
    )

if __name__ == "__main__":
    print(app.output(params = {'agent_list': al}))