from typing import Dict, Callable, Optional, List
from dataclasses import dataclass

from ..base import ItemCollection
from ..scenarios import Scenario, ScenarioList

@dataclass
class Responses:
    source: str 
    question_name: str
    answer_dict: Dict[str, str]

    def to_dict(self):
        return {
            'source': self.source,
            'question_name': self.question_name,
            'answer_dict': self.answer_dict
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            source = data['source'],
            question_name = data['question_name'],
            answer_dict = data['answer_dict']
        )


def success_failure_tally(answer_dict: Dict[str, str], gold_standard: Dict[str, str]) -> Dict:
    """Success failure tally for a single question"""
    results = {
        'success': [],
        'failure': [],
        'key_error': []
    }
    for agent_name, answer in gold_standard.items():
        if (response := answer_dict.get(agent_name, None)) is None:
            results['key_error'].append(agent_name)
        elif response == answer:
            results['success'].append(agent_name)
        else:
            results['failure'].append(agent_name)
    
    # Calculate metrics
    total_valid = len(results['success']) + len(results['failure'])
    accuracy = len(results['success']) / total_valid if total_valid > 0 else 0
    
    return Scenario({
        'evaluation_function_name': 'success_failure_tally',
        'accuracy': accuracy,
        'success_count': len(results['success']),
        'failure_count': len(results['failure']),
        'key_error_count': len(results['key_error']),
        'details': results
    })

    
class Evaluation: 

    def __init__(self, r1: Responses, r2: Responses, name: Optional[str] = None):
        self.r1 = r1
        self.r2 = r2
        self.evaluation_results = []
        if name is None:
            self.name = f"'{r1.source}' vs '{r2.source}' - '{r1.question_name}'"
        else:
            self.name = name

    def to_scenario_list(self):
        scenarios = []
        for evaluation_result in self.evaluation_results:
            scenarios.append(Scenario({'source_1': self.r1.source, 'source_2': self.r2.source, 'question_name': self.r1.question_name}) + evaluation_result)
        return ScenarioList(scenarios)
        
    def evaluate(self, evaluation_function: Callable, evaluation_function_name: Optional[str] = None) -> None:
        """Evaluate agent performance against gold standard"""
        if evaluation_function_name is None:
            evaluation_function_name = evaluation_function.__name__
        self.evaluation_results.append(evaluation_function(self.r1.answer_dict, self.r2.answer_dict))

    def to_dict(self):
        return {
            'r1': self.r1.to_dict(),
            'r2': self.r2.to_dict(),
            'evaluation_results': self.evaluation_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            r1 = Responses.from_dict(data['r1']),
            r2 = Responses.from_dict(data['r2']),
            evaluation_results = data['evaluation_results']
        )

class EvaluationList(ItemCollection):
    item_class = Evaluation

    def __init__(self, *args, evaluation_functions: Optional[List[Callable]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if evaluation_functions is None:
            self.evaluation_functions = [success_failure_tally]
        else:
            self.evaluation_functions = evaluation_functions

    def evaluate(self):
        for item in self:
            for evaluation_function in self.evaluation_functions:
                item.evaluate(evaluation_function)

    def to_scenario_list(self):
        scenarios = []
        for item in self:
            scenarios.extend(item.to_scenario_list())
        return ScenarioList(scenarios)

