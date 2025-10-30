from edsl.comparisons.result_pair_comparison.result_pair_comparison import ResultPairComparison


from typing import Any, List, Dict
from ..comparisons import CompareResultsToGold, ResultPairComparison

from collections import UserDict

class ParetoFrontier:
    """Class to store and display the pareto frontier of agent performance metrics."""
    
    def __init__(self, frontier_data: Dict[str, Dict[str, List[int]]]):
        self.data = dict(frontier_data)
    
    def __repr__(self) -> str:
        if not self.data:
            return "ParetoFrontier(empty)"
        
        lines = ["ParetoFrontier:"]
        for question_name, metrics in sorted(self.data.items()):
            lines.append(f"  Question: {question_name}")
            for metric_name, agent_indices in sorted(metrics.items()):
                indices_str = ", ".join(map(str, agent_indices))
                lines.append(f"    {metric_name}: agents [{indices_str}]")
        return "\n".join(lines)

class EvaluateAgentsAgainstGold(UserDict):
    """Class to evaluate agents against gold results.
    """

    def __init__(self, result_pair_comparison_list: List['ResultPairComparison']):
        self.rpc_list = result_pair_comparison_list
        agent_base_name = None
        for rpc in self.rpc_list:
            if agent_base_name is None:
                agent_base_name = rpc.result_A.agent.base_name
            if rpc.result_A.agent.base_name != agent_base_name:
                raise ValueError(f"""All agents in the list must be the base same. 
                One agent has a name of {rpc.result_A.agent.base_name}; 
                Another has a name of {agent_base_name}""")

        best_metrics = self._compute_best_metrics()
        pareto_frontier = self._compute_by_question_pareto_frontier()
        d = {}
        for question_name, metrics in best_metrics.items():
            d[question_name] = {'best_metrics': metrics, 'pareto_frontier': pareto_frontier.data[question_name]}
        super().__init__(d)

    def __repr__(self) -> str:
        """Return a Rich-formatted representation of the EvaluateAgentsAgainstGold.
        
        Examples:
            >>> from edsl.comparisons.evaluate_agents_against_gold import EvaluateAgentsAgainstGold
            >>> eag = EvaluateAgentsAgainstGold.example()
            >>> repr(eag)  # doctest: +ELLIPSIS
            'EvaluateAgentsAgainstGold(...'
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
        """Return a string representation of the EvaluateAgentsAgainstGold for evaluation purposes.
        
        Examples:
            >>> from edsl.comparisons.evaluate_agents_against_gold import EvaluateAgentsAgainstGold
            >>> eag = EvaluateAgentsAgainstGold.example()
            >>> eag._eval_repr()
            'EvaluateAgentsAgainstGold()'
        """
        return f"{self.__class__.__name__}()"
    
    def _summary_repr(self, MAX_QUESTIONS: int = 10, MAX_METRICS: int = 10) -> str:
        """Generate a summary representation of the EvaluateAgentsAgainstGold with Rich formatting.

        Args:
            MAX_QUESTIONS: Maximum number of questions to show (default: 10)
            MAX_METRICS: Maximum number of metrics to show per question (default: 10)
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
        output.append("EvaluateAgentsAgainstGold(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_agents={len(self.rpc_list)},\n", style=RICH_STYLES["default"])
        output.append(f"    num_questions={len(self)},\n", style=RICH_STYLES["default"])
        output.append("    data={\n", style=RICH_STYLES["default"])
        
        # Show the first MAX_QUESTIONS questions
        num_to_show = min(MAX_QUESTIONS, len(self))
        for i, (question_name, question_data) in enumerate(list(self.items())[:num_to_show]):
            # Show question name
            output.append("        ", style=RICH_STYLES["default"])
            output.append(f"'{question_name}'", style=RICH_STYLES["secondary"])
            output.append(": {\n", style=RICH_STYLES["default"])

            # Show metrics section
            output.append("            ", style=RICH_STYLES["default"])
            output.append("'best_metrics'", style=RICH_STYLES["secondary"])
            output.append(": {\n", style=RICH_STYLES["default"])
            
            metrics = question_data.get('best_metrics', {})
            metrics_items = list(metrics.items())[:MAX_METRICS]
            was_truncated = len(metrics) > MAX_METRICS
            
            for metric_name, metric_value in metrics_items:
                # Format the value
                if isinstance(metric_value, float):
                    value_repr = f"{metric_value:.4f}"
                else:
                    value_repr = repr(metric_value)

                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{metric_name}'", style=RICH_STYLES["key"])
                output.append(f": {value_repr},\n", style=RICH_STYLES["default"])

            if was_truncated:
                output.append(
                    f"                ... ({len(metrics) - MAX_METRICS} more metrics)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            },\n", style=RICH_STYLES["default"])

            # Show pareto_frontier section
            output.append("            ", style=RICH_STYLES["default"])
            output.append("'pareto_frontier'", style=RICH_STYLES["secondary"])
            output.append(": {\n", style=RICH_STYLES["default"])
            
            pareto = question_data.get('pareto_frontier', {})
            pareto_items = list(pareto.items())[:MAX_METRICS]
            pareto_truncated = len(pareto) > MAX_METRICS
            
            for metric_name, agent_indices in pareto_items:
                indices_str = ", ".join(map(str, agent_indices))
                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{metric_name}'", style=RICH_STYLES["key"])
                output.append(f": [{indices_str}],\n", style=RICH_STYLES["default"])

            if pareto_truncated:
                output.append(
                    f"                ... ({len(pareto) - MAX_METRICS} more metrics)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            }\n", style=RICH_STYLES["default"])
            output.append("        }", style=RICH_STYLES["default"])

            # Add comma and newline unless it's the last one
            if i < num_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])

        # Add ellipsis if there are more questions
        if len(self) > MAX_QUESTIONS:
            output.append(
                f"        ... ({len(self) - MAX_QUESTIONS} more questions)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    }\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])
        
        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()
            
    def _compute_best_metrics(self):
        """Evaluate each comparison to find the pareto frontier"""
        best_metrics = {}

        for rpc in self.rpc_list:
            for question_name, metrics in rpc.items():
                if question_name not in best_metrics:
                    best_metrics[question_name] = {}
                for metric_name, metric_value in metrics.items():
                    if metric_value is None:
                        continue
                    if metric_name not in best_metrics[question_name]:
                        best_metrics[question_name][metric_name] = metric_value
                    else:
                        if metric_value > best_metrics[question_name][metric_name]:
                            best_metrics[question_name][metric_name] = metric_value
        return best_metrics

    def _compute_by_question_pareto_frontier(self) -> ParetoFrontier:
        """Compute the pareto frontier of the best metrics.
        
        Returns:
            ParetoFrontier: Object containing which agents achieved best scores for each metric
        """
        best_metrics = self._compute_best_metrics()
        from collections import defaultdict
        pareto_frontier = defaultdict(lambda: defaultdict(list))
        for index, rpc in enumerate(self.rpc_list):
            for question_name, metrics in rpc.items():
                for metric_name, metric_value in metrics.items():
                    if metric_value is None:
                        continue
                    if best_metrics[question_name][metric_name] == metric_value:
                        pareto_frontier[question_name][metric_name].append(index)
                    
        return ParetoFrontier(pareto_frontier)

    def _compute_scores(self) -> Dict[str, float]:
        """Compute the scores for each agent."""
        from .result_pair_comparison.score_comparison import ScoreComparison
        scores = {}
        for index, rpc in enumerate(self.rpc_list):
            scores[index] = ScoreComparison(rpc).weighted_score()
        return scores

    def _best_agent_by_score(self) -> int:
        """Find the best agent by score."""
        self.scores = self._compute_scores()
        max_score = max(self.scores.values())
        index = next(index for index, score in self.scores.items() if score == max_score)
        return self.rpc_list[index].result_A.agent

    @classmethod
    def example(cls) -> 'EvaluateAgentsAgainstGold':
        """Return an example EvaluateAgentsAgainstGold instance.        
        """
        from ..comparisons import ResultPairComparison
        rc1 = ResultPairComparison.example(first_index=0, second_index=2)
        rc2 = ResultPairComparison.example(first_index=1, second_index=2)
        rc1.result_A.agent.name = {'name':"Agent 1"}
        rc2.result_A.agent.name = {'name':"Agent 1"}
        return cls(result_pair_comparison_list=[rc1, rc2])


if __name__ == "__main__":
    eag = EvaluateAgentsAgainstGold.example()
    print(eag.evaluate())

    print(eag._compute_best_metrics())

        