from __future__ import annotations

"""Classes for displaying comparison tables and interactive question viewers."""

from typing import Dict, Any, List, Set


class InteractiveQuestionViewer:
    """Interactive viewer for clicking through all questions in a survey."""

    def __init__(self, questions_data: Dict[str, tuple]):
        """Initialize the interactive question viewer.

        Args:
            questions_data: Dict mapping question_name -> (question_text, agent_data)
        """
        self.questions_data = questions_data
        self.question_names = sorted(questions_data.keys())

    def _repr_html_(self) -> str:
        """Return HTML representation with interactive question navigation."""
        if not self.questions_data:
            return "<p>No questions found.</p>"

        # Generate unique ID for this viewer instance
        import random

        viewer_id = f"qv_{random.randint(100000, 999999)}"

        html = [
            f'<div id="question-viewer-{viewer_id}" style="font-family: Arial, sans-serif;">'
        ]

        # Title
        html.append("<h2>Interactive Question Comparison</h2>")

        # Navigation controls
        html.append(
            '<div style="margin: 15px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
        )
        html.append(
            f'  <button onclick="prevQuestion_{viewer_id}()" style="padding: 8px 20px; margin-right: 10px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">← Previous</button>'
        )
        html.append(
            f'  <span id="question-counter-{viewer_id}" style="font-weight: bold; margin: 0 15px; font-size: 1.1em;">Question 1 of {len(self.question_names)}</span>'
        )
        html.append(
            f'  <button onclick="nextQuestion_{viewer_id}()" style="padding: 8px 20px; margin-left: 10px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">Next →</button>'
        )
        html.append("</div>")

        # Create a div for each question (only first one visible)
        for idx, question_name in enumerate(self.question_names):
            question_text, agent_data = self.questions_data[question_name]
            display = "block" if idx == 0 else "none"
            html.append(
                f'<div class="question-content-{viewer_id}" id="question-{viewer_id}-{idx}" style="display: {display};">'
            )

            # Embed the ByQuestionComparison HTML directly
            comparison = ByQuestionComparison(question_name, question_text, agent_data)
            html.append(comparison._repr_html_())

            html.append("</div>")

        # JavaScript for navigation (unique per instance)
        html.append("<script>")
        html.append(f"let currentQuestion_{viewer_id} = 0;")
        html.append(f"const totalQuestions_{viewer_id} = {len(self.question_names)};")
        html.append(
            f"""
function showQuestion_{viewer_id}(index) {{
    // Hide all questions for this viewer
    const questions = document.querySelectorAll('.question-content-{viewer_id}');
    questions.forEach(q => q.style.display = 'none');
    
    // Show selected question
    const selected = document.getElementById('question-{viewer_id}-' + index);
    if (selected) {{
        selected.style.display = 'block';
    }}
    
    // Update counter
    const counter = document.getElementById('question-counter-{viewer_id}');
    if (counter) {{
        counter.textContent = 'Question ' + (index + 1) + ' of ' + totalQuestions_{viewer_id};
    }}
    
    currentQuestion_{viewer_id} = index;
}}

function nextQuestion_{viewer_id}() {{
    const next = (currentQuestion_{viewer_id} + 1) % totalQuestions_{viewer_id};
    showQuestion_{viewer_id}(next);
}}

function prevQuestion_{viewer_id}() {{
    const prev = (currentQuestion_{viewer_id} - 1 + totalQuestions_{viewer_id}) % totalQuestions_{viewer_id};
    showQuestion_{viewer_id}(prev);
}}
        """
        )
        html.append("</script>")
        html.append("</div>")

        return "\n".join(html)


