from __future__ import annotations

"""Compare candidate results against gold standard results."""

from typing import Dict, Any, List, Set, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from edsl import Results
    from edsl.scenarios import ScenarioList

from ..base import Base

# Import helper classes from comparison_helpers module
from .comparison_helpers import (
    ResultPairComparisonList,
    PersonaViewer,
    FullTraitsTable,
    InteractiveQuestionViewer,
    ByQuestionComparison,
    ComparisonPerformanceTable,
)


class CompareResultsToGold(Base):
    """Compare candidate results against gold standard results.

    Takes candidate results and gold standard results, creating pairwise
    comparisons for ranking and analysis.
    """

    def __init__(
        self,
        candidate_results: "Results",
        gold_results: "Results",
        scenario_names: Dict = None,
        excluded_metrics: set = None,
        excluded_questions: set = None,
    ):
        """Initialize with candidate and gold standard results.

        Args:
            candidate_results: Results from candidate agents
            gold_results: Results from gold agents
            scenario_names: Optional dict mapping scenario_index to pretty display names
            excluded_metrics: Optional set of metric names to exclude from comparisons
            excluded_questions: Optional set of question names to exclude from comparisons

        Raises:
            ValueError: If candidate_results contain more than one unique model_index
        """
        self.candidate_results = candidate_results
        self.gold_results = gold_results
        self.scenario_names = scenario_names or {}
        self.excluded_metrics = excluded_metrics or set()
        self.excluded_questions = excluded_questions or set()

        # Validate single model constraint
        import ast

        model_indices = set()
        for result in self.candidate_results:
            naming_dict = ast.literal_eval(result.agent.name)
            model_indices.add(naming_dict["model_index"])

        if len(model_indices) > 1:
            raise ValueError(
                f"CompareResultsToGold only works with a single model. Found {len(model_indices)} different model_indices: {model_indices}"
            )

        self.model_index = model_indices.pop() if model_indices else None

        self.agent_to_gold_results = {}
        for result in self.gold_results:
            agent_name = result.agent.name
            self.agent_to_gold_results[agent_name] = result

        # Build comparisons - will be dict of agent_name -> ResultPairComparisonList
        self.comparisons = {}
        self._build_comparisons()

        # Validate that we found matching agents
        if not self.comparisons:
            # Extract candidate agent names for helpful error message
            candidate_agent_names = set()
            for result in self.candidate_results:
                naming_dict = ast.literal_eval(result.agent.name)
                candidate_agent_names.add(naming_dict["name"])

            gold_agent_names = set(self.agent_to_gold_results.keys())

            raise ValueError(
                f"No matching agents found between candidate results and gold results.\n"
                f"Candidate agent names: {candidate_agent_names}\n"
                f"Gold agent names: {gold_agent_names}\n"
                f"Make sure agent names match between candidate and gold results."
            )

    def __repr__(self):
        return f"CompareResultsToGold: Total # of comparisons = {len(self.comparisons)}"

    def _repr_html_(self) -> str:
        """Return HTML summary representation for Jupyter notebook display."""
        html = [
            '<div style="font-family: Arial, sans-serif; padding: 15px; border: 2px solid #3498db; border-radius: 8px; background-color: #f8f9fa;">'
        ]

        # Title
        html.append(
            '<h2 style="color: #2c3e50; margin-top: 0;">CompareResultsToGold Summary</h2>'
        )

        # Get summary statistics
        num_agents = len(self.comparisons)
        total_comparisons = sum(
            len(comp_list) for comp_list in self.comparisons.values()
        )

        # Get questions and metrics from first comparison
        all_questions = set()
        all_metrics = set()
        for comp_list in self.comparisons.values():
            if len(comp_list) > 0:
                comp = comp_list[0]
                all_questions.update(comp.comparison.keys())
                if hasattr(comp, "comparison_factory") and comp.comparison_factory:
                    all_metrics.update(
                        str(fn) for fn in comp.comparison_factory.comparison_fns
                    )
                if all_questions and all_metrics:
                    break

        # Overview stats
        html.append(
            '<div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">'
        )
        html.append('<h3 style="color: #34495e; margin-top: 0;">Overview</h3>')
        html.append(f"<p><strong>Total Agents:</strong> {num_agents}</p>")
        html.append(
            f"<p><strong>Total Candidate Comparisons:</strong> {total_comparisons}</p>"
        )
        html.append(f"<p><strong>Total Questions:</strong> {len(all_questions)}</p>")
        html.append(f"<p><strong>Total Metrics:</strong> {len(all_metrics)}</p>")
        if self.excluded_metrics:
            html.append(
                f'<p><strong>Excluded Metrics:</strong> {", ".join(sorted(self.excluded_metrics))}</p>'
            )
        if self.excluded_questions:
            html.append(
                f'<p><strong>Excluded Questions:</strong> {", ".join(sorted(self.excluded_questions))}</p>'
            )
        html.append("</div>")

        # Agents table
        html.append(
            '<div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">'
        )
        html.append(
            '<h3 style="color: #34495e; margin-top: 0;">Agents & Candidates</h3>'
        )
        html.append(
            '<table style="border-collapse: collapse; width: 100%; border: 1px solid #ddd;">'
        )
        html.append('<thead><tr style="background-color: #3498db; color: white;">')
        html.append(
            '<th style="border: 1px solid #2980b9; padding: 10px; text-align: left;">Agent Name</th>'
        )
        html.append(
            '<th style="border: 1px solid #2980b9; padding: 10px; text-align: center;">Number of Candidates</th>'
        )
        html.append("</tr></thead>")
        html.append("<tbody>")

        for idx, (agent_name, comp_list) in enumerate(sorted(self.comparisons.items())):
            row_bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            html.append(f'<tr style="background-color: {row_bg};">')
            html.append(
                f'<td style="border: 1px solid #ddd; padding: 8px;">{agent_name}</td>'
            )
            html.append(
                f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{len(comp_list)}</td>'
            )
            html.append("</tr>")

        html.append("</tbody></table>")
        html.append("</div>")

        # Questions preview
        if all_questions:
            html.append(
                '<div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">'
            )
            html.append('<h3 style="color: #34495e; margin-top: 0;">Questions</h3>')

            sorted_questions = sorted(all_questions)
            if len(sorted_questions) <= 5:
                # Show all if 5 or fewer
                html.append(
                    "<p>"
                    + ", ".join(f"<code>{q}</code>" for q in sorted_questions)
                    + "</p>"
                )
            else:
                # Show first 5 and indicate more
                html.append(
                    "<p>" + ", ".join(f"<code>{q}</code>" for q in sorted_questions[:5])
                )
                html.append(f" ... and {len(sorted_questions) - 5} more</p>")

            html.append("</div>")

        # Metrics
        if all_metrics:
            html.append(
                '<div style="background-color: white; padding: 15px; border-radius: 5px;">'
            )
            html.append('<h3 style="color: #34495e; margin-top: 0;">Metrics</h3>')

            sorted_metrics = sorted(all_metrics)
            html.append('<ul style="margin: 0; padding-left: 20px;">')
            for metric in sorted_metrics:
                html.append(f"<li><code>{metric}</code></li>")
            html.append("</ul>")
            html.append("</div>")

        # Available methods
        html.append(
            '<div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin-top: 15px;">'
        )
        html.append(
            '<h3 style="color: #34495e; margin-top: 0;">📚 Available Methods</h3>'
        )
        html.append('<ul style="margin: 0; padding-left: 20px;">')
        html.append(
            "<li><code>.by_question()</code> - Browse all questions interactively</li>"
        )
        html.append(
            '<li><code>.by_question("q_name")</code> - View specific question comparison</li>'
        )
        html.append(
            "<li><code>.comparison_performance_table()</code> - View performance metrics table</li>"
        )
        html.append(
            "<li><code>.comparisons[agent_name]</code> - Access specific agent comparisons</li>"
        )
        html.append("<li><code>.rank()</code> - Get ranking results</li>")
        html.append(
            "<li><code>.summarize_rankings()</code> - Get summary statistics</li>"
        )
        html.append("</ul>")
        html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    @property
    def agents(self) -> List[str]:
        return list(self.comparisons.keys())

    def get_comparisons(self, agent_name: str) -> ResultPairComparisonList:
        """Get a ResultPairComparisonList for the specified agent.

        Args:
            agent_name: The agent to get comparisons for (required).

        Returns:
            ResultPairComparisonList object with wrapped comparisons

        Raises:
            ValueError: If agent_name is not found

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> agent_name = crtg.agents[0]  # Get an agent name first
            >>> comp_list = crtg.get_comparisons(agent_name)
            >>> personas = comp_list.show_personas()  # Simple persona text viewer
            >>> full_traits = comp_list.show_full_traits()  # Full traits table
        """
        if agent_name not in self.comparisons:
            available = list(self.comparisons.keys())
            raise ValueError(
                f"Agent '{agent_name}' not found. Available agents: {available}"
            )

        return ResultPairComparisonList(
            self.comparisons[agent_name], agent_name=agent_name
        )

    def _filter_comparison_questions(self, comparison):
        """Filter a ResultPairComparison to exclude certain questions.

        Args:
            comparison: A ResultPairComparison object to filter

        Returns:
            The same ResultPairComparison with its comparison dict filtered
        """
        # Filter the comparison dictionary in-place
        comparison.comparison = {
            k: v
            for k, v in comparison.comparison.items()
            if k not in self.excluded_questions
        }
        return comparison

    def _build_comparisons(self):
        """Build ResultPairComparison objects for each candidate-gold pair."""
        from .result_pair_comparison import ResultPairComparison
        from .factory import ComparisonFactory
        import ast

        # Create a filtered comparison factory if there are excluded metrics
        comparison_factory = None
        if self.excluded_metrics:
            # Start with default factory
            default_factory = ComparisonFactory.with_defaults()
            # Filter out excluded metrics
            filtered_fns = [
                fn
                for fn in default_factory.comparison_fns
                if str(fn) not in self.excluded_metrics
            ]
            comparison_factory = ComparisonFactory(filtered_fns)

        # Temporary dict to collect comparisons
        temp_comparisons = defaultdict(list)

        for result in self.candidate_results:
            full_agent_name = result.agent.name
            naming_dict = ast.literal_eval(full_agent_name)
            scenario_index = naming_dict["scenario_index"]
            model_index = naming_dict["model_index"]
            name = naming_dict["name"]

            if name not in self.agent_to_gold_results:
                available_names = list(self.agent_to_gold_results.keys())
                raise ValueError(
                    f"Agent '{name}' from candidate results not found in gold results.\n"
                    f"Available gold agent names: {available_names}\n"
                    f"Candidate agent full name: {full_agent_name}"
                )

            gold_result = self.agent_to_gold_results[name]

            # Create the comparison
            rpc = ResultPairComparison(
                result, gold_result, comparison_factory=comparison_factory
            )

            # Filter questions if needed
            if self.excluded_questions:
                rpc = self._filter_comparison_questions(rpc)

            temp_comparisons[name].append(rpc)

        # Wrap each list in a ResultPairComparisonList
        for agent_name, comparison_list in temp_comparisons.items():
            self.comparisons[agent_name] = ResultPairComparisonList(
                comparison_list, agent_name=agent_name
            )

    def by_question(self, question_name: str = None):
        """Create a table showing candidate answers vs gold standard for question(s).

        If question_name is provided, shows that specific question. If question_name is None,
        returns an interactive viewer to click through all questions in the survey.

        Args:
            question_name: Optional. The specific question to display. If None, shows
                          an interactive viewer for all questions.

        Returns:
            ByQuestionComparison if question_name is provided, otherwise InteractiveQuestionViewer

        Raises:
            ValueError: If specific question_name is not found in any comparisons

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>>
            >>> # Interactive viewer for all questions
            >>> viewer = crtg.by_question()  # Click through all questions
            >>>
            >>> # Specific question
            >>> table = crtg.by_question("how_feeling")  # Just one question
        """
        # If no question specified, create interactive viewer for all questions
        if question_name is None:
            return self._create_interactive_question_viewer()

        # Collect data for specific question across all agents and candidates
        agent_data = {}
        question_found = False
        question_text = None

        for agent_name, comparison_list in self.comparisons.items():
            candidates = []

            for idx, comp in enumerate(comparison_list):
                # Check if this question exists in the comparison
                if question_name in comp.comparison:
                    question_found = True

                    # Get question text if available (access as attribute, not dict key)
                    if question_text is None:
                        try:
                            question_text = comp.comparison[question_name].question_text
                        except (AttributeError, KeyError):
                            question_text = ""

                    # Get candidate answer (result_A)
                    candidate_answer = comp.comparison[question_name].answer_a

                    # Get gold answer (result_B)
                    gold_answer = comp.comparison[question_name].answer_b

                    candidates.append((idx, candidate_answer, gold_answer))

            if candidates:
                agent_data[agent_name] = candidates

        if not question_found:
            raise ValueError(f"Question '{question_name}' not found in any comparisons")

        return ByQuestionComparison(question_name, question_text or "", agent_data)

    def _create_interactive_question_viewer(self) -> InteractiveQuestionViewer:
        """Create an interactive viewer for all questions in the survey.

        Returns:
            InteractiveQuestionViewer with all questions
        """
        # Collect all questions and their data
        all_questions = {}

        for agent_name, comparison_list in self.comparisons.items():
            for comp in comparison_list:
                for question_name in comp.comparison.keys():
                    if question_name not in all_questions:
                        # Initialize this question
                        try:
                            question_text = comp.comparison[question_name].question_text
                        except (AttributeError, KeyError):
                            question_text = ""
                        all_questions[question_name] = (question_text, {})

        # Now collect agent data for each question
        for question_name in all_questions.keys():
            agent_data = {}

            for agent_name, comparison_list in self.comparisons.items():
                candidates = []

                for idx, comp in enumerate(comparison_list):
                    if question_name in comp.comparison:
                        candidate_answer = comp.comparison[question_name].answer_a
                        gold_answer = comp.comparison[question_name].answer_b
                        candidates.append((idx, candidate_answer, gold_answer))

                if candidates:
                    agent_data[agent_name] = candidates

            # Update the question data with agent_data
            question_text = all_questions[question_name][0]
            all_questions[question_name] = (question_text, agent_data)

        return InteractiveQuestionViewer(all_questions)

    def comparison_performance_table(
        self, agent_name: str = None
    ) -> ComparisonPerformanceTable:
        """Create a table showing which candidates perform best on each question-metric combination.

        For each agent's list of ResultPairComparison objects (candidates), creates a table
        where rows are candidates and columns are question-metric pairs. Cells are highlighted
        green if that candidate is the best (or tied for best) on that dimension.

        Args:
            agent_name: The agent to analyze. If None, analyzes all agents.

        Returns:
            ComparisonPerformanceTable object that can be displayed as HTML or Rich table

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> table = crtg.comparison_performance_table()
            >>> # In Jupyter: displays as HTML table automatically
            >>> # In terminal: table.print()
        """
        if not self.comparisons:
            raise ValueError("No comparisons available")

        # Determine which agents to process
        if agent_name is None:
            agents_to_process = list(self.comparisons.keys())
        else:
            if agent_name not in self.comparisons:
                available = list(self.comparisons.keys())
                raise ValueError(
                    f"Agent '{agent_name}' not found. Available agents: {available}"
                )
            agents_to_process = [agent_name]

        # Collect all questions and metrics across all agents
        all_questions = set()
        all_metrics = set()

        for agent in agents_to_process:
            comparisons_list = self.comparisons[
                agent
            ].comparisons  # Access the list from ResultPairComparisonList
            for comp in comparisons_list:
                all_questions.update(comp.comparison.keys())
                if hasattr(comp, "comparison_factory") and comp.comparison_factory:
                    for fn in comp.comparison_factory.comparison_fns:
                        all_metrics.add(str(fn))

        all_questions = sorted(all_questions)
        metric_names = sorted(all_metrics)

        if not all_questions:
            raise ValueError("No questions found in comparisons")

        # Build data structure for all agents
        agent_data = {}
        best_performers_by_agent = {}

        for agent in agents_to_process:
            comparisons_list = self.comparisons[
                agent
            ].comparisons  # Access the list from ResultPairComparisonList

            # Build the data structure: comparison_idx -> question -> metric -> value
            data = {}
            for idx, comp in enumerate(comparisons_list):
                data[idx] = {}
                for q in all_questions:
                    data[idx][q] = {}
                    if q in comp.comparison:
                        for m in metric_names:
                            try:
                                value = comp.comparison[q][m]
                                data[idx][q][m] = value
                            except (KeyError, TypeError):
                                data[idx][q][m] = None
                    else:
                        for m in metric_names:
                            data[idx][q][m] = None

            # Find best performers for this agent
            best_performers = {}
            for q in all_questions:
                for m in metric_names:
                    values = []
                    for idx in data:
                        val = data[idx][q][m]
                        if val is not None:
                            try:
                                values.append((idx, float(val)))
                            except (TypeError, ValueError):
                                pass

                    if values:
                        max_val = max(v[1] for v in values)
                        best_performers[(q, m)] = {
                            idx for idx, val in values if val == max_val
                        }
                    else:
                        best_performers[(q, m)] = set()

            agent_data[agent] = data
            best_performers_by_agent[agent] = best_performers

        # Create and return the performance table object
        return ComparisonPerformanceTable(
            agent_data=agent_data,
            questions=all_questions,
            metrics=metric_names,
            best_performers=best_performers_by_agent,
        )

    def example_comparison(self, agent_name: str = None, comparison_index: int = None):
        """Return a randomly selected ResultPairComparison object.

        Randomly selects an agent (or uses the specified agent) and returns one of their
        ResultPairComparison objects. Useful for quickly inspecting example comparisons.

        Args:
            agent_name: If provided, selects from this agent's comparisons. If None,
                       randomly selects an agent from available agents.
            comparison_index: If provided, returns the comparison at this index for the
                            selected agent. If None, randomly selects one.

        Returns:
            ResultPairComparison object for the selected agent

        Raises:
            ValueError: If no comparisons are available or if specified agent_name or
                       comparison_index is not found

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> from edsl import Results
            >>> # Create a simple example (would need actual Results data)
            >>> # crtg = CompareResultsToGold(candidate_results, gold_results)
            >>> # comp = crtg.example_comparison()
            >>> # isinstance(comp, ResultPairComparison)
            >>> # True
        """
        import random

        if not self.comparisons:
            raise ValueError("No comparisons available")

        # Select agent
        if agent_name is None:
            agent_name = random.choice(list(self.comparisons.keys()))
        elif agent_name not in self.comparisons:
            available = list(self.comparisons.keys())
            raise ValueError(
                f"Agent '{agent_name}' not found. Available agents: {available}"
            )

        comparisons_list = self.comparisons[
            agent_name
        ]  # This is a ResultPairComparisonList

        if not comparisons_list:
            raise ValueError(f"No comparisons found for agent '{agent_name}'")

        # Select comparison (ResultPairComparisonList supports indexing and len)
        if comparison_index is None:
            comparison = random.choice(comparisons_list.comparisons)
        else:
            if comparison_index < 0 or comparison_index >= len(comparisons_list):
                raise ValueError(
                    f"comparison_index {comparison_index} out of range. "
                    f"Agent '{agent_name}' has {len(comparisons_list)} comparisons "
                    f"(valid indices: 0-{len(comparisons_list)-1})"
                )
            comparison = comparisons_list[comparison_index]

        return comparison

    def rank(self) -> "ScenarioList":
        """Compare all pairs of candidates for each agent and return aggregated results.

        Returns:
            ScenarioList with comparison results for all candidate pairs, including
            metadata about which agents and candidates were compared.
        """
        from itertools import combinations
        from .compare_candidates import CompareCandidates
        from edsl import ScenarioList
        import ast

        all_scenarios = []

        for agent_name, comparison_list in self.comparisons.items():
            # Get all pairs of ResultPairComparison objects for this agent
            for idx, (comp_a, comp_b) in enumerate(combinations(comparison_list, 2)):
                # Extract candidate metadata from agent names
                agent_name_a = comp_a.result_A.agent.name
                agent_name_b = comp_b.result_A.agent.name

                naming_dict_a = ast.literal_eval(agent_name_a)
                naming_dict_b = ast.literal_eval(agent_name_b)

                scenario_idx_1 = naming_dict_a["scenario_index"]
                scenario_idx_2 = naming_dict_b["scenario_index"]

                # Use pretty names if available, otherwise use indices
                candidate_1_id = self.scenario_names.get(scenario_idx_1, scenario_idx_1)
                candidate_2_id = self.scenario_names.get(scenario_idx_2, scenario_idx_2)

                # Create CompareCandidates to compare these two candidates
                cc = CompareCandidates(comp_a, comp_b)
                scenario_list = cc.compare()

                # Add metadata about which agent and candidate indices
                for scenario in scenario_list:
                    scenario["agent_name"] = agent_name
                    scenario["comparison_pair_index"] = idx
                    scenario["candidate_1_id"] = str(candidate_1_id)
                    scenario["candidate_2_id"] = str(candidate_2_id)
                    all_scenarios.append(scenario)

        return ScenarioList(all_scenarios)

    def summarize_rankings(self) -> "ScenarioList":
        """Summarize ranking results by counting wins and ties for each candidate pair.

        Returns:
            ScenarioList with one row per agent and candidate pair, showing:
            - agent_name: The base agent name
            - candidate_1_id: scenario_index or pretty name for first candidate
            - candidate_2_id: scenario_index or pretty name for second candidate
            - num_ties: Number of metrics where candidates tied
            - num_candidate_1_wins: Number of metrics where candidate 1 won
            - num_candidate_2_wins: Number of metrics where candidate 2 won
            - winner_id: scenario_index or pretty name of the winner based on net wins, or 'tie'
        """
        from edsl import ScenarioList, Scenario

        # Get detailed rankings
        rankings = self.rank()

        # Group by (agent_name, candidate_1_id, candidate_2_id)
        summary_data = defaultdict(
            lambda: {"ties": 0, "candidate_1_wins": 0, "candidate_2_wins": 0}
        )

        for scenario in rankings:
            key = (
                scenario["agent_name"],
                scenario["candidate_1_id"],
                scenario["candidate_2_id"],
            )
            winner = scenario["winner"]

            if winner == "tie":
                summary_data[key]["ties"] += 1
            elif winner == "candidate_1":
                summary_data[key]["candidate_1_wins"] += 1
            elif winner == "candidate_2":
                summary_data[key]["candidate_2_wins"] += 1

        # Convert to ScenarioList
        summary_scenarios = []
        for (
            agent_name,
            candidate_1_id,
            candidate_2_id,
        ), counts in summary_data.items():
            # Determine overall winner based on net wins
            net_wins = counts["candidate_1_wins"] - counts["candidate_2_wins"]
            if net_wins > 0:
                winner_id = candidate_1_id
            elif net_wins < 0:
                winner_id = candidate_2_id
            else:
                winner_id = "tie"

            row = {
                "agent_name": agent_name,
                "candidate_1_id": candidate_1_id,
                "candidate_2_id": candidate_2_id,
                "num_ties": counts["ties"],
                "num_candidate_1_wins": counts["candidate_1_wins"],
                "num_candidate_2_wins": counts["candidate_2_wins"],
                "winner_id": winner_id,
            }
            summary_scenarios.append(Scenario(row))

        return ScenarioList(summary_scenarios)

    def aggregate_across_agents(self) -> "ScenarioList":
        """Aggregate rankings across all agents, showing only candidate pair comparisons.

        Returns:
            ScenarioList with one row per candidate pair (collapsed across agents), showing:
            - candidate_1_id: scenario_index or pretty name for first candidate
            - candidate_2_id: scenario_index or pretty name for second candidate
            - num_agents: Number of agents in this comparison
            - num_ties: Total number of metric ties across all agents
            - num_candidate_1_wins: Total number of candidate 1 wins across all agents
            - num_candidate_2_wins: Total number of candidate 2 wins across all agents
            - winner_id: scenario_index or pretty name of the winner based on net wins, or 'tie'
        """
        from edsl import ScenarioList, Scenario

        # Get detailed rankings
        rankings = self.rank()

        # Group by (candidate_1_id, candidate_2_id) only - collapse agents
        aggregated_data = defaultdict(
            lambda: {
                "ties": 0,
                "candidate_1_wins": 0,
                "candidate_2_wins": 0,
                "agents": set(),
            }
        )

        for scenario in rankings:
            key = (scenario["candidate_1_id"], scenario["candidate_2_id"])
            winner = scenario["winner"]

            aggregated_data[key]["agents"].add(scenario["agent_name"])

            if winner == "tie":
                aggregated_data[key]["ties"] += 1
            elif winner == "candidate_1":
                aggregated_data[key]["candidate_1_wins"] += 1
            elif winner == "candidate_2":
                aggregated_data[key]["candidate_2_wins"] += 1

        # Convert to ScenarioList
        aggregated_scenarios = []
        for (candidate_1_id, candidate_2_id), counts in aggregated_data.items():
            # Determine overall winner based on net wins
            net_wins = counts["candidate_1_wins"] - counts["candidate_2_wins"]
            if net_wins > 0:
                winner_id = candidate_1_id
            elif net_wins < 0:
                winner_id = candidate_2_id
            else:
                winner_id = "tie"

            row = {
                "candidate_1_id": candidate_1_id,
                "candidate_2_id": candidate_2_id,
                "num_agents": len(counts["agents"]),
                "num_ties": counts["ties"],
                "num_candidate_1_wins": counts["candidate_1_wins"],
                "num_candidate_2_wins": counts["candidate_2_wins"],
                "winner_id": winner_id,
            }
            aggregated_scenarios.append(Scenario(row))

        return ScenarioList(aggregated_scenarios)

    def condorcet_winner(self) -> Dict:
        """Determine the Condorcet winner from pairwise comparisons.

        A Condorcet winner is a candidate that wins all head-to-head matchups
        against every other candidate.

        Returns:
            dict with keys:
            - 'winner': The candidate_id of the Condorcet winner, or None if no winner exists
            - 'pairwise_wins': Dict mapping each candidate to list of candidates they beat
            - 'win_counts': Dict mapping each candidate to their total number of wins
        """
        # Get aggregated pairwise results
        aggregated = self.aggregate_across_agents()

        # Build win matrix
        pairwise_wins = defaultdict(set)
        all_candidates = set()

        for scenario in aggregated:
            cand_1 = scenario["candidate_1_id"]
            cand_2 = scenario["candidate_2_id"]
            winner = scenario["winner_id"]

            all_candidates.add(cand_1)
            all_candidates.add(cand_2)

            if winner == cand_1:
                pairwise_wins[cand_1].add(cand_2)
            elif winner == cand_2:
                pairwise_wins[cand_2].add(cand_1)
            # If tie, neither gets credit for winning

        # Find Condorcet winner (beats all other candidates)
        condorcet_winner = None
        for candidate in all_candidates:
            opponents = all_candidates - {candidate}
            if opponents.issubset(pairwise_wins[candidate]):
                condorcet_winner = candidate
                break

        # Convert sets to lists for cleaner output
        pairwise_wins_dict = {k: list(v) for k, v in pairwise_wins.items()}
        win_counts = {k: len(v) for k, v in pairwise_wins.items()}

        return {
            "winner": condorcet_winner,
            "pairwise_wins": pairwise_wins_dict,
            "win_counts": win_counts,
        }

    def drop_metrics(self, *metric_names: str) -> "CompareResultsToGold":
        """Return a new CompareResultsToGold instance with specified metrics excluded.

        Args:
            *metric_names: Comma-separated metric names to exclude from comparisons

        Returns:
            New CompareResultsToGold instance with the specified metrics excluded

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg_filtered = crtg.drop_metrics("exact_match", "cosine_similarity")
            >>> isinstance(crtg_filtered, CompareResultsToGold)
            True
        """
        # Parse comma-separated list if provided as single string
        metrics_to_drop = set()
        for name in metric_names:
            if "," in name:
                # Split by comma and strip whitespace
                metrics_to_drop.update(m.strip() for m in name.split(","))
            else:
                metrics_to_drop.add(name.strip())

        # Combine with existing excluded metrics
        new_excluded_metrics = self.excluded_metrics | metrics_to_drop

        # Create new instance with updated exclusions
        return CompareResultsToGold(
            candidate_results=self.candidate_results,
            gold_results=self.gold_results,
            scenario_names=self.scenario_names,
            excluded_metrics=new_excluded_metrics,
            excluded_questions=self.excluded_questions,
        )

    def drop_questions(self, *question_names: str) -> "CompareResultsToGold":
        """Return a new CompareResultsToGold instance with specified questions excluded.

        Args:
            *question_names: Comma-separated question names to exclude from comparisons

        Returns:
            New CompareResultsToGold instance with the specified questions excluded

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg_filtered = crtg.drop_questions("q0", "q1")
            >>> isinstance(crtg_filtered, CompareResultsToGold)
            True
        """
        # Parse comma-separated list if provided as single string
        questions_to_drop = set()
        for name in question_names:
            if "," in name:
                # Split by comma and strip whitespace
                questions_to_drop.update(q.strip() for q in name.split(","))
            else:
                questions_to_drop.add(name.strip())

        # Combine with existing excluded questions
        new_excluded_questions = self.excluded_questions | questions_to_drop

        # Create new instance with updated exclusions
        return CompareResultsToGold(
            candidate_results=self.candidate_results,
            gold_results=self.gold_results,
            scenario_names=self.scenario_names,
            excluded_metrics=self.excluded_metrics,
            excluded_questions=new_excluded_questions,
        )

    def keep_metrics(self, *metric_names: str) -> "CompareResultsToGold":
        """Return a new CompareResultsToGold instance keeping only specified metrics.

        This is the inverse of drop_metrics - all metrics except the specified ones
        will be excluded.

        Args:
            *metric_names: Comma-separated metric names to keep in comparisons

        Returns:
            New CompareResultsToGold instance with only the specified metrics

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg_filtered = crtg.keep_metrics("exact_match", "cosine_similarity")
            >>> isinstance(crtg_filtered, CompareResultsToGold)
            True
        """
        from .factory import ComparisonFactory

        # Parse comma-separated list if provided as single string
        metrics_to_keep = set()
        for name in metric_names:
            if "," in name:
                # Split by comma and strip whitespace
                metrics_to_keep.update(m.strip() for m in name.split(","))
            else:
                metrics_to_keep.add(name.strip())

        # Get all available metrics from default factory
        default_factory = ComparisonFactory.with_defaults()
        all_metrics = {str(fn) for fn in default_factory.comparison_fns}

        # Calculate which metrics to exclude (all metrics - kept metrics)
        new_excluded_metrics = (all_metrics - metrics_to_keep) | self.excluded_metrics

        # Create new instance with updated exclusions
        return CompareResultsToGold(
            candidate_results=self.candidate_results,
            gold_results=self.gold_results,
            scenario_names=self.scenario_names,
            excluded_metrics=new_excluded_metrics,
            excluded_questions=self.excluded_questions,
        )

    def keep_questions(self, *question_names: str) -> "CompareResultsToGold":
        """Return a new CompareResultsToGold instance keeping only specified questions.

        This is the inverse of drop_questions - all questions except the specified ones
        will be excluded.

        Args:
            *question_names: Comma-separated question names to keep in comparisons

        Returns:
            New CompareResultsToGold instance with only the specified questions

        Examples:
            >>> from edsl.comparisons import CompareResultsToGold
            >>> crtg = CompareResultsToGold.example()
            >>> crtg_filtered = crtg.keep_questions("q0")
            >>> isinstance(crtg_filtered, CompareResultsToGold)
            True
        """
        # Parse comma-separated list if provided as single string
        questions_to_keep = set()
        for name in question_names:
            if "," in name:
                # Split by comma and strip whitespace
                questions_to_keep.update(q.strip() for q in name.split(","))
            else:
                questions_to_keep.add(name.strip())

        # Get all available questions from results
        all_questions = set()
        for result in self.candidate_results:
            all_questions.update(result.answer.keys())

        # Calculate which questions to exclude (all questions - kept questions)
        new_excluded_questions = (
            all_questions - questions_to_keep
        ) | self.excluded_questions

        # Create new instance with updated exclusions
        return CompareResultsToGold(
            candidate_results=self.candidate_results,
            gold_results=self.gold_results,
            scenario_names=self.scenario_names,
            excluded_metrics=self.excluded_metrics,
            excluded_questions=new_excluded_questions,
        )

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version

        Returns:
            Dictionary representation
        """
        result = {
            "candidate_results": self.candidate_results.to_dict(),
            "gold_results": self.gold_results.to_dict(),
            "scenario_names": self.scenario_names,
            "excluded_metrics": list(self.excluded_metrics),
            "excluded_questions": list(self.excluded_questions),
            "edsl_class_name": self.__class__.__name__,
        }

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
        """
        # Import Results to deserialize
        try:
            from edsl import Results
        except ImportError as exc:
            raise ImportError(
                "edsl is required for CompareResultsToGold.from_dict(); install edsl to use this method."
            ) from exc

        # Remove edsl_version if present
        data_copy = {k: v for k, v in data.items() if k != "edsl_version"}

        # Deserialize results
        candidate_results = Results.from_dict(data_copy["candidate_results"])
        gold_results = Results.from_dict(data_copy["gold_results"])
        scenario_names = data_copy.get("scenario_names", {})
        excluded_metrics = set(data_copy.get("excluded_metrics", []))
        excluded_questions = set(data_copy.get("excluded_questions", []))

        # Create instance (which will rebuild comparisons)
        instance = cls(
            candidate_results,
            gold_results,
            scenario_names=scenario_names,
            excluded_metrics=excluded_metrics,
            excluded_questions=excluded_questions,
        )

        return instance

    def code(self) -> str:
        """Return Python code to recreate this CompareResultsToGold.

        Returns:
            Python code string
        """
        return (
            f"from edsl.comparisons import CompareResultsToGold\n"
            f"# Note: Requires candidate_results and gold_results Results objects\n"
            f"# crtg = CompareResultsToGold(candidate_results, gold_results, "
            f"scenario_names={self.scenario_names})"
        )

    def __hash__(self) -> int:
        """Return hash of the CompareResultsToGold."""
        from ..utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

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
        try:
            from edsl import Results, Agent, Survey, Model, Cache
            from edsl.questions import QuestionMultipleChoice
        except ImportError as exc:
            raise ImportError(
                "edsl is required for CompareResultsToGold.example(); install edsl to use this helper."
            ) from exc

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

        scenario_names = {0: "Candidate 1"}

        return cls(candidate_results, gold_results, scenario_names=scenario_names)

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
        from rich.console import Console
        from rich.text import Text
        import io

        output = Text()
        output.append("CompareResultsToGold(", style="bold cyan")
        output.append(f"agents={len(self.comparisons)}", style="white")
        output.append(", ", style="white")

        total_comparisons = sum(
            len(comp_list) for comp_list in self.comparisons.values()
        )
        output.append(f"comparisons={total_comparisons}", style="yellow")

        output.append(")", style="bold cyan")

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

