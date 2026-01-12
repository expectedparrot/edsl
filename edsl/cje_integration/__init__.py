"""CJE Integration for EDSL.

Provides calibrated evaluation of AI survey responses against human ground truth
using CJE (Causal Judge Evaluation).

Key Features:
- Calibrate with 5-10% human labels to get valid estimates for full dataset
- Proper uncertainty quantification with confidence intervals
- Compare policies statistically

Basic Usage:
    >>> from edsl import Survey, Model
    >>> from edsl.cje_integration import calibrate

    >>> # Run survey with AI agents
    >>> results = survey.by([Model("gpt-4o"), Model("claude-3-5-sonnet")]).run()

    >>> # Collect human ratings for ~10% of samples (None = no label)
    >>> human_labels = [5, None, 3, None, 4, ...]

    >>> # Calibrate and get estimates
    >>> cal_result = calibrate(
    ...     results,
    ...     question_name="sentiment_score",
    ...     oracle_labels=human_labels,
    ... )

    >>> print(cal_result.estimates)
    {'gpt-4o': 0.72, 'claude-3-5-sonnet': 0.68}

    >>> print(cal_result.confidence_intervals)
    {'gpt-4o': (0.68, 0.76), 'claude-3-5-sonnet': (0.64, 0.72)}

    >>> # Statistical comparison
    >>> comparison = cal_result.compare("gpt-4o", "claude-3-5-sonnet")
    >>> print(f"p-value: {comparison.p_value:.3f}")

Requirements:
    pip install cje-eval
"""

from .calibrator import CJECalibrator, calibrate
from .result_types import CalibrationResult, ComparisonResult
from .data_adapters import results_to_fresh_draws

__all__ = [
    "CJECalibrator",
    "calibrate",
    "CalibrationResult",
    "ComparisonResult",
    "results_to_fresh_draws",
]
