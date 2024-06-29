import asyncio
from typing import Optional, Callable
from edsl import Agent, QuestionFreeText, Results, AgentList
from edsl.questions import QuestionBase


class Conversation:

    def __init__(
        self,
        agent_list: AgentList,
        max_turns: int = 10,
        next_statement_question: Optional[QuestionBase] = None,
        next_speaker: Optional[Callable] = None,
        verbose: bool = False,
    ):

        self.agent_list = agent_list
        self.max_turns = max_turns
        self.verbose = verbose
        self.results_data = []

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

    def to_results(self):
        return Results(data=self.results_data)
    
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

    def run(self):
        asyncio.run(self.run_conversations())
        #return asyncio.run(self._run())

    def to_results(self) -> Results:
        first_convo = self.conversations[0]
        results = first_convo.to_results()
        for conv in self.conversations[1:]:
            results += conv.to_results()
        return results


c1 = Conversation(agent_list=AgentList([a1, a3, a2]), max_turns=3, verbose=False)
c2 = Conversation(agent_list=AgentList([a1, a3, a2]), max_turns=3, verbose=False)

combo = Conversations([c1, c2])
combo.run()
results = combo.to_results()
results.select("conversation_index", "index", "agent_name", "dialogue").print(format="rich")
#asyncio.run([c1._converse(), c2._converse()])
#c.converse()
#c.to_results().select("agent_name", "index", "dialogue").print(format="rich")
#asyncio.run(run_conversations())

#combo = c1.to_results() + c2.to_results()