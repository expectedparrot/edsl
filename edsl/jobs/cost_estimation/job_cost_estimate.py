from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...dataset import Dataset


class JobCostEstimate:
    """Result of a job cost estimation.

    Three levels of detail:
    - repr: one-line summary
    - .detail: per-question breakdown as a Dataset
    - .assumptions / .warnings: what the estimator assumed and where it approximated
    """

    def __init__(
        self,
        rows: list[dict],
        assumptions: dict,
        warnings: list[str],
    ):
        self._rows = rows
        self.assumptions = assumptions
        self.warnings = warnings

    # ------------------------------------------------------------------
    # Summary

    @property
    def total_cost_usd(self) -> float:
        return sum(r["cost_usd"] for r in self._rows)

    @property
    def total_input_tokens(self) -> int:
        return sum(r["total_input_tokens"] for r in self._rows)

    @property
    def total_output_tokens(self) -> int:
        return sum(r["total_output_tokens"] for r in self._rows)

    @property
    def num_questions(self) -> int:
        return len(self._rows)

    @property
    def num_interviews(self) -> int:
        if not self._rows:
            return 0
        return max(r["interview_index"] for r in self._rows) + 1

    def __repr__(self) -> str:
        return (
            f"JobCostEstimate: ${self.total_cost_usd:.4f} "
            f"({self.total_input_tokens:,} input tokens, "
            f"{self.total_output_tokens:,} output tokens "
            f"across {self.num_questions} questions)"
        )

    # ------------------------------------------------------------------
    # Per-question aggregation

    def summary_by_question(self) -> list[dict]:
        """Aggregate detail rows by question name across all interviews.

        Returns one dict per unique question with:
          - total_cost_usd: sum across all interviews
          - cost_share: fraction of total job cost
          - avg_input_tokens / avg_output_tokens: mean per interview
          - avg_reach_probability: mean reach across interviews
          - estimator_used: from the first interview (consistent across all)
          - billable: from the first interview
        """
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in self._rows:
            grouped[row["question_name"]].append(row)

        total = self.total_cost_usd
        result = []
        for q_name, rows in grouped.items():
            n = len(rows)
            q_cost = sum(r["cost_usd"] for r in rows)
            result.append({
                "question_name": q_name,
                "estimator_used": rows[0]["estimator_used"],
                "billable": rows[0]["billable"],
                "avg_reach_probability": sum(r["reach_probability"] for r in rows) / n,
                "avg_input_tokens": sum(r["total_input_tokens"] for r in rows) / n,
                "avg_output_tokens": sum(r["total_output_tokens"] for r in rows) / n,
                "total_cost_usd": q_cost,
                "cost_share": q_cost / total if total > 0 else 0.0,
            })
        return result

    # ------------------------------------------------------------------
    # Markdown report

    def to_markdown(self, path: str | None = None) -> str:
        """Human-readable markdown summary of the estimate.

        Includes: top-level totals, per-question cost breakdown, assumptions, warnings.
        Does not include the full detail table — use .detail for that.
        """
        from tabulate import tabulate

        n_interviews = self.num_interviews
        unique_questions = len(set(r["question_name"] for r in self._rows)) if self._rows else 0

        table_rows = [
            {
                "Question": q["question_name"],
                "Estimator": q["estimator_used"].split("(")[0],
                "Billable": "yes" if q["billable"] else "no",
                "Avg reach": f"{q['avg_reach_probability']:.2f}",
                "Avg input": f"{q['avg_input_tokens']:.0f}",
                "Avg output": f"{q['avg_output_tokens']:.0f}",
                "Total cost": f"${q['total_cost_usd']:.4f}",
                "Cost share": f"{q['cost_share']:.1%}",
            }
            for q in self.summary_by_question()
        ]

        assumptions_lines = "\n".join(f"- **{k}:** {v}" for k, v in self.assumptions.items())
        warnings_lines = "\n".join(f"- {w}" for w in self.warnings) if self.warnings else "No warnings."

        md = "\n".join([
            "# Job Cost Estimate",
            "",
            f"**Total cost:** ${self.total_cost_usd:.4f}  ",
            f"**Interviews:** {n_interviews}  ",
            f"**Questions per interview:** {unique_questions}  ",
            f"**Total input tokens:** {self.total_input_tokens:,}  ",
            f"**Total output tokens:** {self.total_output_tokens:,}  ",
            "",
            "## Cost by question",
            "",
            tabulate(table_rows, headers="keys", tablefmt="github"),
            "",
            "## Assumptions",
            "",
            assumptions_lines,
            "",
            "## Warnings",
            "",
            warnings_lines,
        ])

        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)

        return md

    # ------------------------------------------------------------------
    # Detail dataset

    @property
    def detail(self) -> "Dataset":
        from ...dataset import Dataset

        if not self._rows:
            return Dataset([])

        keys = list(self._rows[0].keys())
        return Dataset([{k: [r[k] for r in self._rows]} for k in keys])

    # ------------------------------------------------------------------
    # Warnings display

    def show_warnings(self) -> None:
        if not self.warnings:
            print("No warnings.")
        else:
            for w in self.warnings:
                print(f"  ⚠ {w}")
