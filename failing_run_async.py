import asyncio
from edsl.questions import QuestionFunctional
from edsl.surveys import Survey

def f(scenario, agent_traits): 
    return "yes" if scenario["period"] == "morning" else "no"

from edsl import Scenario 
scenario = Scenario({'period': 'morning'})
print(f(scenario, {}))


q = QuestionFunctional(question_name="q0", func=f)
from edsl import Model 
m = Model("test")

s = Survey([q])

async def test_run_async(): 
    result = await s.run_async(period="morning", disable_remote_inference = True)
    print(result.select("answer.q0").first())

asyncio.run(test_run_async())

