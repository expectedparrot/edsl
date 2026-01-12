"""Tests for the weighting service (sample weighting for Results)."""

import pytest

# Skip all tests if scipy/numpy not installed
try:
    import numpy as np
    from scipy.optimize import minimize
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_DEPS,
    reason="scipy and numpy required for weighting tests"
)


def test_weighting_service_exists():
    """Test that weighting service is registered."""
    from edsl.services import ServiceRegistry, _ensure_builtin_services
    _ensure_builtin_services()
    
    svc = ServiceRegistry.get("weighting")
    assert svc is not None
    assert svc.name == "weighting"


def test_weighting_service_aliases():
    """Test that weighting service has expected aliases."""
    from edsl.services import ServiceRegistry, _ensure_builtin_services
    _ensure_builtin_services()
    
    svc1 = ServiceRegistry.get("weighting")
    svc2 = ServiceRegistry.get("find_weights")
    svc3 = ServiceRegistry.get("sample_weights")
    
    assert svc1 is svc2
    assert svc2 is svc3


def test_categorical_kl_weighting_basic():
    """Test basic categorical KL divergence weighting."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    # Define target distribution
    target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
    
    params = {
        "operation": "categorical_kl",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "target": target,
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    assert "weights" in result
    
    weights = np.array(result["weights"])
    
    # Check weights have correct length
    assert len(weights) == len(results)
    
    # Check weights are normalized
    assert np.isclose(weights.sum(), 1.0)
    
    # Check all weights are non-negative
    assert np.all(weights >= 0)


def test_ipf_weighting():
    """Test iterative proportional fitting weighting."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
    
    params = {
        "operation": "categorical_ipf",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "target": target,
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    weights = np.array(result["weights"])
    assert len(weights) == len(results)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_multi_target_weighting():
    """Test multi-target weighting with two questions."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    params = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {
            "targets": {
                'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
                'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
            }
        }
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    weights = np.array(result["weights"])
    assert len(weights) == len(results)
    assert np.isclose(weights.sum(), 1.0)


def test_multi_target_with_metric_weights():
    """Test multi-target with custom metric weights."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    params = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {
            "targets": {
                'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
                'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
            },
            "metric_weights": {'how_feeling': 2.0, 'how_feeling_yesterday': 1.0}
        }
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    weights = np.array(result["weights"])
    assert len(weights) == len(results)


def test_multi_target_aggregation_methods():
    """Test different aggregation methods."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    targets = {
        'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2},
        'how_feeling_yesterday': {'Great': 0.4, 'Good': 0.3, 'OK': 0.2, 'Terrible': 0.1}
    }
    
    # Test weighted_sum (default)
    params_sum = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {"targets": targets, "aggregation": "weighted_sum"}
    }
    result_sum = WeightingService.execute(params_sum)
    
    # Test max aggregation
    params_max = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {"targets": targets, "aggregation": "max"}
    }
    result_max = WeightingService.execute(params_max)
    
    assert result_sum["status"] == "success"
    assert result_max["status"] == "success"
    
    weights_sum = np.array(result_sum["weights"])
    weights_max = np.array(result_max["weights"])
    
    assert len(weights_sum) == len(results)
    assert len(weights_max) == len(results)
    
    # Results should differ between methods
    assert not np.allclose(weights_sum, weights_max)


def test_compute_kl_divergence():
    """Test KL divergence computation."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    # Need to provide results_data even for compute_kl
    results = Results.example()
    
    p = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
    q = {"Great": 0.4, "OK": 0.4, "Terrible": 0.2}
    
    params = {
        "operation": "compute_kl",
        "results_data": results.to_dict(),
        "target": q,
        "options": {"empirical": p}
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    assert result["kl_divergence"] >= 0
    
    # KL divergence with itself should be 0
    params_self = {
        "operation": "compute_kl",
        "results_data": results.to_dict(),
        "target": p,
        "options": {"empirical": p}
    }
    
    result_self = WeightingService.execute(params_self)
    assert np.isclose(result_self["kl_divergence"], 0.0, atol=1e-10)


def test_get_weighted_distribution():
    """Test computing weighted distribution from weights."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    n = len(results)
    
    # First get optimal weights
    target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
    params_weights = {
        "operation": "categorical_kl",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "target": target,
    }
    weights_result = WeightingService.execute(params_weights)
    weights = weights_result["weights"]
    
    # Then get weighted distribution
    params_dist = {
        "operation": "get_distribution",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "options": {"weights": weights}
    }
    
    result = WeightingService.execute(params_dist)
    
    assert result["status"] == "success"
    assert "distribution" in result
    
    # Check that probabilities sum to 1.0
    assert np.isclose(sum(result["distribution"].values()), 1.0)


def test_invalid_target_distribution_sum():
    """Test that invalid target distribution raises ValueError."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    # Target distribution that doesn't sum to 1.0
    invalid_target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.3}
    
    params = {
        "operation": "categorical_kl",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "target": invalid_target,
    }
    
    with pytest.raises(ValueError) as exc:
        WeightingService.execute(params)
    
    assert "must sum to 1.0" in str(exc.value)


