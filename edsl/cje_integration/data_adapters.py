"""Data adapters for converting EDSL Results to CJE format.

CJE (Causal Judge Evaluation) expects data in a specific format.
This module provides utilities to convert EDSL Results objects
to the format expected by CJE's analyze_dataset() function.
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
import hashlib

if TYPE_CHECKING:
    from ..results import Results


def _make_prompt_id(result: Any, index: int) -> str:
    """Create a stable prompt_id for a Result.

    Uses scenario attributes if available, otherwise falls back to index.
    """
    # Try to get scenario key attributes
    if hasattr(result, "scenario") and result.scenario:
        scenario = result.scenario
        # Use scenario's hash if available
        if hasattr(scenario, "to_dict"):
            scenario_str = str(sorted(scenario.to_dict().items()))
            return hashlib.md5(scenario_str.encode()).hexdigest()[:12]

    # Fall back to index-based ID
    return f"sample_{index}"


def results_to_fresh_draws(
    results: "Results",
    question_name: str,
    oracle_column: Optional[str] = None,
    policy_column: str = "model",
    score_transform: Optional[callable] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Convert EDSL Results to CJE fresh_draws_data format.

    This adapter converts EDSL survey results to the format expected by
    CJE's analyze_dataset() function for Direct mode evaluation.

    Args:
        results: EDSL Results object containing survey responses
        question_name: Name of the question containing judge scores.
            The answer to this question will be used as the judge_score.
        oracle_column: Optional name of a created column containing oracle labels.
            If None, no oracle labels are included.
        policy_column: How to identify policies. Options:
            - "model": Use the model name (default)
            - "agent": Use agent persona
            - Any column name in the results
        score_transform: Optional function to transform scores to [0,1].
            Example: For 1-5 scale, use `lambda x: (x - 1) / 4`

    Returns:
        Dict mapping policy names to lists of records:
        {
            "gpt-4o": [
                {"prompt_id": "abc123", "judge_score": 0.8, "oracle_label": 0.75},
                {"prompt_id": "def456", "judge_score": 0.6},
                ...
            ],
            "claude-3-5-sonnet": [...],
        }

    Example:
        >>> results = survey.by(models).run()
        >>> results = results.add_column("human_rating", human_labels)
        >>> fresh_draws = results_to_fresh_draws(
        ...     results,
        ...     question_name="sentiment_score",
        ...     oracle_column="human_rating",
        ... )
        >>> # Pass to CJE
        >>> from cje import analyze_dataset
        >>> cje_result = analyze_dataset(fresh_draws_data=fresh_draws)
    """
    fresh_draws: Dict[str, List[Dict[str, Any]]] = {}

    for i, result in enumerate(results):
        # Get policy identifier
        if policy_column == "model":
            if hasattr(result, "model") and hasattr(result.model, "model"):
                policy = result.model.model
            else:
                policy = str(getattr(result, "model", "unknown"))
        elif policy_column == "agent":
            if hasattr(result, "agent"):
                agent = result.agent
                if hasattr(agent, "traits") and "persona" in agent.traits:
                    policy = agent.traits["persona"]
                else:
                    policy = str(agent)
            else:
                policy = "unknown"
        else:
            # Try to get from combined_dict
            if hasattr(result, "combined_dict") and policy_column in result.combined_dict:
                policy = str(result.combined_dict[policy_column])
            else:
                policy = "unknown"

        # Initialize policy list if needed
        if policy not in fresh_draws:
            fresh_draws[policy] = []

        # Get judge score
        if hasattr(result, "__getitem__"):
            try:
                answer = result["answer"]
                if question_name in answer:
                    judge_score = answer[question_name]
                else:
                    # Try full question name path
                    judge_score = None
            except (KeyError, TypeError):
                judge_score = None
        else:
            judge_score = None

        if judge_score is None:
            # Skip samples without judge scores
            continue

        # Transform score if needed
        if score_transform is not None:
            judge_score = score_transform(judge_score)

        # Build record
        record: Dict[str, Any] = {
            "prompt_id": _make_prompt_id(result, i),
            "judge_score": float(judge_score),
        }

        # Add oracle label if available
        if oracle_column is not None:
            oracle_label = None
            if hasattr(result, "combined_dict") and oracle_column in result.combined_dict:
                oracle_label = result.combined_dict[oracle_column]
            elif hasattr(result, "__getitem__"):
                try:
                    val = result[oracle_column]
                    # Only use if it's a number (not a dict or other type)
                    if isinstance(val, (int, float)):
                        oracle_label = val
                except (KeyError, TypeError):
                    pass

            if oracle_label is not None:
                if score_transform is not None:
                    oracle_label = score_transform(oracle_label)
                record["oracle_label"] = float(oracle_label)

        fresh_draws[policy].append(record)

    return fresh_draws


def get_policy_sample_counts(fresh_draws: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    """Get sample counts per policy."""
    return {policy: len(samples) for policy, samples in fresh_draws.items()}


def get_oracle_coverage(fresh_draws: Dict[str, List[Dict[str, Any]]]) -> Dict[str, float]:
    """Get fraction of samples with oracle labels per policy."""
    coverage = {}
    for policy, samples in fresh_draws.items():
        if not samples:
            coverage[policy] = 0.0
            continue
        n_oracle = sum(1 for s in samples if "oracle_label" in s)
        coverage[policy] = n_oracle / len(samples)
    return coverage
