from collections import UserDict
from typing import List, Set, Generator, Tuple
import random

from .evaluations import Evaluation, Responses


class AgentResponseMap(UserDict):
    """A mapping of agent names to their responses to questions.

    This class extends UserDict to provide specialized methods for handling
    agent responses, including shuffling, generating random responses, and
    finding modal responses.

    Attributes:
        data (dict): The underlying dictionary mapping agent names to responses.

    Examples:
        >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No', 'Charlie': 'Yes'})
        >>> arm.agent_names
        ['Alice', 'Bob', 'Charlie']
        >>> arm.answers
        ['Yes', 'No', 'Yes']
        >>> len(arm.modal().answers) == 3
        True
    """

    @property
    def agent_names(self) -> List[str]:
        """Get a list of all agent names.

        Returns:
            List[str]: A list containing all agent names as keys.

        Examples:
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No'})
            >>> arm.agent_names
            ['Alice', 'Bob']
        """
        return list(self.keys())

    @property
    def answers(self) -> List[str]:
        """Get a list of all answers.

        Returns:
            List[str]: A list containing all agent responses as values.

        Examples:
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No'})
            >>> arm.answers
            ['Yes', 'No']
        """
        return list(self.values())

    def shuffled(self) -> "AgentResponseMap":
        """Create a new AgentResponseMap with answers shuffled randomly.

        The agent names remain the same, but their answers are randomly
        redistributed among them.

        Returns:
            AgentResponseMap: A new instance with shuffled answers.

        Examples:
            >>> import random; random.seed(42)
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No'})
            >>> shuffled = arm.shuffled()
            >>> set(shuffled.answers) == set(arm.answers)
            True
            >>> len(shuffled.agent_names) == len(arm.agent_names)
            True
        """
        new_answers = [x for x in self.answers]  # Make a copy of the answers
        random.shuffle(new_answers)
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))

    def gold_standard(self) -> "AgentResponseMap":
        """Create a copy of the current AgentResponseMap as gold standard.

        Returns:
            AgentResponseMap: An identical copy of the current mapping.

        Examples:
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No'})
            >>> gold = arm.gold_standard()
            >>> gold.answers == arm.answers
            True
            >>> gold is not arm
            True
        """
        return AgentResponseMap(dict(zip(self.agent_names, self.answers)))

    def random(self) -> "AgentResponseMap":
        """Create a new AgentResponseMap with random answers from the existing set.

        Each agent gets a randomly selected answer from the unique set of
        existing answers.

        Returns:
            AgentResponseMap: A new instance with randomly assigned answers.

        Examples:
            >>> import random; random.seed(42)
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No', 'Charlie': 'Maybe'})
            >>> rand = arm.random()
            >>> all(answer in set(arm.answers) for answer in rand.answers)
            True
            >>> len(rand.agent_names) == len(arm.agent_names)
            True
        """
        new_answers = [random.choice(list(set(self.answers))) for _ in self.answers]
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))

    def modal(self) -> "AgentResponseMap":
        """Create a new AgentResponseMap where all agents have the most common answer.

        All agents will be assigned the most frequently occurring answer from
        the original responses.

        Returns:
            AgentResponseMap: A new instance where all agents have the modal answer.

        Examples:
            >>> arm = AgentResponseMap({'Alice': 'Yes', 'Bob': 'No', 'Charlie': 'Yes'})
            >>> modal = arm.modal()
            >>> all(answer == 'Yes' for answer in modal.answers)
            True
            >>> len(modal.agent_names) == len(arm.agent_names)
            True
        """
        from collections import Counter

        most_common_answer = Counter(self.answers).most_common(1)[0][0]
        new_answers = [most_common_answer for _ in self.answers]
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))

    @classmethod
    def example(cls) -> "AgentResponseMap":
        """Create an example AgentResponseMap for testing and demonstration.

        Returns:
            AgentResponseMap: A sample instance with two agents and their responses.

        Examples:
            >>> arm = AgentResponseMap.example()
            >>> arm['John']
            'Yes'
            >>> arm['Robin']
            'No'
        """
        return cls({"John": "Yes", "Robin": "No"})


