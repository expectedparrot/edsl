from .. import Agent, AgentList, QuestionYesNo, QuestionNumerical
from .Conversation import Conversation, ConversationList


def bargaining_pairs(alice_valuation, bob_valuation):
    a1 = Agent(
        name="Alice",
        traits={
            "motivation": f"""
        You are trying to sell your mug to Bob. You value the mug at ${ alice_valuation }---you would rather have the mug than ${alice_valuation}.
        But you are willing to sell it for ${alice_valuation} or more if Bob is willing to pay that much.
        You WILL NOT sell for less than ${alice_valuation}.
        You want to get as much money as possible for the mug.
        You are an experienced negotiator are strategic in your approach.
        """
        },
    )
    a2 = Agent(
        name="Bob",
        traits={
            "motivation": f"""You are Bob. You are trying to buy a mug from Alice. You value the mug at ${bob_valuation}. You would rather have the mug than ${bob_valuation}.
            But you want to pay as little as possible for the mug.
            You absolutely WILL NOT pay more than ${bob_valuation}.
            Carefully consider your valuation before making or accepting an offer.
            You are an experienced negotiator and are strategic in your approach.
            """
        },
    )
    return AgentList([a1, a2])


valuations = [(10, 15), (10, 100), (10, 9)]
cl = ConversationList(
    [
        Conversation(agent_list=bargaining_pairs(*v), max_turns=10, verbose=True)
        for v in valuations
    ]
)
cl.run()
results = cl.to_results()

results.select("conversation_index", "index", "agent_name", "dialogue").print(
    format="rich"
)


q_deal = QuestionYesNo(
    question_text="""This was a negotiation: {{ transcript }}. 
                     Was a deal reached?
                    """,
    question_name="deal",
)

q_price = QuestionNumerical(
    question_text="""This was a negotiation: {{ transcript }}.
    A deal was reached. What was the price of the deal?
    """,
    question_name="price",
)

q_side_deal = QuestionYesNo(
    question_text="""This was a negotiation: {{ transcript }}.
    Was there a side deal? I.e., seller agreed to other terms in exchange for a higher price?
    """,
    question_name="side_deal",
)

survey = (
    q_deal.add_question(q_price)
    .add_question(q_side_deal)
    .add_stop_rule("deal", "deal == 'No'")
)

transcript_analysis = survey.by(cl.summarize()).run()
transcript_analysis.select("deal", "price", "side_deal").print(format="rich")