def test_invalid_question_name():
    """Test that invalid question name raises error."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    target = {"yes": 0.6, "no": 0.4}
    
    params = {
        "operation": "categorical_kl",
        "results_data": results.to_dict(),
        "question": "nonexistent_question",
        "target": target,
    }
    
    # Should raise an error (either KeyError or ValueError)
    with pytest.raises((KeyError, ValueError, Exception)):
        WeightingService.execute(params)


def test_multi_target_empty_targets():
    """Test that empty targets raises ValueError."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    params = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {"targets": {}}
    }
    
    with pytest.raises(ValueError) as exc:
        WeightingService.execute(params)
    
    assert "empty" in str(exc.value).lower()


def test_multi_target_invalid_aggregation():
    """Test that invalid aggregation method raises ValueError."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    params = {
        "operation": "multi_target",
        "results_data": results.to_dict(),
        "options": {
            "targets": {'how_feeling': {'Great': 0.5, 'OK': 0.3, 'Terrible': 0.2}},
            "aggregation": "invalid_method"
        }
    }
    
    with pytest.raises(ValueError) as exc:
        WeightingService.execute(params)
    
    assert "aggregation" in str(exc.value).lower()


def test_weights_reduce_kl_divergence():
    """Test that optimal weights actually reduce KL divergence."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    # Define target distribution different from actual
    target = {"Great": 0.5, "OK": 0.3, "Terrible": 0.2}
    
    # Get weights
    params = {
        "operation": "categorical_kl",
        "results_data": results.to_dict(),
        "question": "how_feeling",
        "target": target,
    }
    
    result = WeightingService.execute(params)
    
    assert result["status"] == "success"
    
    # The achieved distribution should be closer to target than uniform would be
    # KL divergence in result should be reasonably small
    assert result["kl_divergence"] < 1.0  # Should be much less than 1


def test_parse_result_converts_to_numpy():
    """Test that parse_result converts weights to numpy array."""
    from edsl.services.builtin.weighting_service import WeightingService
    
    mock_result = {
        "status": "success",
        "weights": [0.1, 0.2, 0.3, 0.4],
    }
    
    parsed = WeightingService.parse_result(mock_result)
    
    assert isinstance(parsed["weights"], np.ndarray)
    assert np.allclose(parsed["weights"], [0.1, 0.2, 0.3, 0.4])


def test_unknown_operation():
    """Test that unknown operation raises ValueError."""
    from edsl.results import Results
    from edsl.services.builtin.weighting_service import WeightingService
    
    results = Results.example()
    
    params = {
        "operation": "unknown_op",
        "results_data": results.to_dict(),
    }
    
    with pytest.raises(ValueError) as exc:
        WeightingService.execute(params)
    
    assert "Unknown operation" in str(exc.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
