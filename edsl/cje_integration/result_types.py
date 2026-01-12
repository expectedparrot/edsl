"""Result types for CJE integration with EDSL.

Wraps CJE's EstimationResult with EDSL-specific conveniences.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any, Optional, List


@dataclass
class ComparisonResult:
    """Result of comparing two policies."""

    policy_a: str
    policy_b: str
    difference: float
    se_difference: float
    z_score: float
    p_value: float
    significant: bool

    def __repr__(self) -> str:
        sig = "significant" if self.significant else "not significant"
        return (
            f"ComparisonResult({self.policy_a} vs {self.policy_b}: "
            f"diff={self.difference:.3f}, p={self.p_value:.3f}, {sig})"
        )


@dataclass
class CalibrationResult:
    """Result of calibrating AI responses against oracle labels.

    Wraps CJE's EstimationResult with EDSL-specific conveniences.

    Attributes:
        estimates: Point estimates per policy (e.g., {'gpt-4o': 0.72})
        standard_errors: Standard errors per policy
        confidence_intervals: 95% CIs per policy as (lower, upper) tuples
        n_oracle: Number of oracle-labeled samples used for calibration
        n_total: Total number of samples
        calibration_rmse: Root mean squared error of calibration fit
        overall_status: Quality status ("GOOD", "WARNING", "CRITICAL")
        _cje_result: Raw CJE EstimationResult for advanced use
    """

    estimates: Dict[str, float]
    standard_errors: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    n_oracle: int
    n_total: int
    calibration_rmse: Optional[float]
    overall_status: str
    _cje_result: Any  # CJE EstimationResult

    def compare(self, policy_a: str, policy_b: str, alpha: float = 0.05) -> ComparisonResult:
        """Compare two policies statistically.

        Args:
            policy_a: First policy name
            policy_b: Second policy name
            alpha: Significance level (default 0.05)

        Returns:
            ComparisonResult with difference, p-value, and significance
        """
        policies = list(self.estimates.keys())
        if policy_a not in policies:
            raise ValueError(f"Policy '{policy_a}' not found. Available: {policies}")
        if policy_b not in policies:
            raise ValueError(f"Policy '{policy_b}' not found. Available: {policies}")

        idx_a = policies.index(policy_a)
        idx_b = policies.index(policy_b)

        comparison = self._cje_result.compare_policies(idx_a, idx_b, alpha=alpha)

        return ComparisonResult(
            policy_a=policy_a,
            policy_b=policy_b,
            difference=comparison["difference"],
            se_difference=comparison["se_difference"],
            z_score=comparison["z_score"],
            p_value=comparison["p_value"],
            significant=comparison["significant"],
        )

    def best_policy(self) -> str:
        """Return policy with highest estimate."""
        return max(self.estimates.items(), key=lambda x: x[1])[0]

    def ranking(self) -> List[str]:
        """Return policies ranked by estimate (best first)."""
        return [p for p, _ in sorted(self.estimates.items(), key=lambda x: -x[1])]

    def summary(self) -> str:
        """Human-readable summary of calibration results."""
        lines = [
            f"Calibration Results ({self.overall_status})",
            f"Oracle samples: {self.n_oracle}/{self.n_total} ({100*self.n_oracle/self.n_total:.1f}%)",
            "",
            "Policy Estimates:",
        ]
        for policy in self.ranking():
            est = self.estimates[policy]
            ci = self.confidence_intervals[policy]
            lines.append(f"  {policy}: {est:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()

    def _repr_html_(self) -> str:
        """Rich HTML display for Jupyter notebooks."""
        rows = []
        for policy in self.ranking():
            est = self.estimates[policy]
            se = self.standard_errors[policy]
            ci = self.confidence_intervals[policy]
            rows.append(
                f"<tr><td>{policy}</td><td>{est:.3f}</td>"
                f"<td>{se:.3f}</td><td>[{ci[0]:.3f}, {ci[1]:.3f}]</td></tr>"
            )

        return f"""
        <div style="font-family: monospace;">
            <h4>Calibration Results ({self.overall_status})</h4>
            <p>Oracle samples: {self.n_oracle}/{self.n_total} ({100*self.n_oracle/self.n_total:.1f}%)</p>
            <table style="border-collapse: collapse; border: 1px solid #ddd;">
                <thead style="background-color: #f0f0f0;">
                    <tr><th>Policy</th><th>Estimate</th><th>Std Error</th><th>95% CI</th></tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        """
