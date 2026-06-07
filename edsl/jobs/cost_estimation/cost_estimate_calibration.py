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
                    Use 50 for median or a higher value (75-90) for a conservative
                    budget estimate.
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
    """Return the p-th percentile of values using linear interpolation.

    Computes a float index into the sorted list, then interpolates between
    the two surrounding values. This matches numpy.percentile(method='linear')
    and correctly returns the average of the two middle elements for even-length
    lists at p=50 (e.g. [10, 20, 30, 40] -> 25, not 30).

    Args:
        values: list of numeric values
        p:      percentile to compute, 0-100 inclusive

    Returns:
        Interpolated percentile value truncated to int, or 0 for an empty list.
    """
    if not values:
        return 0
    sorted_values = sorted(values)
    count = len(sorted_values)
    # A float index in [0, count-1] that maps p=0 to the first element
    # and p=100 to the last, with fractional positions in between.
    float_index = (count - 1) * p / 100
    lower_idx = int(float_index)
    upper_idx = min(lower_idx + 1, count - 1)
    # How far float_index sits between lower_idx and upper_idx (0.0 to 1.0).
    fraction = float_index - lower_idx
    interpolated = sorted_values[lower_idx] + fraction * (
        sorted_values[upper_idx] - sorted_values[lower_idx]
    )
    return int(interpolated)
