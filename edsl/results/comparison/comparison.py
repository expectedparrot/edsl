"""Pair-wise comparison of two Result objects across configurable metrics."""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from .metrics import MetricsCollection

if TYPE_CHECKING:
    from ..result import Result

QuestionName = str


class ResultPairComparison:
    """Compare two Result objects across shared questions using a set of metrics.

    The ``comparisons`` attribute is a dict mapping question names to::

        {
            "metrics": {"exact_match": ..., "overlap": ..., ...},
            "answer_a": ...,
            "answer_b": ...,
            "question_text": ...,
            "question_type": ...,
        }

    Examples:
        >>> rpc = ResultPairComparison.example()
        >>> "how_feeling" in rpc.comparisons
        True
        >>> "metrics" in rpc.comparisons["how_feeling"]
        True
    """

    def __init__(
        self,
        result_a: "Result",
        result_b: "Result",
        metrics_collection: MetricsCollection | None = None,
    ):
        self.result_a = result_a
        self.result_b = result_b
        self.metrics_collection = metrics_collection or MetricsCollection()
        self.comparisons: Dict[QuestionName, Dict[str, Any]] = dict(
            self._calculate()
        )

    @property
    def _common_questions(self) -> List[QuestionName]:
        return sorted(
            set(self.result_a.get_question_names())
            & set(self.result_b.get_question_names())
        )

    def _calculate(self):
        for qname in self._common_questions:
            answer_a = self.result_a.get_answer(qname)
            answer_b = self.result_b.get_answer(qname)
            yield qname, {
                "metrics": self.metrics_collection.compute(answer_a, answer_b),
                "answer_a": answer_a,
                "answer_b": answer_b,
                "question_text": self.result_a.get_question_text(qname),
                "question_type": self.result_a.get_question_type(qname),
            }

    def __repr__(self) -> str:
        questions = list(self.comparisons.keys())
        return f"ResultPairComparison(questions={questions})"

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.

        >>> rpc = ResultPairComparison.example()
        >>> d = rpc.to_dict()
        >>> "result_a" in d and "result_b" in d
        True
        """
        result: Dict[str, Any] = {
            "result_a": self.result_a.to_dict(),
            "result_b": self.result_b.to_dict(),
            "comparisons": self.comparisons,
            "edsl_class_name": self.__class__.__name__,
        }
        if add_edsl_version:
            from edsl import __version__

            result["edsl_version"] = __version__
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultPairComparison":
        """Deserialize from dictionary.

        >>> rpc = ResultPairComparison.example()
        >>> rpc2 = ResultPairComparison.from_dict(rpc.to_dict())
        >>> list(rpc2.comparisons.keys()) == list(rpc.comparisons.keys())
        True
        """
        from ..result import Result

        result_a = Result.from_dict(data["result_a"])
        result_b = Result.from_dict(data["result_b"])
        instance = cls(result_a=result_a, result_b=result_b)
        # Use pre-computed comparisons if present
        for key in ("comparisons", "comparison_data", "data"):
            if key in data:
                instance.comparisons = data[key]
                break
        return instance

    def to_scenario_list(self) -> "ScenarioList":
        """Convert to a ScenarioList with one scenario per question-metric pair.

        >>> rpc = ResultPairComparison.example()
        >>> sl = rpc.to_scenario_list()
        >>> len(sl) > 0
        True
        >>> "question_name" in sl[0] and "metric_name" in sl[0]
        True
        """
        from ...scenarios.scenario import Scenario
        from ...scenarios.scenario_list import ScenarioList

        scenarios = []
        for qname, cdata in self.comparisons.items():
            for metric_name, metric_value in cdata["metrics"].items():
                scenarios.append(
                    Scenario(
                        {
                            "question_name": qname,
                            "answer_a": cdata["answer_a"],
                            "answer_b": cdata["answer_b"],
                            "metric_name": metric_name,
                            "metric_value": metric_value,
                        }
                    )
                )
        return ScenarioList(scenarios)

    @classmethod
    def example(cls) -> "ResultPairComparison":
        """Return an example using Results.example().

        >>> rpc = ResultPairComparison.example()
        >>> isinstance(rpc, ResultPairComparison)
        True
        """
        from ...results import Results

        results = Results.example()
        return cls(results[0], results[1])


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
