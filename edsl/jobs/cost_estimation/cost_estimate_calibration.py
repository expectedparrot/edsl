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

    Calibrates both answer_tokens (from raw_model_response.{q}_output_tokens)
    and thinking_tokens (from raw_model_response.{q}_thinking_tokens) when
    thinking token data is present.

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
    output_suffix = "_output_tokens"
    thinking_suffix = "_thinking_tokens"

    output_cols = {
        c[len(prefix) : -len(output_suffix)]: c
        for c in results.columns
        if c.startswith(prefix) and c.endswith(output_suffix)
    }
    thinking_cols = {
        c[len(prefix) : -len(thinking_suffix)]: c
        for c in results.columns
        if c.startswith(prefix) and c.endswith(thinking_suffix)
    }

    overrides: dict[str, TokenOverride | list[TokenOverride]] = {}

    for q, output_col in output_cols.items():
        thinking_col = thinking_cols.get(q)

        if by_model:
            select_cols = [output_col, "model.inference_service", "model.model"]
            if thinking_col:
                select_cols.insert(1, thinking_col)
            df = results.select(*select_cols).to_pandas()
            df = df.dropna(subset=[output_col])
            entries: list[TokenOverride] = []
            for (svc, mdl), grp in df.groupby(
                ["model.inference_service", "model.model"]
            ):
                output_vals = grp[output_col].tolist()
                thinking_tokens = None
                if thinking_col:
                    thinking_vals = grp[thinking_col].dropna().tolist()
                    if thinking_vals:
                        thinking_tokens = _percentile(thinking_vals, percentile)
                entries.append(
                    TokenOverride(
                        answer_tokens=_percentile(output_vals, percentile),
                        thinking_tokens=thinking_tokens,
                        service=svc,
                        model=mdl,
                        note=f"calibrated from pilot (n={len(output_vals)}, p{percentile})",
                    )
                )
            overrides[q] = entries
        else:
            df = results.select(output_col).to_pandas().dropna(subset=[output_col])
            output_vals = df[output_col].tolist()
            thinking_tokens = None
            if thinking_col:
                thinking_df = (
                    results.select(thinking_col)
                    .to_pandas()
                    .dropna(subset=[thinking_col])
                )
                thinking_vals = thinking_df[thinking_col].tolist()
                if thinking_vals:
                    thinking_tokens = _percentile(thinking_vals, percentile)
            overrides[q] = TokenOverride(
                answer_tokens=_percentile(output_vals, percentile),
                thinking_tokens=thinking_tokens,
                note=f"calibrated from pilot (n={len(output_vals)}, p{percentile})",
            )

    return overrides


def _percentile(values: list[float], p: int) -> int:
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * p / 100), len(sorted_vals) - 1)
    return int(sorted_vals[idx])
