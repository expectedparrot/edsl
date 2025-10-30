from __future__ import annotations
import ast

"""Compare candidate results against gold standard results."""

from typing import Dict, Any, TYPE_CHECKING, Optional
from collections import UserDict

if TYPE_CHECKING:
    from edsl.results import Results
    from edsl.scenarios import ScenarioList
    from .metrics import MetricsCollection
    from ..results import Results
    from .result_pair_comparison import ResultPairComparison

class CompareResultsToGold(UserDict):
    """Compare candidate model results against gold standard model results.
    
    This class behaves like a dictionary, mapping base agent names to their comparisons.

    Examples:
        >>> from edsl.comparisons import CompareResultsToGold
        >>> crtg = CompareResultsToGold.example()
        >>> isinstance(crtg, CompareResultsToGold)
        True
        >>> len(crtg.candidate_results) > 0
        True
        >>> len(crtg.gold_results) > 0
        True
        >>> # Test dictionary-like behavior
        >>> 'test_agent' in crtg
        True
        >>> list(crtg.keys())
        ['test_agent']
        >>> len(crtg) > 0
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

        self.candidate_agent_names = set(
            result.agent.base_name for result in self.candidate_results
        )
        self.gold_agent_names = set(
            result.agent.base_name for result in self.gold_results
        )
        for agent_name in self.candidate_agent_names:
            if agent_name not in self.gold_agent_names:
                raise ValueError(f"Agent '{agent_name}' not found in gold results")

        self.base_agent_name_to_gold_results = {
            result.agent.base_name: result for result in self.gold_results
        }

        data = {}
        for base_agent_name, full_agent_name, rpc in self._build_comparisons():
            if base_agent_name not in data:
                data[base_agent_name] = {}
            data[base_agent_name][full_agent_name] = rpc
        super().__init__(data)

    def __repr__(self) -> str:
        """Return a Rich-formatted representation of the CompareResultsToGold.
        
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> repr(crtg)  # doctest: +ELLIPSIS
            'CompareResultsToGold(...'
        """
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr()

        # Check if we're in a Jupyter notebook environment
        # If so, return minimal representation since _repr_html_ will handle display
        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                # We're in a Jupyter notebook/kernel, not IPython terminal
                return f"{self.__class__.__name__}(...)"
        except (NameError, ImportError):
            pass

        return self._summary_repr()

    def _eval_repr(self):
        """Return a string representation of the CompareResultsToGold for evaluation purposes.
        
        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg._eval_repr()
            'CompareResultsToGold()'
        """
        return f"{self.__class__.__name__}()"
    
    def _summary_repr(self, MAX_AGENTS: int = 5, MAX_COMPARISONS: int = 3, MAX_QUESTIONS: int = 3) -> str:
        """Generate a summary representation of the CompareResultsToGold with Rich formatting.

        Args:
            MAX_AGENTS: Maximum number of base agents to show (default: 5)
            MAX_COMPARISONS: Maximum number of full agent comparisons to show per base agent (default: 3)
            MAX_QUESTIONS: Maximum number of questions to show per comparison (default: 3)
        """
        from rich.console import Console
        from rich.text import Text
        import io
        import shutil
        from edsl.config import RICH_STYLES
        
        # Get terminal width
        terminal_width = shutil.get_terminal_size().columns
        
        # Build the Rich text
        output = Text()
        output.append("CompareResultsToGold(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_base_agents={len(self)},\n", style=RICH_STYLES["default"])
        output.append(f"    num_candidates={len(self.candidate_results)},\n", style=RICH_STYLES["default"])
        output.append(f"    num_gold={len(self.gold_results)},\n", style=RICH_STYLES["default"])
        output.append("    data={\n", style=RICH_STYLES["default"])
        
        # Show the first MAX_AGENTS base agents
        num_agents_to_show = min(MAX_AGENTS, len(self))
        for agent_idx, (base_agent_name, comparisons) in enumerate(list(self.items())[:num_agents_to_show]):
            # Show base agent name
            output.append("        ", style=RICH_STYLES["default"])
            output.append(f"'{base_agent_name}'", style=RICH_STYLES["secondary"])
            output.append(": {\n", style=RICH_STYLES["default"])
            
            # Show comparisons for this base agent
            num_comparisons_to_show = min(MAX_COMPARISONS, len(comparisons))
            for comp_idx, (full_agent_name, rpc) in enumerate(list(comparisons.items())[:num_comparisons_to_show]):
                output.append("            ", style=RICH_STYLES["default"])
                output.append(f"'{full_agent_name}'", style=RICH_STYLES["secondary"])
                output.append(": {\n", style=RICH_STYLES["default"])
                
                # Show first few questions from the ResultPairComparison
                num_questions_to_show = min(MAX_QUESTIONS, len(rpc))
                for q_idx, (question_name, metrics) in enumerate(list(rpc.items())[:num_questions_to_show]):
                    output.append("                ", style=RICH_STYLES["default"])
                    output.append(f"'{question_name}'", style=RICH_STYLES["key"])
                    output.append(": ", style=RICH_STYLES["default"])

                    # Show a few key metrics
                    metrics_preview = {}
                    for key in ['exact_match', 'cosine_similarity', 'edit_distance']:
                        if key in metrics:
                            metrics_preview[key] = metrics[key]

                    output.append(f"{metrics_preview}", style=RICH_STYLES["default"])

                    if q_idx < num_questions_to_show - 1:
                        output.append(",\n", style=RICH_STYLES["default"])
                    else:
                        output.append("\n", style=RICH_STYLES["default"])
                
                # Show truncation indicator if needed
                if len(rpc) > MAX_QUESTIONS:
                    output.append(
                        f"                ... ({len(rpc) - MAX_QUESTIONS} more questions)\n",
                        style=RICH_STYLES["dim"],
                    )

                output.append("            }", style=RICH_STYLES["default"])

                if comp_idx < num_comparisons_to_show - 1:
                    output.append(",\n", style=RICH_STYLES["default"])
                else:
                    output.append("\n", style=RICH_STYLES["default"])
            
            # Show truncation indicator if needed
            if len(comparisons) > MAX_COMPARISONS:
                output.append(
                    f"            ... ({len(comparisons) - MAX_COMPARISONS} more comparisons)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("        }", style=RICH_STYLES["default"])

            if agent_idx < num_agents_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])
        
        # Show truncation indicator if needed
        if len(self) > MAX_AGENTS:
            output.append(
                f"        ... ({len(self) - MAX_AGENTS} more base agents)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    }\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])
        
        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()

    def _build_comparisons(
        self, metrics_collection: Optional["MetricsCollection"] = None
    ) -> Dict[str, ResultPairComparison]:
        """Build ResultPairComparison objects for each candidate-gold pair.

        Returns:
            Dict mapping agent names to ResultPairComparisonList objects
        """
        from .result_pair_comparison import ResultPairComparison

        for candidate_result in self.candidate_results:
            full_agent_name = candidate_result.agent.name
            base_agent_name = candidate_result.agent.base_name
            gold_result = self.base_agent_name_to_gold_results[base_agent_name]
            rpc = ResultPairComparison(
                result_A=candidate_result,
                result_B=gold_result,
                metrics_collection=metrics_collection,
            )
            yield base_agent_name, full_agent_name, rpc

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary.

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> d = crtg.to_dict()
            >>> isinstance(d, dict)
            True
            >>> 'candidate_results' in d
            True
            >>> 'gold_results' in d
            True
        """
        return {
            "candidate_results": self.candidate_results.to_dict(),
            "gold_results": self.gold_results.to_dict(),
            "data": {base_agent_name: {full_agent_name: rpc.to_dict() for full_agent_name, rpc in comparisons.items()} for base_agent_name, comparisons in self.data.items()},
        }

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
        instance.data = {
            base_agent_name: {full_agent_name: ResultPairComparison.from_dict(rpc_dict) for full_agent_name, rpc_dict in comparisons.items()} for base_agent_name, comparisons in data.get("data", {}).items()
        }
        return instance

    @classmethod
    def example(cls) -> "CompareResultsToGold":
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
        model_gold = Model(
            model_name="test", service_name="test", canned_response="Great"
        )

        # Candidate model gives a different answer (matching a different option)
        model_cand = Model(
            model_name="test", service_name="test", canned_response="Good"
        )

        # Run surveys to get results (using test models, no API calls)
        gold_results = (
            survey.by(agent_gold)
            .by(model_gold)
            .run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
        )

        candidate_results = (
            survey.by(agent_cand1)
            .by(model_cand)
            .run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
        )
        return cls(candidate_results, gold_results)



if __name__ == "__main__":
    import doctest

    doctest.testmod()
