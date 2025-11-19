"""
Weighting strategies for Results objects.

This module provides an abstract base class (WeightingStrategy) and concrete
implementations for different types of weighting algorithms. Each strategy
defines how to find optimal weights for a specific distribution type and
distance metric.

Strategy classes:
    - CategoricalKLStrategy: KL divergence minimization for categorical data
    - IterativeProportionalFittingStrategy: IPF algorithm for categorical data
    - BinnedContinuousKLStrategy: KL divergence for continuous data via binning
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
import numpy as np
from scipy.optimize import minimize


class WeightingStrategy(ABC):
    """Abstract base class for weighting strategies.

    Each strategy defines how to find optimal weights for a specific
    type of distribution (categorical, continuous, etc.) and distance
    metric (KL divergence, Wasserstein, etc.).

    Subclasses must implement:
        - find_weights(): Core algorithm to compute optimal weights
        - compute_metric(): Compute distance/divergence between distributions
        - validate_inputs(): Validate inputs for the strategy
    """

    @abstractmethod
    def find_weights(self, responses: List[Any], target: Any, **kwargs) -> np.ndarray:
        """Find optimal weights to match target distribution.

        Args:
            responses: List of responses from the survey
            target: Target distribution (format depends on strategy)
            **kwargs: Strategy-specific parameters

        Returns:
            np.ndarray: Normalized weights (sum to 1.0)
        """
        pass

    @abstractmethod
    def compute_metric(self, empirical_dist: Dict, target_dist: Dict) -> float:
        """Compute distance/divergence between distributions.

        Args:
            empirical_dist: The empirical (weighted) distribution
            target_dist: The target distribution

        Returns:
            float: Distance/divergence value (strategy-specific)
        """
        pass

    @abstractmethod
    def validate_inputs(self, responses: List[Any], target: Any) -> None:
        """Validate inputs for this strategy.

        Args:
            responses: List of responses
            target: Target distribution

        Raises:
            ValueError: If inputs are invalid for this strategy
        """
        pass

    def get_weighted_distribution(
        self, responses: List[Any], weights: np.ndarray
    ) -> Dict:
        """Compute weighted distribution from responses and weights.

        This default implementation works for categorical data. Can be
        overridden by subclasses for different data types.

        Args:
            responses: List of responses
            weights: Array of weights (same length as responses)

        Returns:
            dict: Weighted distribution (probabilities sum to 1.0)
        """
        if len(responses) != len(weights):
            raise ValueError(
                f"Length mismatch: {len(responses)} responses but {len(weights)} weights"
            )

        weighted_counts = {}
        for resp, w in zip(responses, weights):
            weighted_counts[resp] = weighted_counts.get(resp, 0.0) + w

        total = sum(weighted_counts.values())
        return {k: v / total for k, v in weighted_counts.items()}


class CategoricalKLStrategy(WeightingStrategy):
    """KL divergence minimization for categorical responses using scipy optimization.

    This strategy uses scipy's L-BFGS-B algorithm to minimize the KL divergence
    between the weighted empirical distribution and a target distribution. The
    optimization problem is convex and uses log-space parameterization to ensure
    positive weights.

    Args:
        optimization_method: scipy optimization method (default: "L-BFGS-B")
    """

    def __init__(self, optimization_method: str = "L-BFGS-B"):
        """Initialize the strategy.

        Args:
            optimization_method: scipy optimization method to use
        """
        self.optimization_method = optimization_method

    def validate_inputs(self, responses: List[Any], target: Dict[str, float]) -> None:
        """Validate inputs for categorical KL divergence.

        Args:
            responses: List of categorical responses
            target: Dictionary mapping categories to target probabilities

        Raises:
            ValueError: If target doesn't sum to 1.0 or if responses contain
                       categories not in target
        """
        # Validate target distribution sums to 1.0
        total = sum(target.values())
        if not np.isclose(total, 1.0, rtol=1e-5):
            raise ValueError(
                f"Target distribution probabilities must sum to 1.0, got {total}"
            )

        # Validate that all responses are in target_dist
        unique_responses = set(responses)
        missing_in_target = unique_responses - set(target.keys())
        if missing_in_target:
            raise ValueError(
                f"Responses {missing_in_target} are not present in target distribution. "
                f"All response categories must be included in target_dist."
            )

    def find_weights(
        self, responses: List[Any], target: Dict[str, float], **kwargs
    ) -> np.ndarray:
        """Find optimal weights using scipy optimization.

        Args:
            responses: List of categorical responses
            target: Dictionary with target probabilities for each category
            **kwargs: Additional arguments (ignored for this strategy)

        Returns:
            np.ndarray: Normalized weights that minimize KL divergence
        """
        self.validate_inputs(responses, target)

        n = len(responses)
        categories = list(target.keys())

        # Create indicator matrix: n x num_categories
        indicators = np.zeros((n, len(categories)))
        for i, resp in enumerate(responses):
            if resp in target:
                j = categories.index(resp)
                indicators[i, j] = 1

        # Objective function: KL divergence KL(P||Q)
        def kl_divergence(log_weights):
            weights = np.exp(log_weights)  # Ensure positivity
            weights = weights / weights.sum()  # Normalize

            # Compute weighted distribution P
            p = indicators.T @ weights

            # Compute KL divergence: Σ P(c) log(P(c)/Q(c))
            kl = 0.0
            for j, cat in enumerate(categories):
                if p[j] > 1e-10:  # Avoid log(0)
                    kl += p[j] * np.log(p[j] / target[cat])
            return kl

        # Initialize with uniform weights in log space
        log_w0 = np.zeros(n)

        # Optimize using specified method
        result = minimize(kl_divergence, log_w0, method=self.optimization_method)

        # Extract and normalize weights
        weights = np.exp(result.x)
        return weights / weights.sum()

    def compute_metric(self, empirical_dist: Dict, target_dist: Dict) -> float:
        """Compute KL divergence between empirical and target distributions.

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution

        Returns:
            float: The KL divergence KL(P||Q)
        """
        kl = 0.0
        for category in empirical_dist:
            p_c = empirical_dist[category]
            q_c = target_dist.get(category, 0.0)

            if p_c > 1e-10:  # Avoid log(0)
                if q_c < 1e-10:
                    # If target has 0 probability but empirical doesn't,
                    # KL divergence is infinite
                    return float("inf")
                kl += p_c * np.log(p_c / q_c)

        return kl


class IterativeProportionalFittingStrategy(WeightingStrategy):
    """Iterative Proportional Fitting (IPF) for categorical responses.

    This strategy uses a simpler iterative algorithm that updates weights
    proportionally to match the target distribution. It's easier to understand
    than optimization-based approaches but may converge more slowly.

    Args:
        max_iter: Maximum number of iterations (default: 100)
    """

    def __init__(self, max_iter: int = 100):
        """Initialize the strategy.

        Args:
            max_iter: Maximum number of iterations
        """
        self.max_iter = max_iter

    def validate_inputs(self, responses: List[Any], target: Dict[str, float]) -> None:
        """Validate inputs for IPF.

        Args:
            responses: List of categorical responses
            target: Dictionary mapping categories to target probabilities

        Raises:
            ValueError: If target doesn't sum to 1.0 or if responses contain
                       categories not in target
        """
        # Same validation as CategoricalKLStrategy
        total = sum(target.values())
        if not np.isclose(total, 1.0, rtol=1e-5):
            raise ValueError(
                f"Target distribution probabilities must sum to 1.0, got {total}"
            )

        unique_responses = set(responses)
        missing_in_target = unique_responses - set(target.keys())
        if missing_in_target:
            raise ValueError(
                f"Responses {missing_in_target} are not present in target distribution. "
                f"All response categories must be included in target_dist."
            )

    def find_weights(
        self,
        responses: List[Any],
        target: Dict[str, float],
        max_iter: Optional[int] = None,
        **kwargs,
    ) -> np.ndarray:
        """Find optimal weights using Iterative Proportional Fitting.

        Args:
            responses: List of categorical responses
            target: Dictionary with target probabilities for each category
            max_iter: Override default max_iter if provided
            **kwargs: Additional arguments (ignored)

        Returns:
            np.ndarray: Normalized weights
        """
        self.validate_inputs(responses, target)

        n = len(responses)
        weights = np.ones(n)
        iterations = max_iter if max_iter is not None else self.max_iter

        for iteration in range(iterations):
            # Compute current weighted distribution
            current_dist = {}
            for i, resp in enumerate(responses):
                current_dist[resp] = current_dist.get(resp, 0.0) + weights[i]

            # Normalize current distribution
            total = sum(current_dist.values())
            for key in current_dist:
                current_dist[key] /= total

            # Update weights proportionally
            for i, resp in enumerate(responses):
                if current_dist[resp] > 1e-10:  # Avoid division by zero
                    weights[i] *= target[resp] / current_dist[resp]

        # Normalize and return
        return weights / weights.sum()

    def compute_metric(self, empirical_dist: Dict, target_dist: Dict) -> float:
        """Compute KL divergence (same as CategoricalKLStrategy).

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution

        Returns:
            float: The KL divergence KL(P||Q)
        """
        kl = 0.0
        for category in empirical_dist:
            p_c = empirical_dist[category]
            q_c = target_dist.get(category, 0.0)

            if p_c > 1e-10:
                if q_c < 1e-10:
                    return float("inf")
                kl += p_c * np.log(p_c / q_c)

        return kl


class BinnedContinuousKLStrategy(WeightingStrategy):
    """KL divergence minimization for continuous responses via binning.

    This strategy converts continuous numerical responses into discrete bins
    and then applies categorical KL divergence minimization. Useful for
    continuous variables like age, income, Likert scales, etc.

    Args:
        bins: List of bin edges, or int for number of bins, or None for auto
        optimization_method: scipy optimization method (default: "L-BFGS-B")
    """

    def __init__(
        self,
        bins: Optional[Union[List[float], int]] = None,
        optimization_method: str = "L-BFGS-B",
    ):
        """Initialize the strategy.

        Args:
            bins: Bin edges (list), number of bins (int), or None for auto
            optimization_method: scipy optimization method to use
        """
        self.bins = bins
        self.categorical_strategy = CategoricalKLStrategy(optimization_method)

    def _create_bins(self, responses: List[float]) -> np.ndarray:
        """Create bin edges from responses.

        Args:
            responses: List of numerical responses

        Returns:
            np.ndarray: Bin edges
        """
        if self.bins is None:
            # Auto: use Sturges' rule for number of bins
            n_bins = int(np.ceil(np.log2(len(responses)) + 1))
            return np.linspace(min(responses), max(responses), n_bins + 1)
        elif isinstance(self.bins, int):
            # Number of bins specified
            return np.linspace(min(responses), max(responses), self.bins + 1)
        else:
            # Explicit bin edges provided
            return np.array(self.bins)

    def _discretize_responses(
        self, responses: List[float], bin_edges: np.ndarray
    ) -> Tuple[List[str], Dict[str, Tuple[float, float]]]:
        """Convert continuous responses to categorical bins.

        Args:
            responses: List of numerical responses
            bin_edges: Array of bin edges

        Returns:
            Tuple of (binned_responses, bin_mapping) where bin_mapping
            maps bin labels to (lower, upper) bounds
        """
        # Use numpy digitize to assign responses to bins
        bin_indices = np.digitize(responses, bin_edges[1:-1])

        # Create string labels for bins
        binned_responses = []
        bin_mapping = {}

        for i in range(len(bin_edges) - 1):
            lower = bin_edges[i]
            upper = bin_edges[i + 1]
            label = f"[{lower:.2f}, {upper:.2f})"
            bin_mapping[label] = (lower, upper)

        # Map responses to labels
        for idx in bin_indices:
            lower = bin_edges[idx]
            upper = bin_edges[idx + 1]
            label = f"[{lower:.2f}, {upper:.2f})"
            binned_responses.append(label)

        return binned_responses, bin_mapping

    def _convert_target_to_bins(
        self,
        target: Dict[Tuple[float, float], float],
        bin_mapping: Dict[str, Tuple[float, float]],
    ) -> Dict[str, float]:
        """Convert target distribution with tuple keys to bin labels.

        Args:
            target: Dictionary mapping (lower, upper) tuples to probabilities
            bin_mapping: Dictionary mapping bin labels to (lower, upper) tuples

        Returns:
            dict: Target distribution with bin labels as keys
        """
        target_binned = {}

        for label, (lower, upper) in bin_mapping.items():
            # Find matching range in target
            prob = 0.0
            for (t_lower, t_upper), t_prob in target.items():
                # Check if bins overlap/match
                if np.isclose(lower, t_lower) and np.isclose(upper, t_upper):
                    prob = t_prob
                    break

            if prob == 0.0:
                # Try to find any overlapping range
                for (t_lower, t_upper), t_prob in target.items():
                    if t_lower <= lower < t_upper or t_lower < upper <= t_upper:
                        prob += t_prob

            target_binned[label] = prob

        # Renormalize in case of rounding errors
        total = sum(target_binned.values())
        if total > 0:
            target_binned = {k: v / total for k, v in target_binned.items()}

        return target_binned

    def validate_inputs(
        self, responses: List[float], target: Dict[Tuple[float, float], float]
    ) -> None:
        """Validate inputs for binned continuous strategy.

        Args:
            responses: List of numerical responses
            target: Dictionary mapping (lower, upper) bin ranges to probabilities

        Raises:
            ValueError: If inputs are invalid
        """
        # Check that responses are numeric
        try:
            [float(r) for r in responses]
        except (ValueError, TypeError):
            raise ValueError("All responses must be numeric for continuous binning")

        # Validate target distribution sums to 1.0
        total = sum(target.values())
        if not np.isclose(total, 1.0, rtol=1e-5):
            raise ValueError(
                f"Target distribution probabilities must sum to 1.0, got {total}"
            )

    def find_weights(
        self,
        responses: List[float],
        target: Dict[Tuple[float, float], float],
        **kwargs,
    ) -> np.ndarray:
        """Find optimal weights for continuous responses via binning.

        Args:
            responses: List of numerical responses
            target: Dictionary mapping (lower, upper) bin ranges to probabilities
            **kwargs: Additional arguments passed to categorical strategy

        Returns:
            np.ndarray: Normalized weights that minimize KL divergence
        """
        self.validate_inputs(responses, target)

        # Create bins
        bin_edges = self._create_bins(responses)

        # Discretize responses
        binned_responses, bin_mapping = self._discretize_responses(responses, bin_edges)

        # Convert target to use bin labels
        target_binned = self._convert_target_to_bins(target, bin_mapping)

        # Use categorical strategy on binned data
        return self.categorical_strategy.find_weights(
            binned_responses, target_binned, **kwargs
        )

    def compute_metric(self, empirical_dist: Dict, target_dist: Dict) -> float:
        """Compute KL divergence (delegates to categorical strategy).

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution

        Returns:
            float: The KL divergence KL(P||Q)
        """
        return self.categorical_strategy.compute_metric(empirical_dist, target_dist)
