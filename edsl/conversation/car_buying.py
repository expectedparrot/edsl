from .. import Agent, AgentList, QuestionFreeText, Cache, QuestionList
from .Conversation import Conversation, ConversationList

a1 = Agent(
    name="Alice",
    traits={
        "motivation": """
    You are Alice. You want to buy a car. You are talking to Bob, a car salesman.
    It is very important to you that the steering wheel not whiff out of the window while you are driving.
    Also, the car can have no space for mother-in-law.
    You brought your brother-in-law along, Paul, who you have an antagonistic relationship with.
    """
    },
)
a2 = Agent(
    name="Bob",
    traits={
        "motivation": "You are Bob, a car salesman. You are talking to Alice, who wants to buy a car."
    },
)
a3 = Agent(
    name="Paul",
    traits={
        "motivation": "You are Paul, you are Alice's brother. You think her concerns are foolish and you are critical of her."
    },
)

c1 = Conversation(agent_list=AgentList([a1, a3, a2]), max_turns=5, verbose=True)
c2 = Conversation(agent_list=AgentList([a1, a2]), max_turns=5, verbose=True)

# c = Cache.load("car_talk.json.gz")
c = Cache()
# breakpoint()
combo = ConversationList([c1, c2], cache=c)
combo.run()
results = combo.to_results()
results.select("conversation_index", "index", "agent_name", "dialogue").print(
    format="rich"
)

q = QuestionFreeText(
    question_text="""This was a conversation about buying a car: {{ transcript }}. 
                    Was a brand or style of car mentioned? If so, what was it?
                    """,
    question_name="car_brand",
)


q_actors = QuestionList(
    question_text="""This was a conversation about buying a car: {{ transcript }}. 
                    Who were the actors in the conversation?
                    """,
    question_name="actors",
)

transcript_analysis = q.add_question(q_actors).by(combo.summarize()).run()
transcript_analysis.select("car_brand", "actors").print(format="rich")
