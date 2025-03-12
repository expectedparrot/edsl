from typing import Optional

from .. import Agent, AgentList, QuestionFreeText
from .. import Cache
from .. import QuestionList
from .. import Model

from .Conversation import Conversation, ConversationList

m = Model("gemini-1.5-flash")


class ChipLover(Agent):
    def __init__(self, name, chip_values, initial_chips, model: Optional[Model] = None):
        self.chip_values = chip_values
        self.initial_chips = initial_chips
        self.current_chips = initial_chips
        self.model = model or Model()
        super().__init__(
            name=name,
            traits={
                "motivation": f"""
            You are {name}. You are negotiating the trading of colored 'chips' with other players. You want to maximize your score.
            When you want to accept a deal, say "DEAL!" 
            Note that different players can have different values for the chips.
            """,
                "chip_values": chip_values,
                "initial_chips": initial_chips,
            },
        )

    def trade(self, chips_given_dict, chips_received_dict):
        for color, amount in chips_given_dict.items():
            self.current_chips[color] -= amount
        for color, amount in chips_received_dict.items():
            self.current_chips[color] += amount

    def get_score(self):
        return sum(
            self.chip_values[color] * self.current_chips[color]
            for color in self.chip_values
        )


a1 = ChipLover(
    name="Alice",
    chip_values={"Green": 7, "Blue": 1, "Red": 0},
    model=Model("gemini-1.5-flash"),
    initial_chips={"Green": 1, "Blue": 2, "Red": 3},
)
a2 = ChipLover(
    name="Bob",
    chip_values={"Green": 7, "Blue": 1, "Red": 0},
    initial_chips={"Green": 1, "Blue": 2, "Red": 3},
)

c1 = Conversation(agent_list=AgentList([a1, a2]), max_turns=10, verbose=True)
c2 = Conversation(agent_list=AgentList([a1, a2]), max_turns=10, verbose=True)

with Cache() as c:
    combo = ConversationList([c1, c2], cache=c)
    combo.run()
    results = combo.to_results()
    results.select("conversation_index", "index", "agent_name", "dialogue").print(
        format="rich"
    )

    q = QuestionFreeText(
        question_text="""This was a conversation/negotiation: {{ transcript }}. 
                        What trades occurred in the conversation?
                        """,
        question_name="trades",
    )

    q_actors = QuestionList(
        question_text="""Here is a transcript: {{ transcript }}. 
                        Who were the actors in the conversation?
                        """,
        question_name="actors",
    )

    from .. import QuestionList

    q_transfers = QuestionList(
        question_text="""This was a conversation/negotiation: {{ transcript }}. 
                        Extract all offers and their outcomes.
                        Use this format: {'proposing_agent':"Alice": 'receiving_agent': "Bob", 'gives':{"Green": 1, "Blue": 2}, 'receives':{"Green": 2, "Blue": 1}, 'accepted':True}
                        """,
        question_name="transfers",
    )

    transcript_analysis = (
        q.add_question(q_actors).add_question(q_transfers).by(combo.summarize()).run()
    )
    transcript_analysis.select("trades", "actors", "transfers").print(format="rich")
