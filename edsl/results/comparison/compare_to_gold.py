"""Compare candidate results against gold standard results."""

from __future__ import annotations

from collections import UserDict
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from .metrics import MetricsCollection


class CompareResultsToGold(UserDict):
    """Compare candidate model results against gold standard model results.

    Behaves like a dict mapping base agent names to
    ``{full_agent_name: ResultPairComparison, ...}``.

    >>> crtg = CompareResultsToGold.example()
    >>> isinstance(crtg, CompareResultsToGold)
    True
    """

    def __init__(
        self,
        candidate_results: "Results",
        gold_results: "Results",
        metrics_collection: Optional["MetricsCollection"] = None,
    ):
        self.candidate_results = candidate_results
        self.gold_results = gold_results
        self.metrics_collection = metrics_collection

        self.candidate_agent_names = {
            r.agent.base_name for r in self.candidate_results
        }
        self.gold_agent_names = {r.agent.base_name for r in self.gold_results}

        for name in self.candidate_agent_names:
            if name not in self.gold_agent_names:
                raise ValueError(f"Agent '{name}' not found in gold results")

        self._gold_by_base = {
            r.agent.base_name: r for r in self.gold_results
        }

        data: Dict[str, Dict[str, Any]] = {}
        for base, full, rpc in self._build_comparisons():
            data.setdefault(base, {})[full] = rpc
        super().__init__(data)

    def _build_comparisons(self):
        from .comparison import ResultPairComparison

        for candidate in self.candidate_results:
            full_name = candidate.agent.name
            base_name = candidate.agent.base_name
            gold = self._gold_by_base[base_name]
            rpc = ResultPairComparison(
                result_a=candidate,
                result_b=gold,
                metrics_collection=self.metrics_collection,
            )
            yield base_name, full_name, rpc

    def __repr__(self) -> str:
        return (
            f"CompareResultsToGold(base_agents={list(self.keys())}, "
            f"candidates={len(self.candidate_results)}, "
            f"gold={len(self.gold_results)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.

        >>> crtg = CompareResultsToGold.example()
        >>> d = crtg.to_dict()
        >>> "candidate_results" in d and "gold_results" in d
        True
        """
        return {
            "candidate_results": self.candidate_results.to_dict(),
            "gold_results": self.gold_results.to_dict(),
            "data": {
                base: {full: rpc.to_dict() for full, rpc in comps.items()}
                for base, comps in self.data.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareResultsToGold":
        """Deserialize from dictionary.

        >>> crtg = CompareResultsToGold.example()
        >>> crtg2 = CompareResultsToGold.from_dict(crtg.to_dict())
        >>> isinstance(crtg2, CompareResultsToGold)
        True
        """
        from .comparison import ResultPairComparison
        from ...results import Results

        instance = cls(
            Results.from_dict(data["candidate_results"]),
            Results.from_dict(data["gold_results"]),
        )
        instance.data = {
            base: {
                full: ResultPairComparison.from_dict(rpc_dict)
                for full, rpc_dict in comps.items()
            }
            for base, comps in data.get("data", {}).items()
        }
        return instance

    @classmethod
    def example(cls) -> "CompareResultsToGold":
        """Return an example instance using test models.

        >>> crtg = CompareResultsToGold.example()
        >>> len(crtg) > 0
        True
        """
        from ...agents import Agent
        from ...surveys import Survey
        from ...language_models import Model
        from ...questions import QuestionMultipleChoice

        q = QuestionMultipleChoice.example()
        survey = Survey(questions=[q])

        agent_gold = Agent(name="test_agent", traits={"persona": "gold standard"})
        agent_cand = Agent(
            name=str({"name": "test_agent", "model_index": 0, "scenario_index": 0}),
            traits={"persona": "candidate"},
        )

        model_gold = Model(model_name="test", service_name="test", canned_response="Great")
        model_cand = Model(model_name="test", service_name="test", canned_response="Good")

        gold_results = (
            survey.by(agent_gold)
            .by(model_gold)
            .run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
        )
        candidate_results = (
            survey.by(agent_cand)
            .by(model_cand)
            .run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
        )
        return cls(candidate_results, gold_results)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
