# /// script
# dependencies = [
#   "pandas",
#   "altair",
# ]
# ///

import random
from typing import Optional
from edsl import ScenarioList, QuestionFreeText, Agent
from edsl.utilities.local_results_cache import local_results_cache
from rich.console import Console
from rich.table import Table


## Idea: See where it fails on the gold standard & ask what would have to be changed in the prompt to
## make it closer. Lamarkian evolution, in a nutshell.

binary_instructions = [
    "Combine these two personas by weaving them together",
]


class CandidateAgent:
    def __init__(self, persona: str, name: str):
        self.persona = persona
        self.name = name
        self._performance_history = []
        self._optimization_history = []

    def __str__(self):
        return self.persona

    def __repr__(self):
        return f"CandidateAgent(name={self.name}, persona={self.persona})"

    def __eq__(self, other):
        return self.persona == other.persona

    def record_performance(self, comparison_result, gold_standard_dict, metrics_dict):
        """Record performance metrics for analysis.

        Parameters
        ----------
        comparison_result : ResultPairComparison
            The comparison result object containing metric scores
        gold_standard_dict : dict
            The gold standard answers for evaluation
        metrics_dict : dict
            Aggregated metric scores (e.g., from _aggregated_metrics)
        """
        performance_record = {
            "timestamp": self._get_timestamp(),
            "gold_standard": gold_standard_dict,
            "aggregated_metrics": metrics_dict,
            "per_question_scores": {},
        }

        # Extract per-question metric scores
        comp_dict = comparison_result.compare()
        for question_name, answer_comparison in comp_dict.items():
            question_scores = {}
            for metric_name in answer_comparison.metrics:
                question_scores[metric_name] = answer_comparison[metric_name]
            performance_record["per_question_scores"][question_name] = question_scores

        self._performance_history.append(performance_record)

    def record_optimization(
        self, suggestions_per_question, comprehensive_suggestion, previous_persona
    ):
        """Record optimization steps for analysis.

        Parameters
        ----------
        suggestions_per_question : dict
            Dictionary mapping question names to improvement suggestions
        comprehensive_suggestion : str
            The comprehensive persona improvement suggestion
        previous_persona : str
            The persona before optimization
        """
        optimization_record = {
            "timestamp": self._get_timestamp(),
            "previous_persona": previous_persona,
            "new_persona": self.persona,
            "suggestions_per_question": suggestions_per_question,
            "comprehensive_suggestion": comprehensive_suggestion,
        }
        self._optimization_history.append(optimization_record)

    def get_performance_summary(self):
        """Return summary statistics of agent performance over time.

        Returns
        -------
        dict
            Summary containing performance trends, best/worst metrics, etc.
        """
        if not self._performance_history:
            return {"error": "No performance history recorded"}

        # Calculate performance trends
        summary = {
            "total_evaluations": len(self._performance_history),
            "first_evaluation": self._performance_history[0]["timestamp"],
            "latest_evaluation": self._performance_history[-1]["timestamp"],
            "metric_trends": {},
            "question_performance": {},
            "best_overall_score": None,
            "worst_overall_score": None,
        }

        # Analyze metric trends
        if len(self._performance_history) > 1:
            first_metrics = self._performance_history[0]["aggregated_metrics"]
            latest_metrics = self._performance_history[-1]["aggregated_metrics"]

            for metric_name in first_metrics:
                if isinstance(first_metrics[metric_name], (int, float)) and isinstance(
                    latest_metrics[metric_name], (int, float)
                ):
                    improvement = (
                        latest_metrics[metric_name] - first_metrics[metric_name]
                    )
                    summary["metric_trends"][metric_name] = {
                        "initial": first_metrics[metric_name],
                        "latest": latest_metrics[metric_name],
                        "improvement": improvement,
                        "percent_change": (
                            improvement / first_metrics[metric_name] * 100
                        )
                        if first_metrics[metric_name] != 0
                        else 0,
                    }

        # Calculate overall scores (mean of all metrics)
        overall_scores = []
        for record in self._performance_history:
            metrics = record["aggregated_metrics"]
            numeric_values = [
                v
                for v in metrics.values()
                if isinstance(v, (int, float)) and not (v != v)
            ]  # filter NaN
            if numeric_values:
                overall_scores.append(sum(numeric_values) / len(numeric_values))

        if overall_scores:
            summary["best_overall_score"] = max(overall_scores)
            summary["worst_overall_score"] = min(overall_scores)
            summary["average_overall_score"] = sum(overall_scores) / len(overall_scores)

        return summary

    def get_optimization_summary(self):
        """Return summary of optimization steps taken.

        Returns
        -------
        dict
            Summary of optimization history including common improvement patterns
        """
        if not self._optimization_history:
            return {"error": "No optimization history recorded"}

        summary = {
            "total_optimizations": len(self._optimization_history),
            "first_optimization": self._optimization_history[0]["timestamp"],
            "latest_optimization": self._optimization_history[-1]["timestamp"],
            "common_improvement_themes": {},
            "questions_optimized": set(),
            "persona_evolution": [],
        }

        # Analyze common themes in improvements
        all_suggestions = []
        for record in self._optimization_history:
            for suggestions in record["suggestions_per_question"].values():
                if isinstance(suggestions, list):
                    all_suggestions.extend(suggestions)
                else:
                    all_suggestions.append(suggestions)
            all_suggestions.append(record["comprehensive_suggestion"])

            # Track which questions were optimized
            summary["questions_optimized"].update(
                record["suggestions_per_question"].keys()
            )

            # Track persona evolution
            summary["persona_evolution"].append(
                {
                    "timestamp": record["timestamp"],
                    "persona": record["new_persona"][:100] + "..."
                    if len(record["new_persona"]) > 100
                    else record["new_persona"],
                }
            )

        summary["questions_optimized"] = list(summary["questions_optimized"])

        # Basic theme extraction (count common words in suggestions)
        from collections import Counter
        import re

        # Extract words from all suggestions
        all_text = " ".join(all_suggestions).lower()
        words = re.findall(r"\b\w+\b", all_text)
        # Filter out common words
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "this",
            "that",
            "these",
            "those",
        }
        filtered_words = [w for w in words if len(w) > 3 and w not in stopwords]

        word_counts = Counter(filtered_words)
        summary["common_improvement_themes"] = dict(word_counts.most_common(10))

        return summary

    def _get_timestamp(self):
        """Get current timestamp string."""
        import datetime

        return datetime.datetime.now().isoformat()

    def export_analysis_data(self):
        """Export all performance and optimization data for external analysis.

        Returns
        -------
        dict
            Complete agent history suitable for CSV export or further analysis
        """
        return {
            "agent_name": self.name,
            "current_persona": self.persona,
            "performance_history": self._performance_history,
            "optimization_history": self._optimization_history,
            "performance_summary": self.get_performance_summary(),
            "optimization_summary": self.get_optimization_summary(),
        }


