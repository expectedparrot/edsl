from __future__ import annotations
from typing import TYPE_CHECKING

from .token_override import TokenOverride

if TYPE_CHECKING:
    from ...results import Results


def calibrate_from_results(
    results: "Results",
    percentile: int = 75,
    by_model: bool = True,
) -> dict[str, TokenOverride | list[TokenOverride]]:
    """Derive token overrides from a pilot Results object.

    Computes the given percentile of actual output tokens per question (and
    optionally per service/model), returning a dict ready to pass as
    token_overrides to JobCostEstimator.estimate_cost().

    Args:
        results:    a completed Results object from a pilot run
        percentile: which percentile of observed output tokens to use (default 75).
                    Use 50 for median (unbiased cost projection) or a higher value
                    (75-90) for a conservative budget estimate.
        by_model:   if True (default), return per-(service, model) overrides so each
                    model gets its own calibrated estimate; if False, pool all models
                    into one global override per question

    Returns:
        dict[str, TokenOverride | list[TokenOverride]] ready for token_overrides=
    """
    prefix = "raw_model_response."
    suffix = "_output_tokens"

    token_cols = [
        c for c in results.columns if c.startswith(prefix) and c.endswith(suffix)
    ]
    question_names = [c[len(prefix) : -len(suffix)] for c in token_cols]

    overrides: dict[str, TokenOverride | list[TokenOverride]] = {}

    for q, col in zip(question_names, token_cols):
        if by_model:
            df = results.select(
                col, "model.inference_service", "model.model"
            ).to_pandas()
            df = df.dropna(subset=[col])
            entries: list[TokenOverride] = []
            for (svc, mdl), grp in df.groupby(
                ["model.inference_service", "model.model"]
            ):
                vals = grp[col].tolist()
                entries.append(
                    TokenOverride(
                        answer_tokens=_percentile(vals, percentile),
                        service=svc,
                        model=mdl,
                        note=f"calibrated from pilot (n={len(vals)}, p{percentile})",
                    )
                )
            overrides[q] = entries
        else:
            df = results.select(col).to_pandas().dropna(subset=[col])
            vals = df[col].tolist()
            overrides[q] = TokenOverride(
                answer_tokens=_percentile(vals, percentile),
                note=f"calibrated from pilot (n={len(vals)}, p{percentile})",
            )

    return overrides


def _percentile(values: list[float], p: int) -> int:
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * p / 100), len(sorted_vals) - 1)
    return int(sorted_vals[idx])
