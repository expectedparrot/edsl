from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...dataset import Dataset


class CostEstimate:
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

    def __repr__(self) -> str:
        return (
            f"CostEstimate: ${self.total_cost_usd:.4f} "
            f"({self.total_input_tokens:,} input tokens, "
            f"{self.total_output_tokens:,} output tokens "
            f"across {self.num_questions} questions)"
        )

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
