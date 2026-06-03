from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

APP_CREDITS_PRICE_CENTS = 1  # 1 credit = 1 cent = $0.01


def usd_to_credits(usd: float) -> float:
    return usd * (100 / APP_CREDITS_PRICE_CENTS)


if TYPE_CHECKING:
    from ...dataset import Dataset


class JobCostEstimate:
    """Result of a job cost estimation.

    Three levels of detail:
    - repr: one-line summary
    - .detail: per-question breakdown as a Dataset
    - .warnings: where the estimator approximated or fell back
    """

    def __init__(
        self,
        rows: list[dict],
        warnings: list[str],
    ):
        self._rows = rows
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
    def total_credits(self) -> float:
        """Total estimated cost in Expected Parrot credits (1 credit = $0.01)."""
        return usd_to_credits(self.total_cost_usd)

    @property
    def num_interviews(self) -> int:
        if not self._rows:
            return 0
        return max(r["interview_index"] for r in self._rows) + 1

    def __repr__(self) -> str:
        return (
            f"JobCostEstimate: ${self.total_cost_usd:.4f} ({self.total_credits:,.2f} credits) "
            f"— {self.total_input_tokens:,} input tokens, "
            f"{self.total_output_tokens:,} output tokens "
            f"across {self.num_questions} questions"
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
            result.append(
                {
                    "question_name": q_name,
                    "question_type": rows[0].get("question_type", ""),
                    "estimator_used": rows[0]["estimator_used"],
                    "estimator_description": rows[0].get("estimator_description", ""),
                    "billable": rows[0]["billable"],
                    "avg_reach_probability": sum(r["reach_probability"] for r in rows)
                    / n,
                    "avg_input_tokens": sum(r["total_input_tokens"] for r in rows) / n,
                    "avg_output_tokens": sum(r["total_output_tokens"] for r in rows)
                    / n,
                    "total_cost_usd": q_cost,
                    "total_cost_credits": usd_to_credits(q_cost),
                    "cost_share": q_cost / total if total > 0 else 0.0,
                }
            )
        return result

    def summary_by_model(self) -> list[dict]:
        """Aggregate detail rows by (model, inference_service).

        Returns one dict per unique model with total tokens, total cost,
        and the price per million tokens used for the estimate.
        """
        grouped: dict[tuple, list[dict]] = defaultdict(list)
        for row in self._rows:
            grouped[(row["inference_service"], row["model"])].append(row)

        result = []
        for (inference_service, model), rows in grouped.items():
            result.append(
                {
                    "inference_service": inference_service,
                    "model": model,
                    "input_price_per_million": rows[0]["input_price_per_million"],
                    "output_price_per_million": rows[0]["output_price_per_million"],
                    "total_input_tokens": sum(r["total_input_tokens"] for r in rows),
                    "total_output_tokens": sum(r["total_output_tokens"] for r in rows),
                    "total_cost_usd": sum(r["cost_usd"] for r in rows),
                    "total_cost_credits": usd_to_credits(
                        sum(r["cost_usd"] for r in rows)
                    ),
                }
            )
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
        unique_questions = (
            len(set(r["question_name"] for r in self._rows)) if self._rows else 0
        )

        model_rows = [
            {
                "Model": f"{m['inference_service']} / {m['model']}",
                "Input $/M": f"${m['input_price_per_million']:.2f}",
                "Output $/M": f"${m['output_price_per_million']:.2f}",
                "Total input": f"{m['total_input_tokens']:,}",
                "Total output": f"{m['total_output_tokens']:,}",
                "Total cost": f"${m['total_cost_usd']:.4f}",
                "Credits": f"{m['total_cost_credits']:,.2f}",
            }
            for m in self.summary_by_model()
        ]

        table_rows = [
            {
                "Question": q["question_name"],
                "Type": q["question_type"],
                "Billable": "yes" if q["billable"] else "no",
                "Avg reach": f"{q['avg_reach_probability']:.2f}",
                "Avg input": f"{q['avg_input_tokens']:.0f}",
                "Avg output": f"{q['avg_output_tokens']:.0f}",
                "Total cost": f"${q['total_cost_usd']:.4f}",
                "Credits": f"{q['total_cost_credits']:,.2f}",
                "Cost share": f"{q['cost_share']:.1%}",
            }
            for q in self.summary_by_question()
        ]

        # Methodology: group question names that share the same description
        desc_to_names: dict[str, list[str]] = defaultdict(list)
        for q in self.summary_by_question():
            desc_to_names[q["estimator_description"]].append(q["question_name"])
        methodology_rows = [
            {"Questions": ", ".join(names), "Description": desc}
            for desc, names in desc_to_names.items()
        ]
        methodology_section = tabulate(methodology_rows, headers="keys", tablefmt="github")

        warnings_lines = (
            "\n".join(f"- {w}" for w in self.warnings)
            if self.warnings
            else "No warnings."
        )

        md = "\n".join(
            [
                "# Job Cost Estimate",
                "",
                f"**Total cost:** ${self.total_cost_usd:.4f} ({self.total_credits:,.2f} credits)  ",
                f"**Responses:** {n_interviews}  ",
                f"**Questions per survey:** {unique_questions}  ",
                f"**Total input tokens:** {self.total_input_tokens:,}  ",
                f"**Total output tokens:** {self.total_output_tokens:,}  ",
                "",
                "## Cost by model",
                "",
                tabulate(model_rows, headers="keys", tablefmt="github"),
                "",
                "## Cost by question",
                "",
                tabulate(table_rows, headers="keys", tablefmt="github"),
                "",
                "## How costs were estimated",
                "",
                methodology_section,
                "",
                "## Warnings",
                "",
                warnings_lines,
            ]
        )

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
