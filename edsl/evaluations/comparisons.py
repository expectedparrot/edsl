from collections import UserDict
from typing import List, Set, Generator, Tuple
import random

from .evaluations import Evaluation, Responses

class AgentResponseMap(UserDict):
    """Keys are agent names, values are answers to questions"""
     
    @property
    def agent_names(self) -> List[str]:
        return list(self.keys())
    
    @property
    def answers(self) -> List[str]:
        return list(self.values())

    def shuffled(self) -> 'AgentResponseMap':
        new_answers = [x for x in self.answers] # Make a copy of the answers
        random.shuffle(new_answers)
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))
   
    def gold_standard(self) -> 'AgentResponseMap':
        return AgentResponseMap(dict(zip(self.agent_names, self.answers)))
    
    def random(self) -> 'AgentResponseMap':
        new_answers = [random.choice(list(set(self.answers))) for _ in self.answers]
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))
    
    def modal(self) -> 'AgentResponseMap':
        from collections import Counter
        most_common_answer = Counter(self.answers).most_common(1)[0][0]
        new_answers = [most_common_answer for _ in self.answers]
        return AgentResponseMap(dict(zip(self.agent_names, new_answers)))
    
    @classmethod
    def example(cls) -> 'AgentResponseMap':
        return cls({'John': 'Yes', 'Robin': 'No'})
    
class QuestionAgentResponseMap(UserDict):
    "Keys are question names, values are AgentResponseMap objects"
    def __init__(self, data: dict):
        new_data = {}
        for key, value in data.items():
            if not isinstance(value, AgentResponseMap):
                new_value = AgentResponseMap(value)
            else:
                new_value = value
            new_data[key] = new_value
        super().__init__(new_data)
    
    @classmethod
    def example(cls) -> 'QuestionAgentResponseMap':
        return cls({'q1': AgentResponseMap({'John': 'Yes', 'Robin': 'No'}), 'q2': AgentResponseMap({'John': 'No', 'Robin': 'Yes'})})

class SourceQuestionAgentResponseMap(UserDict):
    "Keys are source names, values are QuestionAgentResponseMap objects"

    def __init__(self, data: dict):
        new_data = {}
        for key, value in data.items():
            if not isinstance(value, QuestionAgentResponseMap):
                new_value = QuestionAgentResponseMap(value)
            else:
                new_value = value
            new_data[key] = new_value
        super().__init__(new_data)

    special_comparisons = ['gold_standard', 'shuffled', 'random', 'modal']
    
    def questions_by_source(self, source:str) -> Set[str]:
        return set(self[source].keys())
    
    def generate_evaluations(self, other: 'SourceQuestionAgentResponseMap') -> Generator[Tuple[str, str, Evaluation], None, None]:
        for source1 in self.keys():
            for source2 in other.keys():
                questions_1 = self.questions_by_source(source1)
                questions_2 = other.questions_by_source(source2)
                overlapping_questions = questions_1 & questions_2
                for question_name in overlapping_questions:
                    r1 = Responses(source = source1, question_name = question_name, answer_dict = self[source1][question_name])
                    r2 = Responses(source = source2, question_name = question_name, answer_dict = other[source2][question_name])
                    yield source1, question_name, Evaluation(r1, r2)

    def generate_special_comparisons(self, source:str, question_name:str) -> Generator[Evaluation, None, None]:
        r1_gold = self.get_gold_standard_answers(source, question_name)
        for special_comparison in self.special_comparisons:
            r_compare = self._special_comparison(source, question_name, special_comparison)
            yield Evaluation(r1_gold, r_compare)

    def _special_comparison(self, source:str, question_name:str, method_name:str) -> Set[str]:
        answers = self[source][question_name]
        new_answers = getattr(answers, method_name)()
        return Responses(source = method_name, question_name = question_name, answer_dict = new_answers)

    def get_gold_standard_answers(self, source:str, question_name:str) -> AgentResponseMap:
        return self._special_comparison(source, question_name, 'gold_standard')
    
    def get_shuffled_answers(self, source:str, question_name:str) -> AgentResponseMap:
        return self._special_comparison(source, question_name, 'shuffled')
    
    def get_random_answers(self, source:str, question_name:str) -> AgentResponseMap:
        return self._special_comparison(source, question_name, 'random')
    
    def modal_answers(self, source:str, question_name:str) -> AgentResponseMap:
        return self._special_comparison(source, question_name, 'modal')