class CandidateAgentList(list):
    def __init__(self, agents: list[CandidateAgent], info: list[str]):
        if len(agents) != len(info):
            raise ValueError("'agents' and 'info' must be the same length")

        # Initialize the underlying list with the agents
        super().__init__(agents)

        # Also keep the agents and info as attributes for backward compatibility
        self.agents = agents
        self.info = info

        assert all(
            [a.name is not None for a in self.agents]
        ), "All agents must have a name"

    def __str__(self):
        return "\n".join([str(agent) for agent in self.agents])

    def show(self):
        """Pretty-print the list of candidate agents as a table."""
        console = Console()
        table = Table(title="Candidate Agents", show_lines=True)
        table.add_column("Info", style="bold magenta")
        table.add_column("Persona", style="green")

        for info, agent in zip(self.info, self.agents):
            table.add_row(str(info), agent.persona)

        console.print(table)

    def apply_instructions(self, instructions: list[str]):
        instructions = (
            ScenarioList.from_list("instruction", instructions)
            .add_list("persona", [agent.persona for agent in self.agents])
            .add_list("name", [agent.name for agent in self.agents])
        )

        job = QuestionFreeText(
            question_text="""Consider this persona: 
            {{scenario.persona}} and apply the following instruction: 
            {{scenario.instruction}}. Just return the new persona, no other text.""",
            question_name="new_persona",
        ).by(instructions)

        with local_results_cache(job) as results:
            # Extract new personas and agent names properly
            new_personas_and_names = []
            for i, result in enumerate(results):
                new_persona = result["answer"]["new_persona"]

                # Try to get agent name from scenario first (this is where it should be)
                agent_name = "unknown_agent"
                try:
                    if "scenario" in result:
                        scenario = result["scenario"]
                        # Scenario acts like a dictionary
                        if "name" in scenario:
                            agent_name = scenario["name"]
                        elif hasattr(scenario, "name") and scenario.name:
                            agent_name = scenario.name
                        elif hasattr(scenario, "get") and scenario.get("name"):
                            agent_name = scenario.get("name")
                except Exception:
                    pass  # Continue to fallback methods

                # Ensure agent_name is not None or empty
                if not agent_name or agent_name == "None":
                    agent_name = f"agent_{i}"

                # Fallback to agent traits if still unknown
                if agent_name == "unknown_agent":
                    try:
                        # Try to get agent name from traits
                        agent_name = result["agent"].traits.get(
                            "agent_name", f"agent_{i}"
                        )
                    except (AttributeError, KeyError):
                        try:
                            # Fallback to direct agent access
                            agent_name = result["agent"].get("agent_name", f"agent_{i}")
                        except (AttributeError, KeyError):
                            agent_name = f"agent_{i}"

                new_personas_and_names.append((new_persona, agent_name))

            new_personas = CandidateAgentList(
                [
                    CandidateAgent(persona=new_persona, name=agent_name)
                    for new_persona, agent_name in new_personas_and_names
                ],
                info=instructions,
            )

        return new_personas

    def take_survey(
        self,
        survey,
        gold_dictionary: dict | None = None,
        comparison_factory: Optional["ComparisonFactory"] = None,
    ):
        """Run *survey* for each candidate agent and optionally compare answers to a
        gold-standard.

        Parameters
        ----------
        survey
            The :class:`edsl.Survey` (e.g. a ``QuestionYesNo`` instance) to be
            administered.
        gold_dictionary
            Mapping *question_name* → *expected_answer* used to build the
            gold-standard result via
            ``survey.gold_standard(gold_dictionary)``.  If *None* (default)
            the function behaves exactly like the previous implementation and
            merely returns the raw :class:`edsl.Results` object.
        comparison_factory
            Optional :class:`~comparisons.factory.ComparisonFactory` instance
            controlling what metrics are computed during comparison. If not
            supplied a default ``ComparisonFactory()`` is created.

        Returns
        -------
        edsl.Results | list[ResultPairComparison]
            When *gold_dictionary* is *None* the raw ``Results`` object is
            returned (maintaining backwards-compatibility). Otherwise a list of
            :class:`~comparisons.results_comparison.ResultPairComparison` objects –
            one per candidate agent – is returned.  Each object bundles the
            raw answers together with the metric scores produced by
            *comparison_factory*.
        """

        # Build and run the survey for all candidate agents
        job = survey.by(
            [
                Agent(traits={"persona": agent.persona, "agent_name": agent.name})
                for agent in self.agents
            ]
        )

        with local_results_cache(job) as results:
            # Default value when no gold-standard is provided
            comparisons = None

            # ------------------------------------------------------------------
            # Gold-standard generation & comparison logic
            # ------------------------------------------------------------------
            if gold_dictionary is not None:
                gold_result = survey.gold_standard(gold_dictionary)

                # Lazily import to avoid heavy dependency cost at module import time
                from .factory import (
                    ComparisonFactory,
                )  # pylint: disable=import-inside-function
                from .result_pair_comparison import (
                    ResultPairComparison,
                )  # pylint: disable=import-inside-function

                if comparison_factory is None:
                    comparison_factory = ComparisonFactory()

                # Compare each candidate's answers to the gold-standard
                comparisons = ResultPairComparisonList(
                    [
                        ResultPairComparison(res, gold_result, comparison_factory)
                        for res in results  # ``Results`` implements ``__iter__``
                    ],
                    labels=self.info,
                )

            # Return both raw results and optional comparison objects
            return results, comparisons

    def shuffle(self):
        """Shuffle the list of candidate agents."""
        random.shuffle(self.agents)


