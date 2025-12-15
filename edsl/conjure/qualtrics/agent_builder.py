"""Agent builder for Qualtrics data."""

from typing import List, Dict, Any, Callable

from edsl.agents import Agent, AgentList


class QualtricsAgentBuilder:
    """Create EDSL agents from Qualtrics response records.

    Handles:
    - Creating agents with direct answering methods
    - Storing response data for survey replay
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the agent builder.

        Args:
            verbose: Print detailed processing information
        """
        self.verbose = verbose

    def build(self, response_records: List[Dict[str, Any]]) -> AgentList:
        """Build EDSL agents from response records.

        Args:
            response_records: List of response dictionaries, one per respondent

        Returns:
            An AgentList containing one agent per respondent
        """
        if self.verbose:
            print("Building EDSL agents...")

        agents = []
        for index, record in enumerate(response_records):
            agent = Agent()

            # Store actual responses as direct answering method
            agent.add_direct_question_answering_method(
                self._construct_answer_func(record)
            )
            agent.traits["_index"] = index
            agents.append(agent)

        if self.verbose:
            print(f"Created {len(agents)} agents")

        return AgentList(agents)

    @staticmethod
    def _construct_answer_func(record: dict) -> Callable:
        """Create an answer function that returns stored responses.

        Args:
            record: Dictionary of question_name -> answer

        Returns:
            A function suitable for add_direct_question_answering_method
        """

        def func(self, question, scenario=None):
            return record.get(question.question_name, None)

        return func