class QuestionAgentResponseMap(UserDict):
    """A mapping of question names to AgentResponseMap objects.

    This class manages multiple questions, where each question has its own
    set of agent responses stored in an AgentResponseMap.

    Attributes:
        data (dict): The underlying dictionary mapping question names to AgentResponseMap objects.

    Examples:
        >>> qarm = QuestionAgentResponseMap({'q1': {'Alice': 'Yes', 'Bob': 'No'}})
        >>> isinstance(qarm['q1'], AgentResponseMap)
        True
        >>> qarm['q1']['Alice']
        'Yes'
    """

    def __init__(self, data: dict):
        """Initialize a QuestionAgentResponseMap.

        Args:
            data (dict): A dictionary where keys are question names and values
                are either AgentResponseMap objects or dictionaries that will be
                converted to AgentResponseMap objects.

        Examples:
            >>> qarm = QuestionAgentResponseMap({'q1': {'Alice': 'Yes'}})
            >>> isinstance(qarm['q1'], AgentResponseMap)
            True
        """
        new_data = {}
        for key, value in data.items():
            if not isinstance(value, AgentResponseMap):
                new_value = AgentResponseMap(value)
            else:
                new_value = value
            new_data[key] = new_value
        super().__init__(new_data)

    @classmethod
    def example(cls) -> "QuestionAgentResponseMap":
        """Create an example QuestionAgentResponseMap for testing and demonstration.

        Returns:
            QuestionAgentResponseMap: A sample instance with two questions and agent responses.

        Examples:
            >>> qarm = QuestionAgentResponseMap.example()
            >>> qarm['q1']['John']
            'Yes'
            >>> qarm['q2']['Robin']
            'Yes'
        """
        return cls(
            {
                "q1": AgentResponseMap({"John": "Yes", "Robin": "No"}),
                "q2": AgentResponseMap({"John": "No", "Robin": "Yes"}),
            }
        )


