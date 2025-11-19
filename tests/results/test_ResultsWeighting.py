import unittest
import numpy as np
from edsl.results import Results
from edsl.results.results_weighting import ResultsWeighting


class TestResultsWeighting(unittest.TestCase):
    """Test suite for ResultsWeighting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.results = Results.example()
        self.weighter = ResultsWeighting(self.results)

    def test_weighter_initialization(self):
        """Test that ResultsWeighting can be initialized."""
        self.assertIsInstance(self.weighter, ResultsWeighting)
        self.assertEqual(self.weighter.results, self.results)

    def test_find_optimal_weights_basic(self):
        """Test basic weight finding with optimization method."""
        # Define a target distribution
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Find optimal weights
        weights = self.weighter.find_optimal_weights("how_feeling", target_dist)

        # Check that weights have correct length
        self.assertEqual(len(weights), len(self.results))

        # Check that weights are normalized
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)

        # Check that all weights are non-negative
        self.assertTrue(np.all(weights >= 0))

    def test_find_optimal_weights_iterative(self):
        """Test weight finding with iterative method."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Find optimal weights using iterative method
        weights = self.weighter.find_optimal_weights(
            "how_feeling", target_dist, method="iterative"
        )

        # Check basic properties
        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        self.assertTrue(np.all(weights >= 0))

    def test_find_optimal_weights_via_results_method(self):
        """Test the convenience method on Results object."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Use the Results method directly
        weights = self.results.find_weights_for_target_distribution(
            "how_feeling", target_dist
        )

        # Check basic properties
        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        self.assertTrue(np.all(weights >= 0))

    def test_get_weighted_distribution(self):
        """Test computing weighted distribution from weights."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Get optimal weights
        weights = self.weighter.find_optimal_weights("how_feeling", target_dist)

        # Get weighted distribution
        weighted_dist = self.weighter.get_weighted_distribution("how_feeling", weights)

        # Check that it's a dictionary
        self.assertIsInstance(weighted_dist, dict)

        # Check that probabilities sum to 1.0
        self.assertAlmostEqual(sum(weighted_dist.values()), 1.0, places=6)

        # Check that the weighted distribution is close to target
        for category in target_dist:
            self.assertIn(category, weighted_dist)
            # Allow some tolerance since optimization may not be perfect
            self.assertAlmostEqual(
                weighted_dist[category], target_dist[category], places=1
            )

    def test_compute_kl_divergence(self):
        """Test KL divergence computation."""
        p = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
        q = {"Great": 0.4, "OK": 0.4, "Terrible": 0.2}

        kl = self.weighter.compute_kl_divergence(p, q)

        # KL divergence should be non-negative
        self.assertGreaterEqual(kl, 0)

        # KL divergence with itself should be 0
        kl_self = self.weighter.compute_kl_divergence(p, p)
        self.assertAlmostEqual(kl_self, 0.0, places=6)

    def test_invalid_target_distribution_sum(self):
        """Test that invalid target distribution raises ValueError."""
        # Target distribution that doesn't sum to 1.0
        invalid_target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.3}

        with self.assertRaises(ValueError) as context:
            self.weighter.find_optimal_weights("how_feeling", invalid_target)

        self.assertIn("must sum to 1.0", str(context.exception))

    def test_invalid_question_name(self):
        """Test that invalid question name raises error."""
        target_dist = {"yes": 0.6, "no": 0.4}

        # Note: get_answers returns None for non-existent questions,
        # which triggers a ValueError about missing categories in target_dist
        with self.assertRaises((KeyError, ValueError)):
            self.weighter.find_optimal_weights("nonexistent_question", target_dist)

    def test_missing_category_in_target(self):
        """Test that missing category in target raises ValueError."""
        # Target distribution missing the 'Terrible' category
        incomplete_target = {"Great": 0.7, "OK": 0.3}

        with self.assertRaises(ValueError) as context:
            self.weighter.find_optimal_weights("how_feeling", incomplete_target)

        self.assertIn("not present in target distribution", str(context.exception))

    def test_invalid_method(self):
        """Test that invalid method raises ValueError."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        with self.assertRaises(ValueError) as context:
            self.weighter.find_optimal_weights(
                "how_feeling", target_dist, method="invalid_method"
            )

        self.assertIn("Unknown method", str(context.exception))

    def test_weights_reduce_kl_divergence(self):
        """Test that optimal weights actually reduce KL divergence."""
        # Get current distribution
        responses = self.results.get_answers("how_feeling")
        current_counts = {}
        for resp in responses:
            current_counts[resp] = current_counts.get(resp, 0) + 1
        total = sum(current_counts.values())
        current_dist = {k: v / total for k, v in current_counts.items()}

        # Define target distribution
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Compute KL divergence before weighting
        kl_before = self.weighter.compute_kl_divergence(current_dist, target_dist)

        # Get optimal weights
        weights = self.weighter.find_optimal_weights("how_feeling", target_dist)

        # Compute weighted distribution
        weighted_dist = self.weighter.get_weighted_distribution("how_feeling", weights)

        # Compute KL divergence after weighting
        kl_after = self.weighter.compute_kl_divergence(weighted_dist, target_dist)

        # KL divergence should be reduced (or at least not worse)
        self.assertLessEqual(kl_after, kl_before)

    def test_uniform_weights_for_matching_distribution(self):
        """Test that uniform-ish weights result when target matches empirical."""
        # Get current distribution
        responses = self.results.get_answers("how_feeling")
        current_counts = {}
        for resp in responses:
            current_counts[resp] = current_counts.get(resp, 0) + 1
        total = sum(current_counts.values())
        current_dist = {k: v / total for k, v in current_counts.items()}

        # Use current distribution as target
        weights = self.weighter.find_optimal_weights("how_feeling", current_dist)

        # Weights should be relatively uniform (close to 1/n)
        expected_weight = 1.0 / len(self.results)
        # Allow some tolerance
        max_deviation = np.max(np.abs(weights - expected_weight))
        self.assertLess(max_deviation, 0.5)  # Generous tolerance


    def test_strategy_parameter(self):
        """Test using the new strategy parameter."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Test with explicit strategy parameter
        weights_kl = self.weighter.find_optimal_weights(
            "how_feeling", target_dist, strategy="categorical_kl"
        )
        weights_ipf = self.weighter.find_optimal_weights(
            "how_feeling", target_dist, strategy="categorical_ipf"
        )

        # Both should return valid weights
        self.assertEqual(len(weights_kl), len(self.results))
        self.assertEqual(len(weights_ipf), len(self.results))
        self.assertAlmostEqual(weights_kl.sum(), 1.0, places=6)
        self.assertAlmostEqual(weights_ipf.sum(), 1.0, places=6)

    def test_list_strategies(self):
        """Test listing available strategies."""
        strategies = self.weighter.list_strategies()

        self.assertIsInstance(strategies, list)
        self.assertIn("categorical_kl", strategies)
        self.assertIn("categorical_ipf", strategies)
        self.assertIn("continuous_binned", strategies)

    def test_invalid_strategy(self):
        """Test that invalid strategy raises ValueError."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        with self.assertRaises(ValueError) as context:
            self.weighter.find_optimal_weights(
                "how_feeling", target_dist, strategy="nonexistent_strategy"
            )

        self.assertIn("Unknown strategy", str(context.exception))

    def test_backward_compatibility_with_method_param(self):
        """Test that old 'method' parameter still works (with deprecation warning)."""
        target_dist = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}

        # Should work but emit a deprecation warning
        with self.assertWarns(DeprecationWarning):
            weights = self.weighter.find_optimal_weights(
                "how_feeling", target_dist, method="optimization"
            )

        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)

        # Test iterative method mapping
        with self.assertWarns(DeprecationWarning):
            weights_iterative = self.weighter.find_optimal_weights(
                "how_feeling", target_dist, method="iterative"
            )

        self.assertEqual(len(weights_iterative), len(self.results))

    def test_multi_target_basic(self):
        """Test basic multi-target weighting with two questions."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
        }

        weights = self.weighter.find_weights_for_multiple_targets(targets)

        # Check basic properties
        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)
        self.assertTrue(np.all(weights >= 0))

    def test_multi_target_with_metric_weights(self):
        """Test multi-target with custom metric weights."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
        }

        # Make first question 2x more important
        metric_weights = {'how_feeling': 2.0, 'how_feeling_yesterday': 1.0}

        weights = self.weighter.find_weights_for_multiple_targets(
            targets, metric_weights=metric_weights
        )

        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)

    def test_multi_target_aggregation_methods(self):
        """Test different aggregation methods."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
        }

        # Test weighted_sum (default)
        weights_sum = self.weighter.find_weights_for_multiple_targets(
            targets, aggregation='weighted_sum'
        )

        # Test max aggregation
        weights_max = self.weighter.find_weights_for_multiple_targets(
            targets, aggregation='max'
        )

        # Test weighted_product
        weights_prod = self.weighter.find_weights_for_multiple_targets(
            targets, aggregation='weighted_product'
        )

        # All should return valid weights
        for weights in [weights_sum, weights_max, weights_prod]:
            self.assertEqual(len(weights), len(self.results))
            self.assertAlmostEqual(weights.sum(), 1.0, places=6)

        # Results should differ between methods
        self.assertFalse(np.allclose(weights_sum, weights_max))

    def test_multi_target_via_results_method(self):
        """Test the convenience method on Results object."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
        }

        weights = self.results.find_weights_for_multiple_targets(targets)

        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)

    def test_multi_target_empty_targets(self):
        """Test that empty targets raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.weighter.find_weights_for_multiple_targets({})

        self.assertIn("cannot be empty", str(context.exception))

    def test_multi_target_invalid_aggregation(self):
        """Test that invalid aggregation method raises ValueError."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}
        }

        with self.assertRaises(ValueError) as context:
            self.weighter.find_weights_for_multiple_targets(
                targets, aggregation='invalid_method'
            )

        self.assertIn("Unknown aggregation", str(context.exception))

    def test_multi_target_invalid_question(self):
        """Test that invalid question name raises error."""
        targets = {
            'nonexistent_question': {'yes': 0.6, 'no': 0.4}
        }

        # Note: get_answers returns None for non-existent questions,
        # which triggers a ValueError about missing categories in target_dist
        with self.assertRaises((KeyError, ValueError)):
            self.weighter.find_weights_for_multiple_targets(targets)

    def test_multi_target_metric_weight_normalization(self):
        """Test that metric weights are automatically normalized."""
        targets = {
            'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
            'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
        }

        # Provide unnormalized weights
        metric_weights = {'how_feeling': 4.0, 'how_feeling_yesterday': 2.0}

        # Should work (weights will be normalized internally)
        weights = self.weighter.find_weights_for_multiple_targets(
            targets, metric_weights=metric_weights
        )

        self.assertEqual(len(weights), len(self.results))
        self.assertAlmostEqual(weights.sum(), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
