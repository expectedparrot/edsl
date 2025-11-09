"""
Results weighting functionality for KL divergence minimization.

This module provides the ResultsWeighting class which handles weighting operations
for Results objects, including finding optimal weights that minimize KL divergence
between empirical and target distributions.
"""

import numpy as np
from scipy.optimize import minimize
from collections import Counter
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Results


class ResultsWeighting:
    """
    Handles weighting operations for Results objects to minimize KL divergence.

    This class implements algorithms to find optimal weights for survey responses
    such that the weighted empirical distribution matches a target distribution
    as closely as possible (minimizing KL divergence).

    The problem formulation:
    Given responses x₁, x₂, ..., xₙ and a target distribution Q over categories,
    find weights w₁, w₂, ..., wₙ that minimize KL(P||Q) where P is the weighted
    empirical distribution:
        P(c) = Σᵢ wᵢ · 𝟙(xᵢ = c) / Σᵢ wᵢ

    Two algorithms are provided:
    1. Optimization-based approach using scipy (more accurate, convex problem)
    2. Iterative Proportional Fitting (simpler, iterative approach)
    """

    def __init__(self, results: "Results"):
        """
        Initialize the ResultsWeighting with a Results object.

        Args:
            results: The Results object to perform weighting operations on
        """
        self.results = results

    def find_optimal_weights(
        self,
        question_name: str,
        target_dist: Dict[str, float],
        method: str = "optimization",
        max_iter: int = 100,
    ) -> np.ndarray:
        """
        Find optimal weights to minimize KL divergence between empirical and target distributions.

        This method returns weights (same length as the results object) that, when applied
        to the responses for the specified question, minimize the KL divergence between
        the weighted empirical distribution and the target distribution.

        Args:
            question_name: The name of the question to compute weights for
            target_dist: Dictionary mapping category names to target probabilities.
                        Values should sum to 1.0.
            method: Algorithm to use - either "optimization" (scipy-based, default)
                   or "iterative" (iterative proportional fitting)
            max_iter: Maximum iterations for iterative method (ignored for optimization method)

        Returns:
            np.ndarray: Array of normalized weights, one for each result in the Results object.
                       Weights sum to 1.0.

        Raises:
            ValueError: If target_dist probabilities don't sum to ~1.0, if question_name
                       doesn't exist, or if target_dist contains categories not in the data.
            KeyError: If question_name is not found in the results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighting = ResultsWeighting(r)
            >>> target = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> weights = weighting.find_optimal_weights('how_feeling', target)
            >>> len(weights) == len(r)
            True
            >>> bool(abs(weights.sum() - 1.0) < 1e-6)
            True
        """
        # Validate target distribution sums to 1.0
        total = sum(target_dist.values())
        if not np.isclose(total, 1.0, rtol=1e-5):
            raise ValueError(
                f"Target distribution probabilities must sum to 1.0, got {total}"
            )

        # Get responses for the specified question
        try:
            responses = self.results.get_answers(question_name)
        except KeyError:
            raise KeyError(
                f"Question '{question_name}' not found in results. "
                f"Available questions: {self.results.question_names}"
            )

        n = len(responses)
        if n == 0:
            raise ValueError("No responses found for the specified question")

        # Validate that all responses are in target_dist
        unique_responses = set(responses)
        missing_in_target = unique_responses - set(target_dist.keys())
        if missing_in_target:
            raise ValueError(
                f"Responses {missing_in_target} are not present in target distribution. "
                f"All response categories must be included in target_dist."
            )

        # Use the selected method
        if method == "optimization":
            weights = self._optimize_weights(responses, target_dist)
        elif method == "iterative":
            weights = self._iterative_proportional_fitting(
                responses, target_dist, max_iter
            )
        else:
            raise ValueError(
                f"Unknown method '{method}'. Choose 'optimization' or 'iterative'"
            )

        return weights

    def _optimize_weights(
        self, responses: List[str], target_dist: Dict[str, float]
    ) -> np.ndarray:
        """
        Find optimal weights using scipy optimization.

        This method formulates the problem as a convex optimization problem and
        uses L-BFGS-B to find the optimal weights. The weights are parameterized
        in log space to ensure positivity.

        Args:
            responses: List of categorical responses
            target_dist: Dictionary with target probabilities for each category

        Returns:
            np.ndarray: Normalized weights that minimize KL divergence
        """
        n = len(responses)
        categories = list(target_dist.keys())

        # Create indicator matrix: n x num_categories
        # indicators[i, j] = 1 if responses[i] == categories[j], else 0
        indicators = np.zeros((n, len(categories)))
        for i, resp in enumerate(responses):
            if resp in target_dist:
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
                    kl += p[j] * np.log(p[j] / target_dist[cat])
            return kl

        # Initialize with uniform weights in log space
        log_w0 = np.zeros(n)

        # Optimize using L-BFGS-B
        result = minimize(kl_divergence, log_w0, method="L-BFGS-B")

        # Extract and normalize weights
        weights = np.exp(result.x)
        return weights / weights.sum()

    def _iterative_proportional_fitting(
        self, responses: List[str], target_dist: Dict[str, float], max_iter: int = 100
    ) -> np.ndarray:
        """
        Find optimal weights using Iterative Proportional Fitting (IPF).

        This is a simpler, iterative algorithm that updates weights proportionally
        to match the target distribution. It's easier to understand but may converge
        more slowly than the optimization approach.

        Args:
            responses: List of categorical responses
            target_dist: Dictionary with target probabilities for each category
            max_iter: Maximum number of iterations

        Returns:
            np.ndarray: Normalized weights
        """
        n = len(responses)
        weights = np.ones(n)

        for iteration in range(max_iter):
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
                    weights[i] *= target_dist[resp] / current_dist[resp]

        # Normalize and return
        return weights / weights.sum()

    def get_weighted_distribution(
        self, question_name: str, weights: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute the weighted empirical distribution for a question.

        Args:
            question_name: The name of the question
            weights: Array of weights (same length as results)

        Returns:
            Dictionary mapping response categories to their weighted probabilities

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighting = ResultsWeighting(r)
            >>> target = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> weights = weighting.find_optimal_weights('how_feeling', target)
            >>> dist = weighting.get_weighted_distribution('how_feeling', weights)
            >>> isinstance(dist, dict)
            True
        """
        responses = self.results.get_answers(question_name)

        if len(responses) != len(weights):
            raise ValueError(
                f"Length mismatch: {len(responses)} responses but {len(weights)} weights"
            )

        # Compute weighted counts
        weighted_counts = {}
        for resp, w in zip(responses, weights):
            weighted_counts[resp] = weighted_counts.get(resp, 0.0) + w

        # Normalize to probabilities
        total = sum(weighted_counts.values())
        return {k: v / total for k, v in weighted_counts.items()}

    def compute_kl_divergence(
        self, empirical_dist: Dict[str, float], target_dist: Dict[str, float]
    ) -> float:
        """
        Compute KL divergence between empirical and target distributions.

        Computes KL(P||Q) = Σ P(c) log(P(c)/Q(c))

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution

        Returns:
            float: The KL divergence value (always >= 0)

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighting = ResultsWeighting(r)
            >>> p = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> q = {'Great': 0.4, 'OK': 0.4, 'Terrible': 0.2}
            >>> kl = weighting.compute_kl_divergence(p, q)
            >>> bool(kl >= 0)
            True
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