class SourceQuestionAgentResponseMap(UserDict):
    """A mapping of source names to QuestionAgentResponseMap objects.

    This class manages multiple data sources, where each source contains
    multiple questions with their respective agent responses.

    Attributes:
        data (dict): The underlying dictionary mapping source names to QuestionAgentResponseMap objects.

    Examples:
        >>> sqarm = SourceQuestionAgentResponseMap({'source1': {'q1': {'Alice': 'Yes'}}})
        >>> isinstance(sqarm['source1'], QuestionAgentResponseMap)
        True
        >>> sqarm.questions_by_source('source1')
        {'q1'}
    """

    def __init__(self, data: dict):
        """Initialize a SourceQuestionAgentResponseMap.

        Args:
            data (dict): A dictionary where keys are source names and values
                are either QuestionAgentResponseMap objects or nested dictionaries
                that will be converted to the appropriate structure.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}}})
            >>> isinstance(sqarm['src1']['q1'], AgentResponseMap)
            True
        """
        new_data = {}
        for key, value in data.items():
            if not isinstance(value, QuestionAgentResponseMap):
                new_value = QuestionAgentResponseMap(value)
            else:
                new_value = value
            new_data[key] = new_value
        super().__init__(new_data)

    _special_comparisons = ["gold_standard", "shuffled", "random", "modal"]

    def questions_by_source(self, source: str) -> Set[str]:
        """Get all question names for a specific source.

        Args:
            source (str): The name of the source to get questions for.

        Returns:
            Set[str]: A set of question names available in the specified source.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}, 'q2': {'Bob': 'No'}}})
            >>> sqarm.questions_by_source('src1')
            {'q1', 'q2'}
        """
        return set(self[source].keys())

    def generate_evaluations(
        self, other: "SourceQuestionAgentResponseMap"
    ) -> Generator[Tuple[str, str, Evaluation], None, None]:
        """Generate evaluations by comparing this instance with another.

        This method finds overlapping questions between sources and creates
        Evaluation objects for each comparison.

        Args:
            other (SourceQuestionAgentResponseMap): Another instance to compare against.

        Yields:
            Tuple[str, str, Evaluation]: A tuple containing source1 name, question name,
                and the Evaluation object comparing the responses.

        Examples:
            >>> sqarm1 = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}}})
            >>> sqarm2 = SourceQuestionAgentResponseMap({'src2': {'q1': {'Alice': 'No'}}})
            >>> evaluations = list(sqarm1.generate_evaluations(sqarm2))
            >>> len(evaluations) == 1
            True
            >>> evaluations[0][0] == 'src1'
            True
            >>> evaluations[0][1] == 'q1'
            True
        """
        for source1 in self.keys():
            for source2 in other.keys():
                questions_1 = self.questions_by_source(source1)
                questions_2 = other.questions_by_source(source2)
                overlapping_questions = questions_1 & questions_2
                for question_name in overlapping_questions:
                    r1 = Responses(
                        source=source1,
                        question_name=question_name,
                        answer_dict=self[source1][question_name],
                    )
                    r2 = Responses(
                        source=source2,
                        question_name=question_name,
                        answer_dict=other[source2][question_name],
                    )
                    yield source1, question_name, Evaluation(r1, r2)

    def generate_special_comparisons(
        self, source: str, question_name: str
    ) -> Generator[Evaluation, None, None]:
        """Generate special comparison evaluations for a specific source and question.

        This method creates evaluations comparing the gold standard answers
        against shuffled, random, and modal variations.

        Args:
            source (str): The source name to generate comparisons for.
            question_name (str): The question name to generate comparisons for.

        Yields:
            Evaluation: Evaluation objects comparing gold standard against special comparisons.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes', 'Bob': 'No'}}})
            >>> comparisons = list(sqarm.generate_special_comparisons('src1', 'q1'))
            >>> len(comparisons) == 4
            True
        """
        r1_gold = self.get_gold_standard_answers(
            source, question_name, use_method_name=False
        )
        for special_comparison in self._special_comparisons:
            r_compare = self._special_comparison(
                source, question_name, special_comparison
            )
            yield Evaluation(r1_gold, r_compare)

    def _special_comparison(
        self,
        source: str,
        question_name: str,
        method_name: str,
        use_method_name: bool = True,
    ) -> Responses:
        """Create a special comparison using the specified method.

        Args:
            source (str): The source name to get answers from.
            question_name (str): The question name to get answers for.
            method_name (str): The name of the method to call on AgentResponseMap.
            use_method_name (bool, optional): Whether to use method_name as the source
                in the returned Responses object. Defaults to True.

        Returns:
            Responses: A Responses object with the transformed answers.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes', 'Bob': 'No'}}})
            >>> responses = sqarm._special_comparison('src1', 'q1', 'modal')
            >>> responses.source == 'modal'
            True
        """
        answers = self[source][question_name]
        new_answers = getattr(answers, method_name)()
        return Responses(
            source=method_name if use_method_name else source,
            question_name=question_name,
            answer_dict=new_answers,
        )

    def get_gold_standard_answers(
        self, source: str, question_name: str, use_method_name: bool = True
    ) -> Responses:
        """Get the gold standard (original) answers for a source and question.

        Args:
            source (str): The source name to get answers from.
            question_name (str): The question name to get answers for.
            use_method_name (bool, optional): Whether to use 'gold_standard' as the source
                name in the returned object. Defaults to True.

        Returns:
            Responses: A Responses object with the original answers.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}}})
            >>> gold = sqarm.get_gold_standard_answers('src1', 'q1', use_method_name=False)
            >>> gold.source == 'src1'
            True
        """
        return self._special_comparison(
            source, question_name, "gold_standard", use_method_name=False
        )

    def get_shuffled_answers(
        self, source: str, question_name: str, use_method_name: bool = True
    ) -> Responses:
        """Get shuffled answers for a source and question.

        Args:
            source (str): The source name to get answers from.
            question_name (str): The question name to get answers for.
            use_method_name (bool, optional): Whether to use 'shuffled' as the source
                name in the returned object. Defaults to True.

        Returns:
            Responses: A Responses object with shuffled answers.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}}})
            >>> shuffled = sqarm.get_shuffled_answers('src1', 'q1')
            >>> shuffled.source == 'shuffled'
            True
        """
        return self._special_comparison(
            source, question_name, "shuffled", use_method_name=use_method_name
        )

    def get_random_answers(
        self, source: str, question_name: str, use_method_name: bool = True
    ) -> Responses:
        """Get random answers for a source and question.

        Args:
            source (str): The source name to get answers from.
            question_name (str): The question name to get answers for.
            use_method_name (bool, optional): Whether to use 'random' as the source
                name in the returned object. Defaults to True.

        Returns:
            Responses: A Responses object with random answers.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes'}}})
            >>> random_resp = sqarm.get_random_answers('src1', 'q1')
            >>> random_resp.source == 'random'
            True
        """
        return self._special_comparison(
            source, question_name, "random", use_method_name=use_method_name
        )

    def modal_answers(
        self, source: str, question_name: str, use_method_name: bool = True
    ) -> Responses:
        """Get modal (most common) answers for a source and question.

        Args:
            source (str): The source name to get answers from.
            question_name (str): The question name to get answers for.
            use_method_name (bool, optional): Whether to use 'modal' as the source
                name in the returned object. Defaults to True.

        Returns:
            Responses: A Responses object with modal answers.

        Examples:
            >>> sqarm = SourceQuestionAgentResponseMap({'src1': {'q1': {'Alice': 'Yes', 'Bob': 'Yes', 'Charlie': 'No'}}})
            >>> modal_resp = sqarm.modal_answers('src1', 'q1')
            >>> modal_resp.source == 'modal'
            True
        """
        return self._special_comparison(
            source, question_name, "modal", use_method_name=use_method_name
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