if __name__ == "__main__":
    import doctest
    
    # Run doctests
    print("Running doctests...")
    results = doctest.testmod()
    print(f"Doctests: {results.attempted} attempted, {results.failed} failed\n")
    
    if results.failed == 0:
        print("=" * 70)
        print("DEMO: CompareResultsToGold Example")
        print("=" * 70)
        
        # Create example comparison
        print("\n1. Creating example with test models (no LLM calls)...")
        crtg = CompareResultsToGold.example()
        print(f"   ✓ Created comparison with {len(crtg.agents)} agent(s)")
        print(f"   Agents: {', '.join(crtg.agents)}")
        
        # Show the actual comparison object repr
        print("\n2. Examining a ResultPairComparison object...")
        comp_list = list(crtg.comparisons.values())[0]
        comp = comp_list[0]
        print(f"   Type: {type(comp).__name__}")
        print(f"   Repr: {repr(comp)}")
        
        # Show an AnswerComparison object repr
        print("\n3. Examining an AnswerComparison object...")
        for q_name, q_comp in comp.comparison.items():
            print(f"   Question: '{q_name}'")
            print(f"   Type: {type(q_comp).__name__}")
            print(f"\n   Standard repr:")
            print(f"   {repr(q_comp)}")
            print(f"\n   Rich summary representation (_summary_repr):")
            if hasattr(q_comp, '_summary_repr'):
                print(q_comp._summary_repr())
            else:
                print("   (No _summary_repr method available)")
            print(f"\n   Available methods: {[m for m in dir(q_comp) if not m.startswith('_')][:10]}")
        
        # Show by_question table - actual repr
        print("\n4. ByQuestionComparison table representation...")
        try:
            table = crtg.by_question("how_feeling")
            print(f"   Type: {type(table).__name__}")
            print(f"   Question name: {table.question_name}")
            print(f"   Question text: {table.question_text}")
            print(f"   Agent data keys: {list(table.agent_data.keys())}")
            print(f"\n   Repr:")
            print(repr(table))
            print(f"\n   Rich table representation:")
            table.print()
        except Exception as e:
            print(f"   ! Error: {e}")
        
        # Show performance table - actual repr
        print("\n5. ComparisonPerformanceTable representation...")
        try:
            perf_table = crtg.comparison_performance_table()
            print(f"   Type: {type(perf_table).__name__}")
            print(f"   Agents: {perf_table.agents}")
            print(f"   Questions: {perf_table.questions}")
            print(f"   Metrics: {perf_table.metrics}")
            print(f"\n   Repr:")
            print(repr(perf_table))
            print(f"\n   Rich table representation:")
            perf_table.print()
        except Exception as e:
            print(f"   ! Error: {e}")
        
        # Show CompareResultsToGold repr
        print("\n6. CompareResultsToGold object representation...")
        print(f"   Type: {type(crtg).__name__}")
        print(f"   Repr: {repr(crtg)}")
        print(f"   Str: {str(crtg)}")
        
        # Show filtering
        print("\n7. Demonstrating metric filtering...")
        try:
            filtered = crtg.keep_metrics("exact_match")
            print(f"   Original metrics: {len(comp.comparison_factory.comparison_fns) if hasattr(comp, 'comparison_factory') else 'N/A'}")
            fcomp = list(filtered.comparisons.values())[0][0]
            filtered_count = len(fcomp.comparison_factory.comparison_fns) if hasattr(fcomp, "comparison_factory") else 0
            print(f"   Filtered metrics: {filtered_count}")
            print(f"   Filtered comparison repr: {repr(filtered)}")
        except Exception as e:
            print(f"   ! Error: {e}")
        
        print("\n" + "=" * 70)
        print("Demo complete! All features working without LLM calls.")
        print("=" * 70)
