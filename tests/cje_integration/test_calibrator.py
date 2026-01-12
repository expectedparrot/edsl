"""Tests for CJE integration with EDSL.

These tests verify that:
1. Data adapters correctly convert EDSL Results to CJE format
2. CalibrationResult provides expected interfaces
3. End-to-end calibration works with synthetic data
"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np


class TestDataAdapters:
    """Tests for data_adapters module."""

    def test_results_to_fresh_draws_basic(self):
        """Test basic conversion of EDSL Results to fresh_draws format."""
        from edsl.cje_integration.data_adapters import results_to_fresh_draws

        # Create mock results
        mock_results = []
        for i in range(10):
            result = MagicMock()
            result.model = MagicMock()
            result.model.model = "gpt-4o" if i < 5 else "claude-3-5-sonnet"
            result.__getitem__ = lambda self, key, i=i: {
                "answer": {"sentiment": 0.1 * i}
            }.get(key, {})
            result.scenario = MagicMock()
            result.scenario.to_dict = lambda i=i: {"id": i}
            mock_results.append(result)

        # Convert
        fresh_draws = results_to_fresh_draws(
            mock_results,
            question_name="sentiment",
            policy_column="model",
        )

        # Verify structure
        assert "gpt-4o" in fresh_draws
        assert "claude-3-5-sonnet" in fresh_draws
        assert len(fresh_draws["gpt-4o"]) == 5
        assert len(fresh_draws["claude-3-5-sonnet"]) == 5

        # Verify record structure
        record = fresh_draws["gpt-4o"][0]
        assert "prompt_id" in record
        assert "judge_score" in record
        assert isinstance(record["judge_score"], float)

    def test_results_to_fresh_draws_with_oracle(self):
        """Test conversion with oracle labels."""
        from edsl.cje_integration.data_adapters import results_to_fresh_draws

        # Create mock result with oracle
        result = MagicMock()
        result.model = MagicMock()
        result.model.model = "gpt-4o"
        result.__getitem__ = lambda self, key: {
            "answer": {"sentiment": 0.7}
        }.get(key, {})
        result.scenario = MagicMock()
        result.scenario.to_dict = lambda: {"id": 1}

        # Pass oracle labels as a list
        oracle_labels = [0.8]

        fresh_draws = results_to_fresh_draws(
            [result],
            question_name="sentiment",
            oracle_labels=oracle_labels,
        )

        record = fresh_draws["gpt-4o"][0]
        assert "oracle_label" in record
        assert record["oracle_label"] == 0.8

    def test_score_transform(self):
        """Test score transformation (e.g., 1-5 scale to 0-1)."""
        from edsl.cje_integration.data_adapters import results_to_fresh_draws

        result = MagicMock()
        result.model = MagicMock()
        result.model.model = "gpt-4o"
        result.__getitem__ = lambda self, key: {
            "answer": {"rating": 5}  # 1-5 scale
        }.get(key, {})
        result.scenario = MagicMock()
        result.scenario.to_dict = lambda: {"id": 1}

        # Transform 1-5 to 0-1
        transform = lambda x: (x - 1) / 4

        fresh_draws = results_to_fresh_draws(
            [result],
            question_name="rating",
            score_transform=transform,
        )

        record = fresh_draws["gpt-4o"][0]
        assert record["judge_score"] == 1.0  # (5-1)/4 = 1.0

    def test_get_oracle_coverage(self):
        """Test oracle coverage calculation."""
        from edsl.cje_integration.data_adapters import get_oracle_coverage

        fresh_draws = {
            "policy_a": [
                {"prompt_id": "1", "judge_score": 0.5, "oracle_label": 0.6},
                {"prompt_id": "2", "judge_score": 0.7},  # No oracle
            ],
            "policy_b": [
                {"prompt_id": "3", "judge_score": 0.8, "oracle_label": 0.9},
            ],
        }

        coverage = get_oracle_coverage(fresh_draws)
        assert coverage["policy_a"] == 0.5  # 1/2
        assert coverage["policy_b"] == 1.0  # 1/1


class TestResultTypes:
    """Tests for result_types module."""

    def test_calibration_result_best_policy(self):
        """Test best_policy method."""
        from edsl.cje_integration.result_types import CalibrationResult

        result = CalibrationResult(
            estimates={"gpt-4o": 0.72, "claude": 0.68},
            standard_errors={"gpt-4o": 0.02, "claude": 0.03},
            confidence_intervals={"gpt-4o": (0.68, 0.76), "claude": (0.62, 0.74)},
            n_oracle=100,
            n_total=1000,
            calibration_rmse=0.05,
            overall_status="GOOD",
            _cje_result=MagicMock(),
        )

        assert result.best_policy() == "gpt-4o"

    def test_calibration_result_ranking(self):
        """Test ranking method."""
        from edsl.cje_integration.result_types import CalibrationResult

        result = CalibrationResult(
            estimates={"a": 0.5, "b": 0.9, "c": 0.7},
            standard_errors={"a": 0.01, "b": 0.01, "c": 0.01},
            confidence_intervals={"a": (0.48, 0.52), "b": (0.88, 0.92), "c": (0.68, 0.72)},
            n_oracle=50,
            n_total=500,
            calibration_rmse=0.03,
            overall_status="GOOD",
            _cje_result=MagicMock(),
        )

        assert result.ranking() == ["b", "c", "a"]

    def test_comparison_result(self):
        """Test ComparisonResult dataclass."""
        from edsl.cje_integration.result_types import ComparisonResult

        comparison = ComparisonResult(
            policy_a="gpt-4o",
            policy_b="claude",
            difference=0.04,
            se_difference=0.02,
            z_score=2.0,
            p_value=0.046,
            significant=True,
        )

        assert comparison.significant
        assert "significant" in repr(comparison)


class TestResultsCalibrateMethod:
    """Tests for Results.calibrate() method."""

    def test_results_calibrate_method_exists(self):
        """Test that Results class has calibrate method."""
        from edsl.results import Results

        assert hasattr(Results, "calibrate")
        # Check it's a method
        assert callable(getattr(Results, "calibrate", None))

    def test_results_calibrate_import_error(self):
        """Test that Results.calibrate raises ImportError if cje not installed."""
        from edsl.results import Results
        from unittest.mock import MagicMock, patch

        # Create a mock Results object
        mock_results = MagicMock(spec=Results)
        mock_results.__iter__ = lambda self: iter([])

        # Use the actual calibrate method from Results
        calibrate_method = Results.calibrate

        # Patch cje import to fail
        with patch.dict("sys.modules", {"cje": None}):
            with pytest.raises(ImportError, match="cje-eval is required"):
                # Call the unbound method with mock_results as self
                calibrate_method(
                    mock_results,
                    question_name="q",
                    oracle_labels=[0.5],
                )


class TestCJECalibrator:
    """Tests for CJECalibrator class."""

    def test_import_error_without_cje(self):
        """Test that calibrate raises ImportError if cje not installed."""
        from edsl.cje_integration.calibrator import CJECalibrator

        calibrator = CJECalibrator()

        # Mock results
        mock_results = [MagicMock()]
        mock_results[0].model = MagicMock()
        mock_results[0].model.model = "gpt-4o"
        mock_results[0].__getitem__ = lambda self, key: {"answer": {"q": 0.5}}.get(key, {})
        mock_results[0].scenario = MagicMock()
        mock_results[0].scenario.to_dict = lambda: {"id": 1}

        # Patch cje import to fail
        with patch.dict("sys.modules", {"cje": None}):
            with pytest.raises(ImportError, match="cje-eval is required"):
                calibrator.calibrate(
                    mock_results,
                    question_name="q",
                    oracle_labels=[0.6],
                )

    def test_no_oracle_labels_error(self):
        """Test that calibrate raises ValueError if no oracle labels."""
        from edsl.cje_integration.calibrator import CJECalibrator

        calibrator = CJECalibrator()

        # Mock results without oracle labels
        mock_results = [MagicMock()]
        mock_results[0].model = MagicMock()
        mock_results[0].model.model = "gpt-4o"
        mock_results[0].__getitem__ = lambda self, key: {"answer": {"q": 0.5}}.get(key, {})
        mock_results[0].scenario = MagicMock()
        mock_results[0].scenario.to_dict = lambda: {"id": 1}

        # Pass all None oracle labels
        with pytest.raises(ValueError, match="No oracle labels found"):
            calibrator.calibrate(
                mock_results,
                question_name="q",
                oracle_labels=[None],  # No valid oracle labels
            )


def _cje_available():
    """Check if CJE is installed."""
    try:
        import cje
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _cje_available(),
    reason="Requires cje-eval to be installed"
)
class TestEndToEnd:
    """End-to-end tests with actual CJE (requires cje-eval installed)."""

    def test_full_calibration_workflow(self):
        """Test full calibration workflow with synthetic data."""
        from edsl.cje_integration import calibrate

        # Create synthetic results
        np.random.seed(42)
        mock_results = []
        oracle_labels = []

        for i in range(100):
            result = MagicMock()
            result.model = MagicMock()
            result.model.model = "gpt-4o" if i < 50 else "claude-3-5-sonnet"

            # Synthetic judge score with some noise
            true_quality = 0.7 if i < 50 else 0.65
            judge_score = true_quality + np.random.normal(0, 0.1)
            judge_score = np.clip(judge_score, 0, 1)

            result.__getitem__ = lambda self, key, score=judge_score: {
                "answer": {"sentiment": score}
            }.get(key, {})
            result.scenario = MagicMock()
            result.scenario.to_dict = lambda i=i: {"id": i}

            # Add oracle for 10% of samples
            if np.random.random() < 0.1:
                oracle_label = true_quality + np.random.normal(0, 0.05)
                oracle_label = np.clip(oracle_label, 0, 1)
                oracle_labels.append(oracle_label)
            else:
                oracle_labels.append(None)

            mock_results.append(result)

        # Calibrate
        cal_result = calibrate(
            mock_results,
            question_name="sentiment",
            oracle_labels=oracle_labels,
        )

        # Verify structure
        assert "gpt-4o" in cal_result.estimates
        assert "claude-3-5-sonnet" in cal_result.estimates
        assert cal_result.n_oracle > 0
        assert cal_result.n_total == 100

        # Verify estimates are reasonable
        assert 0 < cal_result.estimates["gpt-4o"] < 1
        assert 0 < cal_result.estimates["claude-3-5-sonnet"] < 1

        # Test compare() method
        comparison = cal_result.compare("gpt-4o", "claude-3-5-sonnet")
        assert comparison.policy_a == "gpt-4o"
        assert comparison.policy_b == "claude-3-5-sonnet"
        assert isinstance(comparison.difference, float)
        assert isinstance(comparison.p_value, float)
        assert 0 <= comparison.p_value <= 1

    def test_oracle_labels_shorter_than_results(self):
        """Test that shorter oracle_labels list is handled correctly."""
        from edsl.cje_integration import calibrate

        np.random.seed(42)
        mock_results = []

        for i in range(40):
            result = MagicMock()
            result.model = MagicMock()
            result.model.model = "gpt-4o"
            result.__getitem__ = lambda self, key: {"answer": {"q": 0.5}}.get(key, {})
            result.scenario = MagicMock()
            result.scenario.to_dict = lambda i=i: {"id": i}
            mock_results.append(result)

        # Only 15 oracle labels for 40 results - CJE needs >= 10 for CV
        oracle_labels = [0.4 + 0.02 * i for i in range(15)]

        cal_result = calibrate(
            mock_results,
            question_name="q",
            oracle_labels=oracle_labels,
        )

        assert cal_result.n_oracle == 15
        assert cal_result.n_total == 40

    def test_oracle_labels_with_mixed_none(self):
        """Test sparse oracle labels with None values interspersed."""
        from edsl.cje_integration import calibrate

        np.random.seed(42)
        mock_results = []

        for i in range(50):
            result = MagicMock()
            result.model = MagicMock()
            result.model.model = "policy_a" if i < 25 else "policy_b"
            score = 0.6 if i < 25 else 0.4
            result.__getitem__ = lambda self, key, s=score: {"answer": {"q": s}}.get(key, {})
            result.scenario = MagicMock()
            result.scenario.to_dict = lambda i=i: {"id": i}
            mock_results.append(result)

        # Sparse labels: only every 4th sample has a label (gives 13 labels)
        # Keep values in [0, 1] range
        oracle_labels = [0.3 + 0.01 * i if i % 4 == 0 else None for i in range(50)]

        cal_result = calibrate(
            mock_results,
            question_name="q",
            oracle_labels=oracle_labels,
        )

        # Should have 13 oracle labels (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48)
        assert cal_result.n_oracle == 13
        assert cal_result.n_total == 50
