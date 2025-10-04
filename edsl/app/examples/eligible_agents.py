from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.agents import AgentList, Agent
from edsl import QuestionYesNo
from edsl.surveys import Survey
from edsl.questions import QuestionEDSLObject

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
of = OutputFormatter(description="Eligible Agents", output_type="json").select('answer.eligible').to_list(

)
# Provide initial_survey so the agent list can be supplied as an EDSL object
initial_survey = Survey([
    QuestionEDSLObject(
        question_name="agent_list",
        question_text="Provide the AgentList to evaluate",
        expected_object_type="AgentList",
    )
])

app = App(
    initial_survey=initial_survey,
    jobs_object=jobs,
    application_name="Eligible Agents",
    description="This is a constructed agent. It is randomly collected from a population. Is the agent eligible to participate in the study?",
    output_formatters={"eligible_list": of},
    default_formatter_name="eligible_list",
)

if __name__ == "__main__":
    print(app.output(params = {'agent_list': al}))