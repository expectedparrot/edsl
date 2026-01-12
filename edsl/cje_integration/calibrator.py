"""CJE Calibrator wrapper for EDSL.

Wraps CJE's analyze_dataset() function with EDSL-specific conveniences.
"""

import logging
import warnings
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from .data_adapters import results_to_fresh_draws, get_oracle_coverage
from .result_types import CalibrationResult

if TYPE_CHECKING:
    from ..results import Results


class CJECalibrator:
    """Calibrate AI survey responses against human oracle labels.

    Uses CJE (Causal Judge Evaluation) to calibrate judge scores against
    sparse oracle labels, providing valid estimates with proper uncertainty
    quantification.

    This wrapper uses CJE's Direct mode (isotonic regression calibration)
    since EDSL doesn't store model logprobs needed for IPS/DR modes.

    Example:
        >>> from edsl import Survey, Model
        >>> from edsl.cje_integration import CJECalibrator

        >>> # Run survey
        >>> results = survey.by([Model("gpt-4o"), Model("claude-3-5-sonnet")]).run()

        >>> # Collect human labels for some samples (None = no label)
        >>> human_labels = [5, None, 3, None, 4, ...]

        >>> # Calibrate
        >>> calibrator = CJECalibrator()
        >>> cal_result = calibrator.calibrate(
        ...     results,
        ...     question_name="sentiment_score",
        ...     oracle_labels=human_labels,
        ... )

        >>> print(cal_result.estimates)
        {'gpt-4o': 0.72, 'claude-3-5-sonnet': 0.68}
    """

    def __init__(
        self,
        calibration_mode: str = "monotone",
        verbose: bool = False,
    ):
        """Initialize the calibrator.

        Args:
            calibration_mode: Calibration mode for isotonic regression.
                - "monotone": Standard isotonic regression (default)
                - "two_stage": Two-stage with covariates
                - "auto": Let CJE decide
            verbose: Whether to print progress messages
        """
        self.calibration_mode = calibration_mode
        self.verbose = verbose

    def calibrate(
        self,
        results: "Results",
        question_name: str,
        oracle_labels: List[Any],
        policy_column: str = "model",
        score_transform: Optional[callable] = None,
        min_oracle_fraction: float = 0.01,
    ) -> CalibrationResult:
        """Calibrate AI responses against oracle labels.

        Args:
            results: EDSL Results object containing survey responses
            question_name: Name of question containing judge scores
            oracle_labels: List of oracle (human) labels, same length as results.
                Use None for samples without labels.
            policy_column: How to identify policies ("model", "agent", or column name)
            score_transform: Optional function to transform scores to [0,1]
            min_oracle_fraction: Minimum fraction of oracle labels required

        Returns:
            CalibrationResult with estimates, CIs, and diagnostics

        Raises:
            ImportError: If cje-eval is not installed
            ValueError: If insufficient oracle labels or invalid data
        """
        try:
            from cje import analyze_dataset
        except ImportError:
            raise ImportError(
                "cje-eval is required for calibration. "
                "Install with: pip install cje-eval"
            )

        # Convert EDSL Results to CJE format
        fresh_draws = results_to_fresh_draws(
            results,
            question_name=question_name,
            oracle_labels=oracle_labels,
            policy_column=policy_column,
            score_transform=score_transform,
        )

        if not fresh_draws:
            raise ValueError(
                f"No valid samples found. Check that question '{question_name}' "
                "has numeric answers."
            )

        # Check oracle coverage
        coverage = get_oracle_coverage(fresh_draws)
        total_samples = sum(len(s) for s in fresh_draws.values())
        total_oracle = sum(
            sum(1 for s in samples if "oracle_label" in s)
            for samples in fresh_draws.values()
        )

        if total_oracle == 0:
            raise ValueError(
                "No oracle labels found. "
                "Provide human labels (use None for unlabeled samples)."
            )

        oracle_fraction = total_oracle / total_samples
        if oracle_fraction < min_oracle_fraction:
            raise ValueError(
                f"Only {oracle_fraction:.1%} of samples have oracle labels "
                f"(minimum {min_oracle_fraction:.1%} required). "
                "Add more human labels."
            )

        if self.verbose:
            print(f"Calibrating with {total_oracle}/{total_samples} oracle labels")
            print(f"Policies: {list(fresh_draws.keys())}")

        # Run CJE analysis (suppress internal CJE messages for cleaner UX)
        # Temporarily suppress CJE logger warnings
        cje_logger = logging.getLogger("cje")
        original_level = cje_logger.level
        cje_logger.setLevel(logging.ERROR)
        try:
            cje_result = analyze_dataset(
                fresh_draws_data=fresh_draws,
                estimator="direct",
                verbose=False,  # We handle our own messaging
            )
        finally:
            cje_logger.setLevel(original_level)

        # Extract policies from metadata
        policies = cje_result.metadata.get("target_policies", list(fresh_draws.keys()))

        # Build EDSL-friendly result
        estimates = {}
        standard_errors = {}
        confidence_intervals = {}

        ci_lower, ci_upper = cje_result.confidence_interval()

        for i, policy in enumerate(policies):
            estimates[policy] = float(cje_result.estimates[i])
            standard_errors[policy] = float(cje_result.standard_errors[i])
            confidence_intervals[policy] = (float(ci_lower[i]), float(ci_upper[i]))

        # Get calibration RMSE from diagnostics if available
        calibration_rmse = None
        if cje_result.diagnostics and hasattr(cje_result.diagnostics, "calibration_rmse"):
            calibration_rmse = cje_result.diagnostics.calibration_rmse

        # Determine overall status
        overall_status = "GOOD"
        if cje_result.diagnostics:
            if hasattr(cje_result.diagnostics, "overall_status"):
                overall_status = cje_result.diagnostics.overall_status.value.upper()

        return CalibrationResult(
            estimates=estimates,
            standard_errors=standard_errors,
            confidence_intervals=confidence_intervals,
            n_oracle=total_oracle,
            n_total=total_samples,
            calibration_rmse=calibration_rmse,
            overall_status=overall_status,
            _cje_result=cje_result,
        )


def calibrate(
    results: "Results",
    question_name: str,
    oracle_labels: List[Any],
    policy_column: str = "model",
    score_transform: Optional[callable] = None,
    verbose: bool = False,
) -> CalibrationResult:
    """Convenience function for one-shot calibration.

    Equivalent to:
        CJECalibrator(verbose=verbose).calibrate(results, ...)

    Example:
        >>> from edsl.cje_integration import calibrate
        >>> human_labels = [5, None, 3, None, ...]
        >>> result = calibrate(
        ...     results,
        ...     question_name="sentiment",
        ...     oracle_labels=human_labels,
        ... )
    """
    calibrator = CJECalibrator(verbose=verbose)
    return calibrator.calibrate(
        results,
        question_name=question_name,
        oracle_labels=oracle_labels,
        policy_column=policy_column,
        score_transform=score_transform,
    )
