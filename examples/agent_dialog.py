from textwrap import dedent
from itertools import cycle

from edsl.data import Cache
from edsl import Agent, Scenario, Survey
from edsl.questions import QuestionFreeText, QuestionYesNo

c = Cache()

MAX_TURNS = 20

q_yn = QuestionYesNo(question_text = dedent("""\
    You are {{ agent_name }}. 
    You are talking to {{ other_agent_name }}.
    The transcript so far is: 
    {{ transcript }}
    It is your turn to speak.
    Do you want to say anything at all or is the conversation over?                   
    If the transcript is empty, you can make the first statement.                      
    """), 
    question_name = "should_continue")

q_response = QuestionFreeText(question_text = dedent("""\
    It is your turn to speak.
    """), 
    question_name = "response"
)
survey = Survey([q_yn, q_response]).add_stop_rule("should_continue", "should_continue == 'No'")
survey.add_targeted_memory('response', 'should_continue')

agents = [
    Agent(name = "John", instruction = "You really want to go hiking and will not go biking."),
    Agent(name = "Robin", instruction = "You really want to go biking but will go hiking as a compromise.")
]

num_turns = 0 
transcript = []
for index in cycle([0,1]):
    agent1, agent2 = agents[index], agents[(index+1)%2]
    s = Scenario({'agent_name': agent1.name, 
                  'other_agent_name': agent2.name, 
                  'transcript': transcript}) 
    results = survey.by(agent1).by(s).run(cache = c)
    response = results.select('response').first()
    if response is None:
        print(f"{agent1.name} has ended the conversation.")
        break       
    print(f"{agent1.name}: {response}")
    transcript.append({agent1.name: response})
    num_turns += 1
    if num_turns >= MAX_TURNS:
        break


c.write_jsonl("conversation_cache.jsonl")