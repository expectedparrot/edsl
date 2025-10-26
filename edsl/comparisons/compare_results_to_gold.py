from __future__ import annotations
import ast

"""Compare candidate results against gold standard results."""

from typing import Dict, Any, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from edsl.results import Results
    from edsl.scenarios import ScenarioList
    from .metrics import MetricsCollection
    from ..results import Results

from ..base import Base


class CompareResultsToGold(Base):
    """Compare candidate model results against gold standard model results.
    
    Examples:
        >>> from edsl.comparisons import CompareResultsToGold
        >>> crtg = CompareResultsToGold.example()
        >>> isinstance(crtg, CompareResultsToGold)
        True
        >>> len(crtg.candidate_results) > 0
        True
        >>> len(crtg.gold_results) > 0
        True
    """
    def __init__(
        self,
        candidate_results: "Results",
        gold_results: "Results",
    ):
        """Initialize with candidate and gold standard results.
        
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg.candidate_agent_names == {'test_agent'}
            True
            >>> crtg.gold_agent_names == {'test_agent'}
            True
        """
        self.candidate_results = candidate_results
        self.gold_results = gold_results

        self.candidate_agent_names = set(result.agent.base_name for result in self.candidate_results)
        self.gold_agent_names = set(result.agent.base_name for result in self.gold_results)
        for agent_name in self.candidate_agent_names:
            if agent_name not in self.gold_agent_names:
                raise ValueError(f"Agent '{agent_name}' not found in gold results")

        self.base_agent_name_to_gold_results = {result.agent.base_name: result for result in self.gold_results}

        self._comparisons = None

    @property
    def comparisons(self) -> Dict[str, Dict[str, 'ResultPairComparison']]:
        """Return the comparisons.
        
        Returns:
            Dict mapping agent names to ResultPairComparisonList objects
            
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> comparisons = crtg.comparisons
            >>> isinstance(comparisons, dict)
            True
            >>> 'test_agent' in comparisons
            True
        """
        if self._comparisons is None:
            from collections import defaultdict
            self._comparisons = defaultdict(dict)
            for base_agent_name, full_agent_name, rpc in self._build_comparisons():
                self._comparisons[base_agent_name][full_agent_name] = rpc
        return self._comparisons

    @classmethod
    def example(cls, randomize: bool = False) -> "CompareResultsToGold":
        """Return an example CompareResultsToGold instance.

        Creates a simple example with mock candidate and gold standard results
        for demonstration purposes using test models (no actual LLM calls).

        Args:
            randomize: If True, creates random example data

        Returns:
            Example CompareResultsToGold instance

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> isinstance(crtg, CompareResultsToGold)
            True
        """
        from edsl import Results, Agent, Survey, Model, Cache
        from edsl.questions import QuestionMultipleChoice

        # Create a simple survey for testing
        q = QuestionMultipleChoice.example()
        survey = Survey(questions=[q])

        # Create agents with proper naming pattern
        # Pattern: {'name': 'base_name', 'model_index': X, 'scenario_index': Y}
        agent_gold = Agent(name="test_agent", traits={"persona": "gold standard"})
        agent_cand1 = Agent(
            name=str({"name": "test_agent", "model_index": 0, "scenario_index": 0}),
            traits={"persona": "candidate 1"},
        )

        # Create test models with different canned responses (no actual LLM calls)
        # Gold model gives the "correct" answer (matching one of the question options)
        model_gold = Model(model_name="test", service_name="test", canned_response="Great")
        
        # Candidate model gives a different answer (matching a different option)
        model_cand = Model(model_name="test", service_name="test", canned_response="Good")

        # Run surveys to get results (using test models, no API calls)
        gold_results = survey.by(agent_gold).by(model_gold).run(
            cache=False, disable_remote_cache=True, disable_remote_inference=True
        )

        candidate_results = survey.by(agent_cand1).by(model_cand).run(
            cache=False, disable_remote_cache=True, disable_remote_inference=True
        )
        return cls(candidate_results, gold_results)

    def _build_comparisons(self, metrics_collection: Optional['MetricsCollection'] = None) -> Dict[str, ResultPairComparisonList]:
        """Build ResultPairComparison objects for each candidate-gold pair.
        
        Returns:
            Dict mapping agent names to ResultPairComparisonList objects
        """
        from .result_pair_comparison import ResultPairComparison
        from .metrics import MetricsCollection
        for candidate_result in self.candidate_results:
            full_agent_name = candidate_result.agent.name
            base_agent_name = candidate_result.agent.base_name
            gold_result = self.base_agent_name_to_gold_results[base_agent_name]
            rpc = ResultPairComparison(
                result_A=candidate_result, 
                result_B=gold_result, 
                metrics_collection = metrics_collection
            )
            yield base_agent_name, full_agent_name, rpc

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.
        
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> _ = crtg.comparisons
            >>> d = crtg.to_dict()
            >>> isinstance(d, dict)
            True
            >>> 'candidate_results' in d
            True
            >>> 'gold_results' in d
            True
        """
        result = {
            "candidate_results": self.candidate_results.to_dict(),
            "gold_results": self.gold_results.to_dict(),
            "comparisons": {base_agent_name: {full_agent_name: rpc.to_dict() for full_agent_name, rpc in comparisons.items()} for base_agent_name, comparisons in self.comparisons.items()}}

        if add_edsl_version:
            try:
                from edsl import __version__

                result["edsl_version"] = __version__
            except ImportError:
                pass

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareResultsToGold":
        """Deserialize from dictionary.
        Args:
            data: Dictionary containing CompareResultsToGold data

        Returns:
            CompareResultsToGold instance
            
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> _ = crtg.comparisons
            >>> d = crtg.to_dict()
            >>> crtg2 = CompareResultsToGold.from_dict(d)
            >>> isinstance(crtg2, CompareResultsToGold)
            True
        """
        from .result_pair_comparison import ResultPairComparison
        from edsl.results import Results
        instance = cls(
            Results.from_dict(data["candidate_results"]),
            Results.from_dict(data["gold_results"]),
        )
        cls._comparisons = {base_agent_name: {full_agent_name: ResultPairComparison.from_dict(rpc_dict) for full_agent_name, rpc_dict in comparisons.items()} for base_agent_name, comparisons in data.get("comparisons", {}).items()}
        return instance

        # Import Results to deserialize
    def code(self) -> str:
        """Return Python code to recreate this CompareResultsToGold.

        Returns:
            Python code string
        """
        raise NotImplementedError("Code generation not implemented for CompareResultsToGold")

    def __hash__(self) -> int:
        """Return hash of the CompareResultsToGold.
        
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> _ = crtg.comparisons
            >>> isinstance(hash(crtg), int)
            True
        """
        from ..utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))


    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the CompareResultsToGold.

        Returns:
            str: A string that can be evaluated to recreate the CompareResultsToGold
        """
        return f"CompareResultsToGold(candidate_results, gold_results)"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the CompareResultsToGold with Rich formatting.

        Returns:
            str: A formatted summary representation of the CompareResultsToGold
        """
        return f"CompareResultsToGold(candidate_results, gold_results)"

if __name__ == "__main__":
    import doctest
    doctest.testmod()
