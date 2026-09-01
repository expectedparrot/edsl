from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

APP_CREDITS_PRICE_CENTS = 1  # 1 credit = 1 cent = $0.01


def usd_to_credits(usd: float) -> float:
    return usd * (100 / APP_CREDITS_PRICE_CENTS)


def _unique_file_descriptions(rows: list[dict]) -> list[dict]:
    """Return unique file descriptions across rows, each with its avg token count and models.

    Groups rows by their file_description string so that different provider
    formulas (OpenAI PDF vs Anthropic PDF vs Google PDF) each get their own entry.
    Models are tracked so callers can show which models use each formula when
    multiple formulas exist for the same provider.
    """
    groups: dict[str, dict] = {}
    for r in rows:
        desc = r.get("file_description", "")
        if not desc:
            continue
        if desc not in groups:
            groups[desc] = {
                "tokens": [],
                "models": [],
                "seen": set(),
                "breakdowns": r.get("file_breakdowns", []),
            }
        groups[desc]["tokens"].append(r.get("file_tokens", 0))
        model = r.get("model", "")
        if model and model not in groups[desc]["seen"]:
            groups[desc]["seen"].add(model)
            groups[desc]["models"].append(model)
    return sorted(
        [
            {
                "description": desc,
                "avg_tokens": sum(d["tokens"]) / len(d["tokens"]),
                "models": d["models"],
                "breakdowns": d["breakdowns"],
            }
            for desc, d in groups.items()
        ],
        key=lambda x: x["description"],
    )


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
        return round(
            sum(r["total_input_tokens"] * r["reach_probability"] for r in self._rows)
        )

    @property
    def total_output_tokens(self) -> int:
        return round(
            sum(r["total_output_tokens"] * r["reach_probability"] for r in self._rows)
        )

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
                    "override_description": rows[0].get("override_description", ""),
                    "billable": rows[0]["billable"],
                    "avg_reach_probability": sum(r["reach_probability"] for r in rows)
                    / n,
                    "avg_file_tokens": sum(r.get("file_tokens", 0) for r in rows) / n,
                    "avg_memory_tokens": sum(r.get("memory_tokens", 0) for r in rows)
                    / n,
                    "file_descriptions": _unique_file_descriptions(rows),
                    "avg_input_tokens": sum(r["total_input_tokens"] for r in rows) / n,
                    "avg_output_tokens": sum(r["total_output_tokens"] for r in rows)
                    / n,
                    "avg_comment_tokens": sum(r.get("comment_tokens", 0) for r in rows)
                    / n,
                    "avg_thinking_tokens": sum(
                        r.get("thinking_tokens", 0) for r in rows
                    )
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
                    "total_input_tokens": round(
                        sum(
                            r["total_input_tokens"] * r["reach_probability"]
                            for r in rows
                        )
                    ),
                    "total_output_tokens": round(
                        sum(
                            r["total_output_tokens"] * r["reach_probability"]
                            for r in rows
                        )
                    ),
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

        q_summaries = self.summary_by_question()

        show_file_col = any(q["avg_file_tokens"] > 0 for q in q_summaries)
        show_memory_col = any(q["avg_memory_tokens"] > 0 for q in q_summaries)
        show_comment_col = any(q["avg_comment_tokens"] > 0 for q in q_summaries)
        show_thinking_col = any(q["avg_thinking_tokens"] > 0 for q in q_summaries)

        input_col_label = "Avg input tokens (prompt + file + memory)"
        output_col_label = "Avg output tokens (answer + comment + thinking)"

        table_rows = []
        for q in q_summaries:
            row = {
                "Question": q["question_name"],
                "Type": q["question_type"],
                "Avg reach*": f"{q['avg_reach_probability']:.2f}",
            }
            if show_file_col:
                row["Avg file tokens"] = f"{q['avg_file_tokens']:.0f}"
            if show_memory_col:
                row["Avg memory tokens"] = f"{q['avg_memory_tokens']:.0f}"
            row[input_col_label] = f"{q['avg_input_tokens']:.0f}"
            if show_comment_col:
                row["Avg comment tokens"] = f"{q['avg_comment_tokens']:.0f}"
            if show_thinking_col:
                row["Avg thinking tokens"] = f"{q['avg_thinking_tokens']:.0f}"
            row[output_col_label] = f"{q['avg_output_tokens']:.0f}"
            row["Total cost"] = f"${q['total_cost_usd']:.4f}"
            row["Credits"] = f"{q['total_cost_credits']:,.2f}"
            row["Cost share"] = f"{q['cost_share']:.1%}"
            table_rows.append(row)

        # Methodology section
        # Simple questions (no override, no files) are grouped by shared description.
        # Complex questions (override or files) each get their own bullet block.
        simple_groups: dict[str, list[str]] = defaultdict(list)
        complex_questions = []
        for q in q_summaries:
            if not q.get("override_description") and not q.get("file_descriptions"):
                simple_groups[q["estimator_description"]].append(q["question_name"])
            else:
                complex_questions.append(q)

        # Each question is a block; blocks are separated by blank lines.
        # Lines within a block are separated by single newlines so that
        # nested sub-bullets stay attached to their parent bullet.
        methodology_blocks = []
        for base_desc, names in simple_groups.items():
            methodology_blocks.append(f"**{', '.join(names)}** — {base_desc}")

        for q in complex_questions:
            block = [f"**{q['question_name']}**"]
            override_desc = q.get("override_description", "")
            base_desc = q["estimator_description"]
            if override_desc:
                block.append(
                    f"- Output tokens: {override_desc} (override; default: {base_desc.lower()})"
                )
            else:
                block.append(f"- Output tokens: {base_desc}")
            file_descs = q.get("file_descriptions", [])
            show_models = len(file_descs) > 1
            for fd in file_descs:
                models = fd["models"] if show_models and fd["models"] else []
                breakdowns = fd.get("breakdowns", [])
                if len(breakdowns) == 1:
                    bd = breakdowns[0]
                    label = bd.get("file_label", "")
                    label_str = f"`{label}` " if label else ""
                    block.append(
                        f"- File tokens: {fd['avg_tokens']:,.0f} — {label_str}({bd['provider']})"
                    )
                    if models:
                        block.append(f"  - models: {', '.join(models)}")
                    for comp in bd["components"]:
                        tokens_str = (
                            f" = {comp['tokens']:,}"
                            if comp.get("tokens") is not None
                            else ""
                        )
                        block.append(
                            f"  - {comp['label']}: {comp['value']}{tokens_str}"
                        )
                    if bd.get("note"):
                        block.append(f"  - _{bd['note']}_")
                elif breakdowns:
                    block.append(
                        f"- File tokens: {fd['avg_tokens']:,.0f} total ({len(breakdowns)} files)"
                    )
                    if models:
                        block.append(f"  - models: {', '.join(models)}")
                    for bd in breakdowns:
                        label = bd.get("file_label", "")
                        label_str = f"`{label}` " if label else ""
                        block.append(
                            f"  - {label_str}({bd['provider']}): {bd['total']:,} tokens"
                        )
                        for comp in bd["components"]:
                            tokens_str = (
                                f" = {comp['tokens']:,}"
                                if comp.get("tokens") is not None
                                else ""
                            )
                            block.append(
                                f"    - {comp['label']}: {comp['value']}{tokens_str}"
                            )
                        if bd.get("note"):
                            block.append(f"    - _{bd['note']}_")
                else:
                    block.append(
                        f"- File tokens: {fd['avg_tokens']:,.0f} — {fd['description']}"
                    )
                    if models:
                        block.append(f"  - models: {', '.join(models)}")
            methodology_blocks.append("\n".join(block))

        methodology_section = "\n\n".join(methodology_blocks)

        warnings_intro = (
            "_Warnings flag places where the estimate used a fallback, approximation, "
            "or ignored something (e.g. skip logic, unsupported file types). "
            "Each warning identifies what was affected and how to address it._"
        )
        warnings_body = (
            "\n".join(f"- {w}" for w in self.warnings)
            if self.warnings
            else "No warnings."
        )
        warnings_lines = f"{warnings_intro}\n\n{warnings_body}"

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
                "_\\* Avg reach: estimated fraction of respondents who reach this question. "
                "Always 1.0 for surveys with no skip rules; less than 1.0 when skip logic is present "
                "and branch\\_weights are provided._",
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
