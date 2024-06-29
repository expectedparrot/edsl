import asyncio
from typing import Optional, Callable
from edsl import Agent, QuestionFreeText, Results, AgentList, ScenarioList, Scenario
from edsl.questions import QuestionBase
from edsl.results.Result import Result


class Conversation:
    """A conversation between a list of agents. The first agent in the list is the first speaker.
    After that, order is determined by the next_speaker function.
    The question asked to each agent is determined by the next_statement_question.
    """

    def __init__(
        self,
        agent_list: AgentList,
        max_turns: int = 10,
        next_statement_question: Optional[QuestionBase] = None,
        next_speaker: Optional[Callable] = None,
        verbose: bool = False,
        conversation_index: Optional[int] = None
    ):

        self.agent_list = agent_list
        self.max_turns = max_turns
        self.verbose = verbose
        self.results_data = []
        self._conversation_index = conversation_index

        if next_statement_question is None:
            self.next_statement_question = QuestionFreeText(
                question_text="You are {{ agent_name }}. This is the converstaion so far: {{ conversation }}. What do you say next?",
                question_name="dialogue",
            )

        if next_speaker is None:

            def turn_taking(i, agent_list):
                return agent_list[i % len(agent_list)]

            self.next_speaker = turn_taking

    def add_index(self, index):
        self._conversation_index = index

    @property
    def conversation_index(self):
        return self._conversation_index
    
    def to_dict(self):
        return {
            "agent_list": self.agent_list.to_dict(),
            "max_turns": self.max_turns,
            "verbose": self.verbose,
            "results_data": [d.to_dict() for d in self.results_data],
            "conversation_index": self.conversation_index        
            }
    
    @classmethod
    def from_dict(cls, data):
        agent_list = AgentList.from_dict(data["agent_list"])
        max_turns = data["max_turns"]
        verbose = data["verbose"]
        results_data = [Result.from_dict(d) for d in data["results_data"]]
        conversation_index = data["conversation_index"]
        return cls(
            agent_list=agent_list,
            max_turns=max_turns,
            verbose=verbose,
            results_data=results_data,
            conversation_index=conversation_index
        )
    
    def to_results(self):
        return Results(data=self.results_data)

    def summarize(self):
        d =  {
            'num_agents': len(self.agent_list),
            'max_turns': self.max_turns,
            'conversation_index': self.conversation_index,
            'transcript': self.to_results().select("agent_name", "dialogue").to_list(),
            "number_of_utterances": len(self.results_data)
        }
        return Scenario(d)

    async def get_next_statement(self, i, agent_name, conversation, speaker):
        return await self.next_statement_question.run_async(
            index=i,
            agent_name=agent_name,
            conversation=conversation,
            conversation_index=self.conversation_index,
            agent=speaker,
            just_answer=False)
    
    def converse(self):
        return asyncio.run(self._converse())

    async def _converse(self):
        conversation = []
        previous_speaker = None
        for i in range(self.max_turns):
            speaker = self.next_speaker(i, self.agent_list)
            agent_name = speaker.name

            next_statement_results = await self.get_next_statement(i, agent_name, conversation, speaker)

            next_statement = next_statement_results.select("dialogue").first()
            conversation.append(f"{agent_name} said '{next_statement}'")
            if self.verbose:
                print(f"{agent_name} said {next_statement}")
            self.results_data.append(next_statement_results[0])
            previous_speaker = speaker


#from edsl import Conversation

a1 = Agent(
    name="Alice",
    traits={
        "motivation": """
    You are Alice. You want to buy a car. You are talking to Bob, a car salesman.
    It is very important to you that the steering wheel not whiff out of the window while you are driving.
    Also, car can have no space for mother-in-law.
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
a3 = Agent(name = "Paul",traits = {
    "motivation": 
    "You are Paul, you are Alice's brother. You think her concerns are foolish and you are critical of her."}
    )


class Conversations:

    def __init__(self, conversations):
        self.conversations = conversations
        for i, conversation in enumerate(self.conversations):
            conversation.add_index(i)

    async def run_conversations(self):
       await asyncio.gather(*[c._converse() for c in self.conversations])

    def to_dict(self):
        return {
            'conversations': c.to_dict() for c in self.conversations
            }

    @classmethod
    def from_dict(cls, data):
        conversations = [Conversation.from_dict(d) for d in data["conversations"]]
        return cls(conversations)

    def run(self):
        asyncio.run(self.run_conversations())

    def to_results(self) -> Results:
        first_convo = self.conversations[0]
        results = first_convo.to_results()
        for conv in self.conversations[1:]:
            results += conv.to_results()
        return results
    
    def summarize(self):
        return ScenarioList([c.summarize() for c in self.conversations])


c1 = Conversation(agent_list=AgentList([a1, a3, a2]), max_turns=3, verbose=False)
c2 = Conversation(agent_list=AgentList([a1, a2]), max_turns=5, verbose=False)

combo = Conversations([c1, c2])
combo.run()
results = combo.to_results()
results.select("conversation_index", "index", "agent_name", "dialogue").print(format="rich")


q = QuestionFreeText(question_text = """This was a conversation about buying a car: {{ transcript }}. 
                     Was a brand or style of car mentioned? If so, what was it?
                     """, 
                     question_name = "car_brand")

from edsl import QuestionList

q_actors = QuestionList(question_text = """This was a conversation about buying a car: {{ transcript }}. 
                     Who were the actors in the conversation?
                     """, 
                     question_name = "actors")

transcript_analysis = q.add_question(q_actors).by(combo.summarize()).run()
transcript_analysis.select("car_brand", "actors").print(format="rich")