# ---------------------------------------------------------------------------
# Helper: list-like container for multiple ResultPairComparison objects
# ---------------------------------------------------------------------------


class ResultPairComparisonList(list):
    """Container for multiple :class:`ResultPairComparison` objects with helpful
    rich-display utilities."""

    def __init__(self, comparisons: list, labels: Optional[list[str]] = None):
        super().__init__(comparisons)
        self.labels = labels  # Optional row labels (e.g. agent info)

    # -------------------------------------------
    # Pretty-printing helpers
    # -------------------------------------------

    def show(self, console: Optional[Console] = None):  # Seq of individual tables
        if console is None:
            console = Console()
        for i, comp in enumerate(self):  # type: ignore[index]
            # Extract agent information for the table title
            try:
                agent_data = comp.result_A["agent"]
                agent_name = agent_data.traits.get("agent_name", f"agent_{i+1}")
                persona = agent_data.traits.get("persona", "Unknown persona")

                # Create a descriptive title
                title = f"Agent Comparison: {agent_name}"
                if len(persona) <= 60:
                    title += f" - {persona}"
                else:
                    title += f" - {persona[:57]}..."

                # Use the modified to_table method with title
                table = comp.to_table(title=title)
                console.print(table)
            except Exception:
                # Fallback to original behavior if agent data extraction fails
                comp.print_table(console)

            console.print()  # blank line between tables

    # Aggregate one big table --------------------------------------------------

    def _metric_vectors(self):
        """Return list of flattened metric vectors for each comparison.

        Each vector is a dict mapping "{question}::{metric}" → value with no
        across-question aggregation. NaNs are preserved."""
        if not self:
            return []

        # Determine metric names
        metric_names: list[str] = [
            str(fn) for fn in self[0].comparison_factory.comparison_fns  # type: ignore[attr-defined]
        ]
        question_keys = list(self[0].compare().keys())  # type: ignore[index]

        vectors: list[dict[str, float]] = []
        for comp in self:
            comp_dict = comp.compare()
            vec: dict[str, float] = {}
            for q in question_keys:
                ac = comp_dict[q]
                for m in metric_names:
                    vec[f"{q}::{m}"] = ac[m]
            vectors.append(vec)
        return vectors

    def summary_table(self):
        """Return a single rich Table summarising metric scores per agent.

        Adds a *Dominated* column (computed using per-question metric vectors)
        and orders rows with the Pareto frontier (non-dominated agents) first."""

        if not self:
            return Table(title="No comparisons")

        # Determine metric columns from first comparison's factory
        comp0 = self[0]  # type: ignore[index]
        metric_names: list[str] = [str(fn) for fn in comp0.comparison_factory.comparison_fns]  # type: ignore[attr-defined]

        # Pre-compute aggregated metric dicts for display
        aggregated_list = self._aggregated_metrics()

        # Compute dominated flags using disaggregated metric vectors -----------
        vectors = self._metric_vectors()
        dominated_flags: list[bool] = []
        for idx_a, vec_a in enumerate(vectors):
            dominated = False
            for idx_b, vec_b in enumerate(vectors):
                if idx_a == idx_b:
                    continue
                if self._dominates(vec_b, vec_a):
                    dominated = True
                    break
            dominated_flags.append(dominated)

        # Sort indices: non-dominated (False) first, then dominated (True)
        sorted_indices = sorted(range(len(self)), key=lambda i: dominated_flags[i])

        # -----------------------------------------------------------------------
        table = Table(title="Agent Scores vs Gold Standard", show_lines=True)

        table.add_column("Agent", style="bold magenta")
        table.add_column("Pareto", justify="center")
        for m in metric_names:
            table.add_column(m.replace("_", " ").title(), justify="right")

        # Helper for NaN check
        def _isnan(x):
            return x != x

        for idx in sorted_indices:
            aggregated = aggregated_list[idx]
            dominated = dominated_flags[idx]

            # Row label construction same as before
            if self.labels and idx < len(self.labels):
                label_raw = f"{idx + 1}. {self.labels[idx]}"
                max_len = 60
                label = (
                    label_raw
                    if len(label_raw) <= max_len
                    else label_raw[: max_len - 3] + "..."
                )
            else:
                try:
                    persona = self[idx].result_A["agent"].get("persona")  # type: ignore[index]
                except Exception:
                    persona = f"agent_{idx}"
                max_len = 60
                label = (
                    persona
                    if len(str(persona)) <= max_len
                    else str(persona)[: max_len - 3] + "..."
                )

            row = [label, "" if dominated else "*"]
            for m in metric_names:
                val = aggregated[m]
                row.append("-" if _isnan(val) else f"{val:.3f}")
            table.add_row(*row)

        return table

    def show_summary(self, console: Optional[Console] = None):
        if console is None:
            console = Console()
        console.print(self.summary_table())

    # String representation ----------------------------------------------------

    def __str__(self) -> str:  # pragma: no cover – formatting only
        console = Console(width=120, record=True)
        self.show(console)
        return console.export_text()

    __repr__ = __str__  # fall-back

    def _aggregated_metrics(self):
        """Return a list with one aggregated metric dict per comparison.

        The aggregation function mirrors ``summary_table`` (mean of numeric
        metric values, NaN if no numeric values)."""
        if not self:
            return []

        # Determine metric columns from the first comparison's factory
        comp0 = self[0]  # type: ignore[index]
        metric_names: list[str] = [str(fn) for fn in comp0.comparison_factory.comparison_fns]  # type: ignore[attr-defined]

        # Helper for mean of numeric list (avoid numpy dependency)
        def mean(vals):
            numeric_vals = [float(v) for v in vals if isinstance(v, (int, float))]
            return (
                sum(numeric_vals) / len(numeric_vals) if numeric_vals else float("nan")
            )

        aggregated_list: list[dict[str, float]] = []
        for comp in self:
            comp_dict = comp.compare()  # type: ignore[attr-defined]

            # Collect per-metric lists across questions
            metric_to_vals: dict[str, list] = {m: [] for m in metric_names}
            for ac in comp_dict.values():
                for m in metric_names:
                    metric_to_vals[m].append(ac[m])

            # Aggregate (mean)
            aggregated = {m: mean(metric_to_vals[m]) for m in metric_names}
            aggregated_list.append(aggregated)
        return aggregated_list

    def _dominates(
        self, metrics_a: dict[str, float], metrics_b: dict[str, float]
    ) -> bool:
        """Return True if *a* strictly dominates *b* based on comparable numeric metrics.

        A dominates B when it is >= on every **comparable** metric and > on at
        least one. Only finite numeric values (int/float and not NaN) present in
        *both* vectors are considered. Other entries (None, strings, NaN, etc.)
        are ignored for the dominance test. If no comparable metrics exist the
        function returns False."""

        def _is_num(x):
            return isinstance(x, (int, float)) and not (x != x)  # filter NaN

        any_strictly_better = False
        comparable_found = False
        for m, val_a in metrics_a.items():
            val_b = metrics_b.get(m, None)
            if not (_is_num(val_a) and _is_num(val_b)):
                continue  # skip non-numeric or NaN
            comparable_found = True
            if val_a < val_b:
                return False  # worse on at least one metric -> not dominating
            if val_a > val_b:
                any_strictly_better = True
        return comparable_found and any_strictly_better

    def nondominated(self):
        """Return a new ResultPairComparisonList containing only non-dominated comparisons.

        A comparison *i* is dominated if there exists another comparison *j* that is
        at least as good on every aggregated metric and strictly better on at least
        one metric. The returned list preserves the original order of appearance.
        """
        if not self:
            return ResultPairComparisonList([], labels=[])

        aggregated = self._aggregated_metrics()
        non_dom_indices: list[int] = []
        for idx_a, metrics_a in enumerate(aggregated):
            dominated = False
            for idx_b, metrics_b in enumerate(aggregated):
                if idx_a == idx_b:
                    continue
                if self._dominates(metrics_b, metrics_a):
                    dominated = True
                    break
            if not dominated:
                non_dom_indices.append(idx_a)

        comps = [self[i] for i in non_dom_indices]
        lbls = [self.labels[i] for i in non_dom_indices] if self.labels else None
        return ResultPairComparisonList(comps, labels=lbls)

    def nondominated_per_question(self):
        """Return a dict mapping *question* → ResultPairComparisonList of non-dominated agents
        for that particular question (Pareto front computed on that question's
        metric vectors, no cross-question aggregation).
        """
        if not self:
            return {}

        # Determine all question identifiers from first comparison
        first_comp_dict = self[0].compare()  # type: ignore[index]
        question_keys = list(first_comp_dict.keys())

        # Determine metric names from first comparison's factory
        metric_names: list[str] = [
            str(fn) for fn in self[0].comparison_factory.comparison_fns  # type: ignore[attr-defined]
        ]

        per_question_fronts: dict[str, "ResultPairComparisonList"] = {}

        for q in question_keys:
            # Collect metric dictionaries for every comparison for this question
            metric_vectors: list[dict[str, float]] = []
            for comp in self:
                ac = comp.compare()[q]
                metric_vectors.append({m: ac[m] for m in metric_names})

            # Compute nondominated indices for this question
            non_dom_indices: list[int] = []
            for idx_a, vec_a in enumerate(metric_vectors):
                dominated = False
                for idx_b, vec_b in enumerate(metric_vectors):
                    if idx_a == idx_b:
                        continue
                    if self._dominates(vec_b, vec_a):
                        dominated = True
                        break
                if not dominated:
                    non_dom_indices.append(idx_a)

            comps = [self[i] for i in non_dom_indices]
            lbls = [self.labels[i] for i in non_dom_indices] if self.labels else None
            per_question_fronts[q] = ResultPairComparisonList(comps, labels=lbls)

        return per_question_fronts

    def get_performance_analysis(self):
        """Generate comprehensive performance analysis across all agents.

        Returns
        -------
        dict
            Analysis including diversity metrics, performance distributions,
            optimization effectiveness, etc.
        """
        if not self:
            return {"error": "No agents in list"}

        analysis = {
            "population_size": len(self),
            "diversity_metrics": self._calculate_diversity_metrics(),
            "performance_distribution": self._calculate_performance_distribution(),
            "pareto_analysis": self._calculate_pareto_analysis(),
            "optimization_effectiveness": self._calculate_optimization_effectiveness(),
        }

        return analysis

    def _calculate_diversity_metrics(self):
        """Calculate diversity metrics for the agent population."""
        # Get aggregated metrics for all agents
        aggregated = self._aggregated_metrics()
        if not aggregated:
            return {"error": "No metrics available"}

        # Calculate variance and range for each metric
        diversity = {}
        metric_names = list(aggregated[0].keys())

        for metric in metric_names:
            values = [
                agg[metric]
                for agg in aggregated
                if isinstance(agg[metric], (int, float))
                and not (agg[metric] != agg[metric])
            ]
            if values:
                diversity[metric] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "range": max(values) - min(values),
                    "variance": sum(
                        (x - sum(values) / len(values)) ** 2 for x in values
                    )
                    / len(values),
                }

        return diversity

    def _calculate_performance_distribution(self):
        """Calculate performance distribution statistics."""
        aggregated = self._aggregated_metrics()
        if not aggregated:
            return {"error": "No metrics available"}

        # Calculate overall performance scores (mean across metrics)
        overall_scores = []
        for agg in aggregated:
            numeric_values = [
                v for v in agg.values() if isinstance(v, (int, float)) and not (v != v)
            ]
            if numeric_values:
                overall_scores.append(sum(numeric_values) / len(numeric_values))

        if not overall_scores:
            return {"error": "No valid numeric scores"}

        overall_scores.sort()
        n = len(overall_scores)

        return {
            "count": n,
            "mean": sum(overall_scores) / n,
            "median": overall_scores[n // 2]
            if n % 2 == 1
            else (overall_scores[n // 2 - 1] + overall_scores[n // 2]) / 2,
            "min": min(overall_scores),
            "max": max(overall_scores),
            "q1": overall_scores[n // 4],
            "q3": overall_scores[3 * n // 4],
            "std": (sum((x - sum(overall_scores) / n) ** 2 for x in overall_scores) / n)
            ** 0.5,
        }

    def _calculate_pareto_analysis(self):
        """Analyze Pareto frontier characteristics."""
        pareto_agents = self.nondominated()
        pareto_per_question = self.nondominated_per_question()

        return {
            "pareto_frontier_size": len(pareto_agents),
            "pareto_percentage": len(pareto_agents) / len(self) * 100 if self else 0,
            "per_question_pareto_sizes": {
                q: len(agents) for q, agents in pareto_per_question.items()
            },
            "dominated_agents": len(self) - len(pareto_agents),
        }

    def _calculate_optimization_effectiveness(self):
        """Calculate effectiveness of optimization across population."""
        # This would require access to optimization history
        # For now, return basic structure that could be populated
        return {
            "agents_with_optimization_history": 0,
            "average_optimizations_per_agent": 0,
            "optimization_success_rate": 0,
            "common_optimization_patterns": {},
        }

    def export_performance_csv(self, filename: str = None):
        """Export performance data to CSV format.

        Parameters
        ----------
        filename : str, optional
            Output filename. If None, returns CSV string.

        Returns
        -------
        str or None
            CSV string if filename is None, otherwise writes to file
        """
        import csv
        import io

        # Prepare data for CSV export
        rows = []

        # Get metric names from first comparison
        if not self:
            return "No data to export"

        metric_names = (
            list(self._aggregated_metrics()[0].keys())
            if self._aggregated_metrics()
            else []
        )

        # Header row
        header = (
            ["agent_index", "agent_name", "persona_preview"]
            + metric_names
            + ["overall_score", "pareto_optimal"]
        )
        rows.append(header)

        # Get aggregated metrics and pareto status
        aggregated = self._aggregated_metrics()
        pareto_agents = self.nondominated()
        pareto_indices = {id(comp): True for comp in pareto_agents}

        # Data rows
        for idx, comp in enumerate(self):
            try:
                # Extract agent info
                agent_obj = comp.result_A["agent"]
                agent_name = agent_obj.get("agent_name", f"agent_{idx}")
                persona = (
                    str(agent_obj.get("persona", ""))[:50] + "..."
                    if len(str(agent_obj.get("persona", ""))) > 50
                    else str(agent_obj.get("persona", ""))
                )
            except:
                agent_name = f"agent_{idx}"
                persona = "Unknown"

            # Metric values
            row = [idx, agent_name, persona]

            if idx < len(aggregated):
                agg = aggregated[idx]
                for metric in metric_names:
                    row.append(agg.get(metric, "NaN"))

                # Overall score (mean of numeric metrics)
                numeric_values = [
                    v
                    for v in agg.values()
                    if isinstance(v, (int, float)) and not (v != v)
                ]
                overall_score = (
                    sum(numeric_values) / len(numeric_values)
                    if numeric_values
                    else "NaN"
                )
                row.append(overall_score)
            else:
                # Fill with NaN if no metrics available
                row.extend(["NaN"] * (len(metric_names) + 1))

            # Pareto optimal status
            is_pareto = id(comp) in pareto_indices
            row.append(is_pareto)

            rows.append(row)

        # Generate CSV
        if filename:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            return None
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(rows)
            return output.getvalue()

    def extract_top_agents(
        self,
        method: str = "pareto",
        metric: Optional[str] = None,
        percentage: Optional[float] = None,
        count: Optional[int] = None,
        question: Optional[str] = None,
    ) -> "CandidateAgentList":
        """Extract top performing agents as a new CandidateAgentList.

        Parameters
        ----------
        method : str, default "pareto"
            Selection method. Options:
            - "pareto": Select non-dominated agents (Pareto frontier)
            - "top_percent": Select top percentage of agents based on a metric
            - "top_count": Select top N agents based on a metric
        metric : str, optional
            Metric name to use for ranking (required for "top_percent" and "top_count").
            Should match one of the metric names from the comparison factory.
        percentage : float, optional
            Percentage of top agents to select (0-100, required for "top_percent").
        count : int, optional
            Number of top agents to select (required for "top_count").
        question : str, optional
            Specific question to evaluate metrics on. If None, uses aggregated metrics
            across all questions.

        Returns
        -------
        CandidateAgentList
            New list containing the selected top performing agents.

        Examples
        --------
        >>> # Get Pareto optimal agents
        >>> top_agents = comparisons.extract_top_agents(method="pareto")

        >>> # Get top 10% based on exact_match metric
        >>> top_agents = comparisons.extract_top_agents(
        ...     method="top_percent", metric="exact_match", percentage=10
        ... )

        >>> # Get top 5 agents based on overlap for specific question
        >>> top_agents = comparisons.extract_top_agents(
        ...     method="top_count", metric="overlap",
        ...     count=5, question="nervous"
        ... )
        """
        if not self:
            return CandidateAgentList([], [])

        if method == "pareto":
            if question is not None:
                # Use per-question Pareto frontier
                per_q_fronts = self.nondominated_per_question()
                if question not in per_q_fronts:
                    raise ValueError(f"Question '{question}' not found in results")
                selected_comparisons = per_q_fronts[question]
            else:
                # Use overall Pareto frontier
                selected_comparisons = self.nondominated()

        elif method in ["top_percent", "top_count"]:
            if metric is None:
                raise ValueError(f"'metric' parameter required for method '{method}'")

            # Get metric values for ranking
            if question is not None:
                # Use metric values for specific question
                metric_values = []
                for comp in self:
                    comp_dict = comp.compare()
                    if question not in comp_dict:
                        raise ValueError(
                            f"Question '{question}' not found in comparison results"
                        )
                    metric_values.append(comp_dict[question][metric])
            else:
                # Use aggregated metric values across all questions
                aggregated = self._aggregated_metrics()
                metric_values = [agg[metric] for agg in aggregated]

            # Filter out NaN values and create (value, index) pairs
            valid_pairs = [
                (val, idx)
                for idx, val in enumerate(metric_values)
                if isinstance(val, (int, float)) and not (val != val)  # filter NaN
            ]

            if not valid_pairs:
                return CandidateAgentList([], [])

            # Sort by metric value (descending - higher is better)
            valid_pairs.sort(reverse=True, key=lambda x: x[0])

            if method == "top_percent":
                if percentage is None:
                    raise ValueError(
                        "'percentage' parameter required for method 'top_percent'"
                    )
                if not (0 < percentage <= 100):
                    raise ValueError("'percentage' must be between 0 and 100")

                num_to_select = max(1, int(len(valid_pairs) * percentage / 100))
                selected_indices = [idx for _, idx in valid_pairs[:num_to_select]]

            elif method == "top_count":
                if count is None:
                    raise ValueError(
                        "'count' parameter required for method 'top_count'"
                    )
                if count <= 0:
                    raise ValueError("'count' must be positive")

                num_to_select = min(count, len(valid_pairs))
                selected_indices = [idx for _, idx in valid_pairs[:num_to_select]]

            # Create ResultPairComparisonList with selected indices
            selected_comps = [self[i] for i in selected_indices]
            selected_labels = (
                [self.labels[i] for i in selected_indices] if self.labels else None
            )
            selected_comparisons = ResultPairComparisonList(
                selected_comps, labels=selected_labels
            )

        else:
            raise ValueError(
                f"Unknown method '{method}'. Use 'pareto', 'top_percent', or 'top_count'"
            )

        # Extract agents from selected comparisons
        agents = []
        info = []

        for idx, comp in enumerate(selected_comparisons):
            # Extract persona and name from the agent
            try:
                # First try accessing as dictionary (if result is already converted)
                persona = comp.result_A["agent"].get("persona", f"agent_{idx}")
                name = comp.result_A["agent"].get("agent_name", f"agent_{idx}")
            except (AttributeError, KeyError, TypeError):
                try:
                    # Try accessing as Agent object with traits
                    agent_obj = comp.result_A["agent"]
                    persona = agent_obj.traits.get("persona", f"agent_{idx}")
                    name = agent_obj.traits.get("agent_name", f"agent_{idx}")
                except (AttributeError, KeyError, TypeError):
                    persona = f"agent_{idx}"
                    name = f"agent_{idx}"

            agents.append(CandidateAgent(persona=str(persona), name=str(name)))

            # Use existing label or create descriptive info
            if selected_comparisons.labels and idx < len(selected_comparisons.labels):
                info.append(selected_comparisons.labels[idx])
            else:
                info.append(f"top_performer_{idx + 1}")

        return CandidateAgentList(agents, info)


if __name__ == "__main__":
    from edsl import QuestionCheckBox, QuestionYesNo, Survey
    from .prompt_adjust import UNARY_INSTRUCTIONS
    from .agent_optimizer import AgentOptimizer

    # Create initial candidate agents
    candidates = [
        CandidateAgent(persona="I like to play basketball", name=f"agent_{i}")
        for i in range(len(UNARY_INSTRUCTIONS))
    ]
    agents = CandidateAgentList(candidates, info=UNARY_INSTRUCTIONS)

    # Apply various persona modifications to create diverse starting agents
    new_agents = agents.apply_instructions(UNARY_INSTRUCTIONS)
    new_agents.show()

    # Define the survey
    q1 = QuestionYesNo(
        question_text="Are you a nervous person?", question_name="nervous"
    )
    q2 = QuestionCheckBox(
        question_text="What are your hobbies?",
        question_name="hobbies",
        question_options=[
            "Basketball",
            "Baseball",
            "Cooking",
            "Reading",
            "Writing",
            "Other",
        ],
    )
    q3 = QuestionYesNo(
        question_text="Have you ever traveled to Puerto Rico?",
        question_name="puerto_rico",
    )
    q4 = QuestionFreeText(
        question_text="What is your favorite color?", question_name="favorite_color"
    )

    survey = Survey([q1, q2, q3, q4])

    # Define gold standard
    gold_dictionary = {
        "nervous": "Yes",
        "hobbies": ["Basketball", "Cooking"],
        "puerto_rico": "Yes",
        "favorite_color": "Chartreuse",
    }

    # Validate that gold_dictionary matches survey questions
    survey_questions = set(q.question_name for q in survey.questions)
    gold_questions = set(gold_dictionary.keys())
    if survey_questions != gold_questions:
        raise ValueError(
            f"Gold dictionary questions {gold_questions} don't match survey questions {survey_questions}"
        )

    print("\n" + "=" * 80)
    print("🚀 AGENT OPTIMIZATION FRAMEWORK DEMO")
    print("=" * 80)

    # Create and run the optimizer
    optimizer = AgentOptimizer(
        survey=survey, gold_standard=gold_dictionary, starting_agents=new_agents
    )

    # Run the complete optimization process
    results = optimizer.optimize(
        optimization_method="pareto",  # Try "all" to optimize every agent
        max_suggestions_per_question=2,
        verbose=False,
        ask_confirmation=False,
    )

    # Access results if needed for further analysis
    print("\n📊 OPTIMIZATION SUMMARY:")
    print(
        f"• Process completed with {len(optimizer.optimization_log)} optimization steps"
    )
    print("• Final optimization log available in results['optimization_log']")
    print("• All data accessible via results dictionary")

    # Example: Access the optimization log
    if optimizer.optimization_log:
        print("\n📝 Sample optimization log entry:")
        first_log = optimizer.optimization_log[0]
        print(f"  Agent: {first_log['agent_name']}")
        print(
            f"  Questions improved: {list(first_log['suggestions_per_question'].keys())}"
        )
        print(
            f"  Comprehensive suggestion: {first_log['comprehensive_suggestion'][:100]}..."
        )

    # ------------------------------------------------------------------
    # Continue with existing visualization functionality if desired
    # ------------------------------------------------------------------

    # # ------------------------------------------------------------------
    # # Vega-Lite visualisation example
    # # ------------------------------------------------------------------
    # # Local (relative) import; will raise ImportError if dependencies missing
    # from .results_comparison_visualization import question_metric_bar, all_question_metric_bars

    # # Plot the 'exact_match' metric for the 'nervous' question
    # bar = question_metric_bar(
    #     comparisons,
    #     question_name="nervous",
    #     metric_name="exact_match",
    #     title="Exact Match – Nervous Question",
    # )

    # # Save to an HTML file for easy viewing (avoid potential altair_saver hang)
    # html_content = bar.to_html()
    # with open("nervous_exact_match_bar.html", "w", encoding="utf-8") as _f:
    #     _f.write(html_content)
    # print("Saved Vega-Lite bar chart to nervous_exact_match_bar.html")

    # # ------------------------------------------------------------------
    # # Facet grid for all questions × metrics
    # # ------------------------------------------------------------------

    # grid = all_question_metric_bars(comparisons)

    # html_grid = grid.to_html()
    # rows = []
    # all_trait_keys: set[str] = set()
    # for idx, comp in enumerate(comparisons):
    #     traits = {}
    #     try:
    #         traits = dict(comp.result_A.agent.traits)  # type: ignore[attr-defined]
    #     except Exception:
    #         try:
    #             traits = dict(comp.result_A["agent"])  # fallback to sub-dict
    #         except Exception:
    #             traits = {}

    #     row = {"Agent": f"agent_{idx + 1}", **traits}
    #     rows.append(row)
    #     all_trait_keys.update(traits.keys())

    # # Ensure consistent column order (Agent first, then sorted trait keys)
    # columns = ["Agent"] + sorted(all_trait_keys)
    # df_personas = _pd.DataFrame(rows, columns=columns).fillna("")
    # table_html = df_personas.to_html(index=False, escape=True)

    # combined_html = html_grid + "<hr><h2>Agent Traits</h2>" + table_html

    # with open("all_metrics_grid.html", "w", encoding="utf-8") as _f:
    #     _f.write(combined_html)
    # print("Saved comprehensive metrics grid to all_metrics_grid.html")
