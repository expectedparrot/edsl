"""
Results weighting functionality for distribution matching.

This module provides the ResultsWeighting class which coordinates weighting
operations for Results objects. It uses a strategy pattern to support different
weighting algorithms and distribution types.

Strategies available:
    - categorical_kl: KL divergence minimization for categorical data (default)
    - categorical_ipf: Iterative Proportional Fitting for categorical data
    - continuous_binned: KL divergence for continuous data via binning

For implementation details, see results_weighting_strategies.py
"""

from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

# Lazy import for numpy to speed up module import time
_np = None


def _get_numpy():
    """Lazily import numpy module."""
    global _np
    if _np is None:
        import numpy as _np
    return _np


from .results_weighting_strategies import (
    WeightingStrategy,
    CategoricalKLStrategy,
    IterativeProportionalFittingStrategy,
    BinnedContinuousKLStrategy,
)

if TYPE_CHECKING:
    from . import Results


class ResultsWeighting:
    """
    Coordinator for weighting operations on Results objects.

    This class manages different weighting strategies and provides a unified
    interface for finding optimal weights that match target distributions.
    Uses the Strategy pattern to support multiple algorithms and data types.

    The general problem formulation:
    Given responses x₁, x₂, ..., xₙ and a target distribution Q,
    find weights w₁, w₂, ..., wₙ that minimize distance/divergence between
    the weighted empirical distribution P and Q.

    Attributes:
        results: The Results object to perform weighting on
        strategies: Dictionary of available weighting strategies

    Examples:
        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> weighter = ResultsWeighting(r)

        >>> # Categorical data with KL divergence
        >>> target = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
        >>> weights = weighter.find_optimal_weights('how_feeling', target)

        >>> # Continuous data with binning (requires numeric data)
        >>> # target_bins = {(0, 30): 0.3, (30, 50): 0.5, (50, 100): 0.2}
        >>> # weights = weighter.find_optimal_weights('age', target_bins, strategy='continuous_binned')
    """

    def __init__(self, results: "Results"):
        """
        Initialize the ResultsWeighting coordinator.

        Args:
            results: The Results object to perform weighting operations on
        """
        self.results = results

        # Initialize available strategies
        self._strategies: Dict[str, WeightingStrategy] = {
            "categorical_kl": CategoricalKLStrategy(),
            "categorical_ipf": IterativeProportionalFittingStrategy(),
            "continuous_binned": BinnedContinuousKLStrategy(),
        }

    def register_strategy(self, name: str, strategy: WeightingStrategy) -> None:
        """Register a custom weighting strategy.

        This allows users to add their own weighting algorithms without
        modifying the core code.

        Args:
            name: Name to identify the strategy
            strategy: Instance of a WeightingStrategy subclass

        Examples:
            >>> from edsl.results import Results
            >>> from edsl.results.results_weighting_strategies import WeightingStrategy
            >>> # Define custom strategy class...
            >>> # custom_strategy = MyCustomStrategy()
            >>> # weighter = ResultsWeighting(Results.example())
            >>> # weighter.register_strategy('my_method', custom_strategy)
        """
        if not isinstance(strategy, WeightingStrategy):
            raise TypeError(
                f"Strategy must be an instance of WeightingStrategy, got {type(strategy)}"
            )
        self._strategies[name] = strategy

    def list_strategies(self) -> List[str]:
        """List available strategy names.

        Returns:
            List of strategy names that can be used with find_optimal_weights

        Examples:
            >>> from edsl.results import Results
            >>> weighter = ResultsWeighting(Results.example())
            >>> strategies = weighter.list_strategies()
            >>> 'categorical_kl' in strategies
            True
        """
        return list(self._strategies.keys())

    def find_optimal_weights(
        self,
        question_name: str,
        target_dist: Union[Dict, Any],
        strategy: str = "categorical_kl",
        method: Optional[str] = None,
        max_iter: int = 100,
        **kwargs,
    ) -> "np.ndarray":
        """
        Find optimal weights to match a target distribution.

        This is the main entry point for computing weights. It delegates to
        the specified strategy to handle the actual computation.

        Args:
            question_name: Name of the question to compute weights for
            target_dist: Target distribution (format depends on strategy)
                        - For categorical: Dict[str, float] mapping categories to probabilities
                        - For continuous_binned: Dict[Tuple[float, float], float] mapping ranges to probabilities
            strategy: Strategy to use (default: "categorical_kl")
                     Options: "categorical_kl", "categorical_ipf", "continuous_binned"
            method: DEPRECATED - use strategy instead. For backward compatibility:
                   "optimization" -> "categorical_kl", "iterative" -> "categorical_ipf"
            max_iter: Maximum iterations for iterative methods
            **kwargs: Additional strategy-specific parameters

        Returns:
            np.ndarray: Normalized weights (sum to 1.0), one per result

        Raises:
            ValueError: If strategy is unknown or inputs are invalid
            KeyError: If question_name doesn't exist in results

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighter = ResultsWeighting(r)

            >>> # Categorical with KL divergence (default)
            >>> target = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> weights = weighter.find_optimal_weights('how_feeling', target)
            >>> len(weights) == len(r)
            True
            >>> bool(abs(weights.sum() - 1.0) < 1e-6)
            True

            >>> # Categorical with IPF
            >>> weights = weighter.find_optimal_weights('how_feeling', target, strategy='categorical_ipf')

            >>> # Continuous with binning
            >>> target_bins = {(0.0, 2.5): 0.5, (2.5, 5.0): 0.5}
            >>> # weights = weighter.find_optimal_weights('some_score', target_bins, strategy='continuous_binned')
        """
        # Handle backward compatibility with old 'method' parameter
        if method is not None:
            import warnings

            warnings.warn(
                "The 'method' parameter is deprecated. Use 'strategy' instead. "
                "'method=\"optimization\"' -> 'strategy=\"categorical_kl\"', "
                "'method=\"iterative\"' -> 'strategy=\"categorical_ipf\"'",
                DeprecationWarning,
                stacklevel=2,
            )
            if method == "optimization":
                strategy = "categorical_kl"
            elif method == "iterative":
                strategy = "categorical_ipf"
            else:
                raise ValueError(
                    f"Unknown method '{method}'. Use strategy parameter instead."
                )

        # Get responses for the specified question
        try:
            responses = self.results.get_answers(question_name)
        except KeyError:
            raise KeyError(
                f"Question '{question_name}' not found in results. "
                f"Available questions: {self.results.question_names}"
            )

        if len(responses) == 0:
            raise ValueError("No responses found for the specified question")

        # Get the strategy
        strategy_obj = self._strategies.get(strategy)
        if strategy_obj is None:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Available strategies: {self.list_strategies()}"
            )

        # Delegate to strategy
        return strategy_obj.find_weights(
            responses, target_dist, max_iter=max_iter, **kwargs
        )

    def get_weighted_distribution(
        self,
        question_name: str,
        weights: "np.ndarray",
        strategy: str = "categorical_kl",
    ) -> Dict:
        """
        Compute the weighted empirical distribution for a question.

        Args:
            question_name: The name of the question
            weights: Array of weights (same length as results)
            strategy: Strategy to use for computing distribution (default: "categorical_kl")

        Returns:
            Dictionary mapping response values to their weighted probabilities

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighter = ResultsWeighting(r)
            >>> target = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> weights = weighter.find_optimal_weights('how_feeling', target)
            >>> dist = weighter.get_weighted_distribution('how_feeling', weights)
            >>> isinstance(dist, dict)
            True
        """
        responses = self.results.get_answers(question_name)

        strategy_obj = self._strategies.get(strategy)
        if strategy_obj is None:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Available strategies: {self.list_strategies()}"
            )

        return strategy_obj.get_weighted_distribution(responses, weights)

    def compute_kl_divergence(self, empirical_dist: Dict, target_dist: Dict) -> float:
        """
        Compute KL divergence between empirical and target distributions.

        Computes KL(P||Q) = Σ P(c) log(P(c)/Q(c))

        This is a convenience method that delegates to the categorical KL strategy.

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution

        Returns:
            float: The KL divergence value (always >= 0)

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighter = ResultsWeighting(r)
            >>> p = {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
            >>> q = {'Great': 0.4, 'OK': 0.4, 'Terrible': 0.2}
            >>> kl = weighter.compute_kl_divergence(p, q)
            >>> bool(kl >= 0)
            True
        """
        # Use categorical KL strategy for metric computation
        strategy = self._strategies["categorical_kl"]
        return strategy.compute_metric(empirical_dist, target_dist)

    def compute_metric(
        self, empirical_dist: Dict, target_dist: Dict, strategy: str = "categorical_kl"
    ) -> float:
        """
        Compute distance/divergence metric using specified strategy.

        More general version of compute_kl_divergence that allows specifying
        which strategy's metric to use.

        Args:
            empirical_dist: The empirical (actual) distribution
            target_dist: The target distribution
            strategy: Strategy whose metric to use (default: "categorical_kl")

        Returns:
            float: The distance/divergence value
        """
        strategy_obj = self._strategies.get(strategy)
        if strategy_obj is None:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Available strategies: {self.list_strategies()}"
            )

        return strategy_obj.compute_metric(empirical_dist, target_dist)

    def find_weights_for_multiple_targets(
        self,
        targets: Dict[str, Union[Dict, Any]],
        metric_weights: Optional[Dict[str, float]] = None,
        strategies: Optional[Dict[str, str]] = None,
        aggregation: str = "weighted_sum",
        **kwargs,
    ) -> "np.ndarray":
        """
        Find optimal weights that simultaneously match multiple target distributions.

        This method extends single-target weighting to handle multiple questions at once,
        finding a single set of weights that balances matching all target distributions.
        This is useful for survey reweighting where you need to match multiple marginal
        distributions (e.g., age AND gender AND location).

        Args:
            targets: Dictionary mapping question names to their target distributions
                    Format: {question_name: target_dist}
                    Example: {'age': {(0,30): 0.3, (30,50): 0.7}, 'gender': {'M': 0.5, 'F': 0.5}}
            metric_weights: Dictionary of relative importance for each question (will be normalized)
                           Default: equal weights for all questions
                           Example: {'age': 2.0, 'gender': 1.0} means age is 2x more important
            strategies: Dictionary mapping question names to strategy names
                       Default: "categorical_kl" for all questions
                       Example: {'age': 'continuous_binned', 'gender': 'categorical_kl'}
            aggregation: How to combine metrics across questions
                        - "weighted_sum" (default): Σᵢ αᵢ * metric_i
                        - "max": max(α₁*metric₁, α₂*metric₂, ...)
                        - "weighted_product": Πᵢ metric_i^αᵢ
            **kwargs: Additional parameters passed to optimization

        Returns:
            np.ndarray: Normalized weights (sum to 1.0) that balance all target distributions

        Raises:
            ValueError: If targets is empty, strategies are invalid, or aggregation is unknown
            KeyError: If question names don't exist in results

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> weighter = ResultsWeighting(r)

            >>> # Match two distributions simultaneously
            >>> targets = {
            ...     'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            ...     'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
            ... }
            >>> weights = weighter.find_weights_for_multiple_targets(targets)
            >>> len(weights) == len(r)
            True
            >>> bool(abs(weights.sum() - 1.0) < 1e-6)
            True

            >>> # With custom importance weights (age 2x more important than gender)
            >>> metric_weights = {'how_feeling': 2.0, 'how_feeling_yesterday': 1.0}
            >>> weights = weighter.find_weights_for_multiple_targets(targets, metric_weights)
        """
        from scipy.optimize import minimize

        if not targets:
            raise ValueError("targets dictionary cannot be empty")

        # Normalize metric weights
        if metric_weights is None:
            metric_weights = {q: 1.0 for q in targets.keys()}
        else:
            # Auto-normalize to sum to 1.0
            total = sum(metric_weights.values())
            metric_weights = {q: w / total for q, w in metric_weights.items()}

        # Set default strategies
        if strategies is None:
            strategies = {q: "categorical_kl" for q in targets.keys()}

        # Validate all questions exist and strategies are valid
        for question_name in targets.keys():
            try:
                _ = self.results.get_answers(question_name)
            except KeyError:
                raise KeyError(
                    f"Question '{question_name}' not found in results. "
                    f"Available questions: {self.results.question_names}"
                )

            strategy_name = strategies.get(question_name, "categorical_kl")
            if strategy_name not in self._strategies:
                raise ValueError(
                    f"Unknown strategy '{strategy_name}' for question '{question_name}'. "
                    f"Available strategies: {self.list_strategies()}"
                )

        # Pre-fetch all responses and strategies to avoid repeated lookups
        question_data = {}
        for question_name, target_dist in targets.items():
            responses = self.results.get_answers(question_name)
            strategy_name = strategies.get(question_name, "categorical_kl")
            strategy_obj = self._strategies[strategy_name]

            # Validate inputs for this strategy
            strategy_obj.validate_inputs(responses, target_dist)

            question_data[question_name] = {
                "responses": responses,
                "target": target_dist,
                "strategy": strategy_obj,
                "weight": metric_weights.get(question_name, 1.0),
            }

        n = len(self.results)

        # Define aggregation functions
        def aggregate_weighted_sum(metrics: List[Tuple[float, float]]) -> float:
            """Weighted sum: Σᵢ αᵢ * metric_i"""
            return sum(weight * metric for weight, metric in metrics)

        def aggregate_max(metrics: List[Tuple[float, float]]) -> float:
            """Max: max(α₁*metric₁, α₂*metric₂, ...)"""
            return max(weight * metric for weight, metric in metrics)

        def aggregate_weighted_product(metrics: List[Tuple[float, float]]) -> float:
            """Weighted product: Πᵢ metric_i^αᵢ"""
            product = 1.0
            for weight, metric in metrics:
                if metric > 0:
                    product *= metric**weight
            return product

        # Select aggregation function
        aggregation_funcs = {
            "weighted_sum": aggregate_weighted_sum,
            "max": aggregate_max,
            "weighted_product": aggregate_weighted_product,
        }

        if aggregation not in aggregation_funcs:
            raise ValueError(
                f"Unknown aggregation '{aggregation}'. "
                f"Available: {list(aggregation_funcs.keys())}"
            )

        aggregate_func = aggregation_funcs[aggregation]

        # Objective function
        def objective(log_weights):
            np = _get_numpy()
            weights = np.exp(log_weights)
            weights = weights / weights.sum()

            # Compute metric for each question
            metrics = []
            for question_name, data in question_data.items():
                # Get weighted distribution
                weighted_dist = data["strategy"].get_weighted_distribution(
                    data["responses"], weights
                )

                # Compute metric
                metric = data["strategy"].compute_metric(weighted_dist, data["target"])

                metrics.append((data["weight"], metric))

            # Aggregate metrics
            return aggregate_func(metrics)

        # Initialize with uniform weights
        np = _get_numpy()
        log_w0 = np.zeros(n)

        # Optimize
        result = minimize(objective, log_w0, method="L-BFGS-B")

        # Extract and normalize weights
        weights = _get_numpy().exp(result.x)
        return weights / weights.sum()