class ByQuestionComparison:
    """Table showing candidate answers vs gold standard for a specific question.

    This class provides a nice HTML visualization for Jupyter notebooks showing
    how different candidates answered a question compared to the gold standard.
    """

    def __init__(
        self, question_name: str, question_text: str, agent_data: Dict[str, List[tuple]]
    ):
        """Initialize the by-question comparison table.

        Args:
            question_name: The question identifier
            question_text: The full text of the question
            agent_data: Dict mapping agent_name -> list of (candidate_idx, candidate_answer, gold_answer) tuples
        """
        self.question_name = question_name
        self.question_text = question_text
        self.agent_data = agent_data

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebook display."""
        html = ['<div style="overflow-x: auto; font-family: Arial, sans-serif;">']

        # Title with question name and text
        html.append(
            f'<h3 style="color: #2c3e50; margin-bottom: 5px;">Question: {self.question_name}</h3>'
        )
        if self.question_text:
            html.append(
                f'<p style="color: #7f8c8d; font-style: italic; margin-top: 0; margin-bottom: 15px;">{self.question_text}</p>'
            )

        html.append(
            '<table style="border-collapse: collapse; border: 1px solid #ddd; width: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
        )

        # Header row
        html.append('<thead><tr style="background-color: #34495e; color: white;">')
        html.append(
            '<th style="border: 1px solid #2c3e50; padding: 12px; text-align: left; font-weight: bold; width: 30%;">Agent / Candidate</th>'
        )
        html.append(
            '<th style="border: 1px solid #2c3e50; padding: 12px; text-align: left; font-weight: bold;">Candidate Answer</th>'
        )
        html.append(
            '<th style="border: 1px solid #2c3e50; padding: 12px; text-align: left; font-weight: bold; background-color: #2c3e50;">True Answer (Gold)</th>'
        )
        html.append("</tr></thead>")

        # Data rows
        html.append("<tbody>")
        for agent_name in sorted(self.agent_data.keys()):
            # Agent grouping row
            html.append('<tr style="background-color: #3498db; color: white;">')
            html.append(
                f'<td colspan="3" style="border: 1px solid #2980b9; padding: 10px; font-weight: bold; font-size: 1.05em;">📊 {agent_name}</td>'
            )
            html.append("</tr>")

            # Candidate rows
            candidates = self.agent_data[agent_name]
            for row_idx, (candidate_idx, candidate_answer, gold_answer) in enumerate(
                candidates
            ):
                # Alternate row colors
                row_bg = "#f8f9fa" if row_idx % 2 == 0 else "#ffffff"
                html.append(f'<tr style="background-color: {row_bg};">')

                # Candidate identifier (indented)
                html.append(
                    f'<td style="border: 1px solid #ddd; padding: 8px; padding-left: 30px; color: #555;">→ Candidate #{candidate_idx}</td>'
                )

                # Format candidate answer
                candidate_str = (
                    str(candidate_answer)
                    if candidate_answer is not None
                    else '<em style="color: #95a5a6;">No answer</em>'
                )
                # Highlight if it matches gold
                if candidate_answer == gold_answer:
                    answer_style = "border: 1px solid #ddd; padding: 8px; background-color: #d4edda; font-weight: bold;"
                    candidate_str = f"✓ {candidate_str}"
                else:
                    answer_style = "border: 1px solid #ddd; padding: 8px;"
                html.append(f'<td style="{answer_style}">{candidate_str}</td>')

                # Format gold answer
                gold_str = (
                    str(gold_answer)
                    if gold_answer is not None
                    else '<em style="color: #95a5a6;">No answer</em>'
                )
                html.append(
                    f'<td style="border: 1px solid #ddd; padding: 8px; background-color: #fff3cd;">{gold_str}</td>'
                )

                html.append("</tr>")

        html.append("</tbody>")
        html.append("</table>")
        html.append("</div>")

        return "\n".join(html)

    def to_rich_table(self):
        """Return a Rich Table object for terminal display."""
        from rich.table import Table

        table = Table(title=f"Answers for Question: {self.question_name}")

        # Add columns
        table.add_column("Agent / Candidate", style="bold")
        table.add_column("Candidate Answer")
        table.add_column("True Answer")

        # Add rows
        for agent_name in sorted(self.agent_data.keys()):
            # Agent grouping row
            table.add_row(f"[bold cyan]{agent_name}[/bold cyan]", "", "")

            # Candidate rows
            candidates = self.agent_data[agent_name]
            for candidate_idx, candidate_answer, gold_answer in candidates:
                candidate_str = (
                    str(candidate_answer) if candidate_answer is not None else "-"
                )
                gold_str = str(gold_answer) if gold_answer is not None else "-"

                table.add_row(f"  Candidate #{candidate_idx}", candidate_str, gold_str)

        return table

    def print(self):
        """Print the table to console using Rich."""
        from rich.console import Console

        console = Console()
        console.print(self.to_rich_table())


class ComparisonPerformanceTable:
    """Table showing which candidates perform best on each question-metric combination.

    This class holds performance data for multiple candidates across questions and metrics,
    identifying which candidates are best performers (or tied) on each dimension.
    Can display data for one or multiple agents.
    """

    def __init__(
        self,
        agent_data: Dict[str, Dict[int, Dict[str, Dict[str, Any]]]],
        questions: List[str],
        metrics: List[str],
        best_performers: Dict[str, Dict[tuple, Set[int]]],
        pareto_members: Dict[str, Set[int]] = None,
    ):
        """Initialize the performance table.

        Args:
            agent_data: Nested dict: agent_name -> candidate_idx -> question -> metric -> value
            questions: List of question names
            metrics: List of metric names
            best_performers: Dict mapping agent_name -> (question, metric) -> set of best candidate indices
            pareto_members: Dict mapping agent_name -> set of candidate indices in Pareto frontier
        """
        self.agent_data = agent_data
        self.questions = questions
        self.metrics = metrics
        self.best_performers = best_performers
        self.pareto_members = pareto_members or {}

    @property
    def agents(self) -> List[str]:
        """Return list of agent names in the table."""
        return list(self.agent_data.keys())

    def _calculate_pareto_frontier(self, agent_name: str) -> Set[int]:
        """Calculate which candidates are in the Pareto frontier for an agent.

        A candidate is in the Pareto frontier if it's not dominated by any other candidate.
        Candidate A dominates B if A >= B on all question-metric pairs and A > B on at least one.
        Higher values are better.

        Args:
            agent_name: The agent to calculate Pareto frontier for

        Returns:
            Set of candidate indices that are in the Pareto frontier
        """
        data = self.agent_data[agent_name]
        candidate_indices = list(data.keys())

        if not candidate_indices:
            return set()

        # For each candidate, collect all their metric values
        candidate_scores = {}
        for idx in candidate_indices:
            scores = []
            for q in self.questions:
                for m in self.metrics:
                    val = data[idx][q][m]
                    if val is not None:
                        try:
                            scores.append(float(val))
                        except (TypeError, ValueError):
                            # If can't convert to float, use 0
                            scores.append(0.0)
                    else:
                        scores.append(0.0)
            candidate_scores[idx] = scores

        # Find Pareto frontier
        pareto_set = set()
        for idx in candidate_indices:
            is_dominated = False
            for other_idx in candidate_indices:
                if idx == other_idx:
                    continue

                # Check if other_idx dominates idx
                scores_idx = candidate_scores[idx]
                scores_other = candidate_scores[other_idx]

                # other dominates idx if other >= idx on all dimensions and other > idx on at least one
                all_gte = all(
                    s_other >= s_idx for s_other, s_idx in zip(scores_other, scores_idx)
                )
                any_gt = any(
                    s_other > s_idx for s_other, s_idx in zip(scores_other, scores_idx)
                )

                if all_gte and any_gt:
                    is_dominated = True
                    break

            if not is_dominated:
                pareto_set.add(idx)

        return pareto_set

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebook display."""
        html = ['<div style="overflow-x: auto;">']
        html.append("<h2>Candidate Performance Comparison</h2>")

        # Create a table for each agent
        for agent_name in sorted(self.agent_data.keys()):
            data = self.agent_data[agent_name]
            agent_best = self.best_performers[agent_name]

            # Calculate Pareto frontier if not already done
            if agent_name not in self.pareto_members:
                self.pareto_members[agent_name] = self._calculate_pareto_frontier(
                    agent_name
                )
            pareto_set = self.pareto_members[agent_name]

            html.append(f'<h3 style="margin-top: 20px;">Agent: {agent_name}</h3>')
            html.append(
                '<table style="border-collapse: collapse; border: 1px solid #ddd; margin-bottom: 30px;">'
            )

            # Header row
            html.append('<thead><tr style="background-color: #f2f2f2;">')
            html.append(
                '<th style="border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold;">Candidate</th>'
            )
            html.append(
                '<th style="border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold; width: 60px;">Pareto</th>'
            )
            for q in self.questions:
                for m in self.metrics:
                    html.append(
                        f'<th style="border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 0.9em;">{q}<br/>{m}</th>'
                    )
            html.append("</tr></thead>")

            # Data rows
            html.append("<tbody>")
            for idx in sorted(data.keys()):
                html.append("<tr>")
                html.append(
                    f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold;">#{idx}</td>'
                )

                # Pareto column
                pareto_mark = "✓" if idx in pareto_set else ""
                pareto_style = (
                    "border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #e3f2fd;"
                    if idx in pareto_set
                    else "border: 1px solid #ddd; padding: 8px; text-align: center;"
                )
                html.append(f'<td style="{pareto_style}">{pareto_mark}</td>')

                for q in self.questions:
                    for m in self.metrics:
                        val = data[idx][q][m]

                        if val is None:
                            cell_text = "-"
                            cell_style = "border: 1px solid #ddd; padding: 8px; text-align: center;"
                        else:
                            # Format the value
                            try:
                                if isinstance(val, bool):
                                    cell_text = "✓" if val else "✗"
                                elif isinstance(val, float):
                                    cell_text = f"{val:.3f}"
                                else:
                                    cell_text = str(val)
                            except:
                                cell_text = str(val)

                            # Check if this is a best performer
                            if idx in agent_best.get((q, m), set()):
                                cell_style = "border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #90EE90; font-weight: bold;"
                            else:
                                cell_style = "border: 1px solid #ddd; padding: 8px; text-align: center;"

                        html.append(f'<td style="{cell_style}">{cell_text}</td>')

                html.append("</tr>")
            html.append("</tbody>")
            html.append("</table>")

        html.append("</div>")
        return "\n".join(html)

    def to_rich_table(self):
        """Return a list of Rich Table objects for terminal display (one per agent)."""
        from rich.table import Table

        tables = []
        for agent_name in sorted(self.agent_data.keys()):
            data = self.agent_data[agent_name]
            agent_best = self.best_performers[agent_name]

            # Calculate Pareto frontier if not already done
            if agent_name not in self.pareto_members:
                self.pareto_members[agent_name] = self._calculate_pareto_frontier(
                    agent_name
                )
            pareto_set = self.pareto_members[agent_name]

            table = Table(
                title=f"Candidate Performance Comparison for Agent: {agent_name}"
            )

            # Add columns
            table.add_column("Candidate", style="bold", justify="center")
            table.add_column("Pareto", justify="center", width=7)
            for q in self.questions:
                for m in self.metrics:
                    table.add_column(f"{q}\n{m}", justify="center")

            # Add rows
            for idx in sorted(data.keys()):
                row_data = [f"#{idx}"]

                # Add Pareto checkmark
                if idx in pareto_set:
                    row_data.append("[blue]✓[/blue]")
                else:
                    row_data.append("")

                for q in self.questions:
                    for m in self.metrics:
                        val = data[idx][q][m]
                        if val is None:
                            row_data.append("-")
                        else:
                            # Format the value
                            try:
                                if isinstance(val, bool):
                                    cell_text = "✓" if val else "✗"
                                elif isinstance(val, float):
                                    cell_text = f"{val:.3f}"
                                else:
                                    cell_text = str(val)
                            except:
                                cell_text = str(val)

                            # Check if this is a best performer
                            if idx in agent_best.get((q, m), set()):
                                cell_text = f"[green]{cell_text}[/green]"

                            row_data.append(cell_text)

                table.add_row(*row_data)

            tables.append(table)

        return tables if len(tables) > 1 else tables[0]

    def print(self):
        """Print the table(s) to console using Rich."""
        from rich.console import Console

        console = Console()
        tables = self.to_rich_table()
        if isinstance(tables, list):
            for table in tables:
                console.print(table)
                console.print()  # Add spacing between tables
        else:
            console.print(tables)

