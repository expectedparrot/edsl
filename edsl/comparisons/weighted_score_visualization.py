from __future__ import annotations

"""Visualization for weighted score calculations."""

from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison


class WeightedScoreVisualization:
    """Visualizes the breakdown of a weighted score calculation.

    Shows a detailed table with metrics, questions, weights, and contributions
    to the final weighted score.
    """

    def __init__(
        self,
        result_comparison: "ResultPairComparison",
        metric_weights: Dict[str, float],
        question_weights: Dict[str, float],
        final_score: float,
        breakdown: List[Dict[str, Any]],
    ):
        """Initialize the visualization.

        Args:
            result_comparison: The ResultPairComparison object
            metric_weights: Normalized metric weights used in calculation
            question_weights: Question weights used in calculation
            final_score: The final weighted score
            breakdown: List of dicts with computation details for each metric
        """
        self.result_comparison = result_comparison
        self.metric_weights = metric_weights
        self.question_weights = question_weights
        self.final_score = final_score
        self.breakdown = breakdown

    def __repr__(self) -> str:
        """Return string representation."""
        return f"WeightedScoreVisualization(final_score={self.final_score:.4f}, metrics={len(self.breakdown)})"

    def to_html(self) -> str:
        """Generate HTML table showing the weighted score breakdown.

        Returns:
            HTML string with formatted table
        """
        html_parts = []

        # Add styles
        html_parts.append(
            """
<style>
    .weighted-score-viz {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        max-width: 1200px;
        margin: 20px auto;
    }
    .weighted-score-viz h3 {
        color: #333;
        margin-bottom: 20px;
        font-size: 20px;
        font-weight: 600;
    }
    .weighted-score-viz table {
        width: 100%;
        border-collapse: collapse;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        background: white;
        border-radius: 8px;
        overflow: hidden;
    }
    .weighted-score-viz th {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 14px 12px;
        text-align: left;
        font-weight: 600;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .weighted-score-viz td {
        padding: 12px;
        border-bottom: 1px solid #e5e7eb;
        font-size: 14px;
        color: #374151;
    }
    .weighted-score-viz tr:hover {
        background-color: #f9fafb;
    }
    .weighted-score-viz .metric-name {
        font-weight: 500;
        color: #111827;
    }
    .weighted-score-viz .question-name {
        color: #6b7280;
        font-size: 13px;
    }
    .weighted-score-viz .numeric {
        text-align: right;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
        font-size: 13px;
    }
    .weighted-score-viz .weight-col {
        color: #8b5cf6;
        font-weight: 500;
    }
    .weighted-score-viz .contribution-col {
        color: #059669;
        font-weight: 500;
    }
    .weighted-score-viz .total-row {
        background: #f3f4f6;
        font-weight: 700;
        border-top: 2px solid #667eea;
        border-bottom: none;
    }
    .weighted-score-viz .total-row td {
        padding: 16px 12px;
        font-size: 16px;
        color: #111827;
    }
    .weighted-score-viz .final-score {
        color: #667eea;
        font-size: 24px;
        font-weight: 700;
    }
    .weighted-score-viz .section-header {
        background: #f9fafb;
        font-weight: 600;
        color: #4b5563;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .weighted-score-viz .indent {
        padding-left: 32px;
    }
</style>
"""
        )

        # Start the container
        html_parts.append('<div class="weighted-score-viz">')
        html_parts.append("<h3>Weighted Score Breakdown</h3>")

        # Start table
        html_parts.append("<table>")
        html_parts.append("<thead>")
        html_parts.append("<tr>")
        html_parts.append("<th>Metric</th>")
        html_parts.append("<th>Question</th>")
        html_parts.append('<th style="text-align: right;">Score</th>')
        html_parts.append('<th style="text-align: right;">Question Weight</th>')
        html_parts.append('<th style="text-align: right;">Metric Weight</th>')
        html_parts.append('<th style="text-align: right;">Contribution</th>')
        html_parts.append("</tr>")
        html_parts.append("</thead>")
        html_parts.append("<tbody>")

        # Add rows for each metric
        for metric_info in self.breakdown:
            metric_name = metric_info["metric_name"]
            metric_weight = metric_info["metric_weight"]
            metric_avg = metric_info["metric_avg"]
            questions_data = metric_info["questions"]

            # Metric header row
            if questions_data:
                html_parts.append('<tr class="section-header">')
                html_parts.append(
                    f'<td colspan="6" class="metric-name">{metric_name}</td>'
                )
                html_parts.append("</tr>")

                # Question rows
                for q_data in questions_data:
                    qname = q_data["question"]
                    score = q_data["score"]
                    q_weight = q_data["question_weight"]
                    weighted_score = q_data["weighted_score"]

                    html_parts.append("<tr>")
                    html_parts.append('<td class="indent"></td>')
                    html_parts.append(f'<td class="question-name">{qname}</td>')

                    if score is not None:
                        html_parts.append(f'<td class="numeric">{score:.4f}</td>')
                        html_parts.append(
                            f'<td class="numeric weight-col">{q_weight:.4f}</td>'
                        )
                        html_parts.append(
                            f'<td class="numeric weight-col">{metric_weight:.4f}</td>'
                        )
                        html_parts.append(
                            f'<td class="numeric contribution-col">{weighted_score:.4f}</td>'
                        )
                    else:
                        html_parts.append(
                            '<td class="numeric" style="color: #9ca3af;">N/A</td>'
                        )
                        html_parts.append(
                            f'<td class="numeric weight-col">{q_weight:.4f}</td>'
                        )
                        html_parts.append(
                            f'<td class="numeric weight-col">{metric_weight:.4f}</td>'
                        )
                        html_parts.append(
                            '<td class="numeric" style="color: #9ca3af;">—</td>'
                        )

                    html_parts.append("</tr>")

                # Metric subtotal
                contribution = metric_weight * metric_avg
                html_parts.append('<tr style="background: #fafafa;">')
                html_parts.append(
                    f'<td colspan="2" style="text-align: right; font-weight: 600; color: #6b7280;">{metric_name} Average:</td>'
                )
                html_parts.append(
                    f'<td class="numeric" style="font-weight: 600;">{metric_avg:.4f}</td>'
                )
                html_parts.append("<td></td>")
                html_parts.append(
                    f'<td class="numeric weight-col">{metric_weight:.4f}</td>'
                )
                html_parts.append(
                    f'<td class="numeric contribution-col" style="font-weight: 600;">{contribution:.4f}</td>'
                )
                html_parts.append("</tr>")

        # Total row
        html_parts.append('<tr class="total-row">')
        html_parts.append(
            '<td colspan="5" style="text-align: right;">FINAL WEIGHTED SCORE:</td>'
        )
        html_parts.append(
            f'<td class="numeric final-score">{self.final_score:.4f}</td>'
        )
        html_parts.append("</tr>")

        html_parts.append("</tbody>")
        html_parts.append("</table>")
        html_parts.append("</div>")

        return "\n".join(html_parts)

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebooks."""
        return self.to_html()

    @classmethod
    def example(cls) -> "WeightedScoreVisualization":
        """Create an example visualization.

        Returns:
            WeightedScoreVisualization instance

        Examples:
            >>> from edsl.comparisons.weighted_score_visualization import WeightedScoreVisualization
            >>> viz = WeightedScoreVisualization.example()
            >>> isinstance(viz, WeightedScoreVisualization)
            True
        """
        from .result_pair_comparison import (
            ResultPairComparison,
            example_metric_weighting_dict,
            example_question_weighting_dict,
        )

        rc = ResultPairComparison.example()
        mw = example_metric_weighting_dict(rc.comparison_factory)
        qw = example_question_weighting_dict(rc)

        return rc.visualize_weighted_score(mw, qw)


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
