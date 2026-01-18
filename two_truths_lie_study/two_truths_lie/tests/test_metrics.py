"""Tests for metrics calculation."""

import pytest
import tempfile
import shutil

from src.metrics import MetricsCalculator, ConditionMetrics, CalibrationMetrics
from src.storage import ResultStore
from tests.fixtures import create_mock_round


class TestMetricsCalculator:
    """Test suite for MetricsCalculator."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary result store."""
        temp_dir = tempfile.mkdtemp()
        store = ResultStore(base_dir=temp_dir)
        yield store
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def calculator(self, temp_store):
        """Create metrics calculator."""
        return MetricsCalculator(temp_store)

    def test_empty_metrics(self, calculator):
        """Test metrics with no rounds."""
        metrics = calculator.calculate_all_metrics()

        assert metrics.total_rounds == 0
        assert metrics.overall_judge_accuracy == 0.0
        assert metrics.overall_fibber_success == 0.0
        assert len(metrics.by_condition) == 0
        assert len(metrics.by_strategy) == 0

    def test_basic_accuracy_calculation(self, temp_store, calculator):
        """Test basic accuracy calculation."""
        # Add 7 correct, 3 incorrect rounds
        for i in range(7):
            temp_store.save_round(create_mock_round(detection_correct=True))

        for i in range(3):
            temp_store.save_round(create_mock_round(detection_correct=False))

        metrics = calculator.calculate_all_metrics()

        assert metrics.total_rounds == 10
        assert metrics.overall_judge_accuracy == pytest.approx(0.7)
        assert metrics.overall_fibber_success == pytest.approx(0.3)

    def test_false_accusation_rate(self, temp_store, calculator):
        """Test false accusation rate calculation."""
        # 6 correct, 4 false accusations
        for i in range(6):
            temp_store.save_round(create_mock_round(detection_correct=True))

        for i in range(4):
            temp_store.save_round(create_mock_round(detection_correct=False))

        metrics = calculator.calculate_all_metrics()

        # All incorrect detections are false accusations
        assert metrics.overall_false_accusation == pytest.approx(0.4)

    def test_by_strategy_breakdown(self, temp_store, calculator):
        """Test metrics broken down by strategy."""
        # Baseline: 80% accuracy (4/5)
        for i in range(4):
            temp_store.save_round(create_mock_round(
                strategy="baseline",
                detection_correct=True
            ))
        temp_store.save_round(create_mock_round(
            strategy="baseline",
            detection_correct=False
        ))

        # level_k_0: 60% accuracy (3/5)
        for i in range(3):
            temp_store.save_round(create_mock_round(
                strategy="level_k_0",
                detection_correct=True
            ))
        for i in range(2):
            temp_store.save_round(create_mock_round(
                strategy="level_k_0",
                detection_correct=False
            ))

        metrics = calculator.calculate_all_metrics()

        assert metrics.by_strategy["baseline"] == pytest.approx(0.8)
        assert metrics.by_strategy["level_k_0"] == pytest.approx(0.6)

    def test_by_category_breakdown(self, temp_store, calculator):
        """Test metrics broken down by category."""
        # Science: 70% accuracy (7/10)
        for i in range(7):
            temp_store.save_round(create_mock_round(
                category="science",
                detection_correct=True
            ))
        for i in range(3):
            temp_store.save_round(create_mock_round(
                category="science",
                detection_correct=False
            ))

        # History: 50% accuracy (5/10)
        for i in range(5):
            temp_store.save_round(create_mock_round(
                category="history",
                detection_correct=True
            ))
        for i in range(5):
            temp_store.save_round(create_mock_round(
                category="history",
                detection_correct=False
            ))

        metrics = calculator.calculate_all_metrics()

        assert metrics.by_category["science"] == pytest.approx(0.7)
        assert metrics.by_category["history"] == pytest.approx(0.5)

    def test_by_condition_breakdown(self, temp_store, calculator):
        """Test metrics broken down by full condition."""
        # Condition 1: baseline + science + curious
        for i in range(5):
            temp_store.save_round(create_mock_round(
                strategy="baseline",
                category="science",
                question_style="curious",
                detection_correct=True
            ))

        # Condition 2: level_k_0 + history + curious
        for i in range(3):
            temp_store.save_round(create_mock_round(
                strategy="level_k_0",
                category="history",
                question_style="curious",
                detection_correct=True
            ))
        for i in range(2):
            temp_store.save_round(create_mock_round(
                strategy="level_k_0",
                category="history",
                question_style="curious",
                detection_correct=False
            ))

        metrics = calculator.calculate_all_metrics()

        assert len(metrics.by_condition) == 2

        # Find baseline_science_curious condition
        baseline_condition = None
        level_k_condition = None

        for c in metrics.by_condition:
            if c.strategy == "baseline" and c.category == "science":
                baseline_condition = c
            elif c.strategy == "level_k_0" and c.category == "history":
                level_k_condition = c

        # Debug: print conditions if not found
        if baseline_condition is None or level_k_condition is None:
            print("\nActual conditions found:")
            for c in metrics.by_condition:
                print(f"  {c.condition_id}: {c.strategy} / {c.category} / {c.question_style}")

        assert baseline_condition is not None, "baseline_science_curious condition not found"
        assert level_k_condition is not None, "level_k_0_history_curious condition not found"

        assert baseline_condition.total_rounds == 5
        assert baseline_condition.judge_accuracy == pytest.approx(1.0)

        assert level_k_condition.total_rounds == 5
        assert level_k_condition.judge_accuracy == pytest.approx(0.6)

    def test_confidence_metrics(self, temp_store, calculator):
        """Test average confidence calculations."""
        # High confidence correct (8-10)
        for i in range(3):
            temp_store.save_round(create_mock_round(
                confidence=9,
                detection_correct=True
            ))

        # Low confidence incorrect (3-5)
        for i in range(2):
            temp_store.save_round(create_mock_round(
                confidence=4,
                detection_correct=False
            ))

        metrics = calculator.calculate_all_metrics()

        # Overall average: (9*3 + 4*2) / 5 = 35/5 = 7
        assert metrics.by_condition[0].avg_confidence == pytest.approx(7.0)

        # Confidence when correct: 9
        assert metrics.by_condition[0].avg_confidence_when_correct == pytest.approx(9.0)

        # Confidence when wrong: 4
        assert metrics.by_condition[0].avg_confidence_when_wrong == pytest.approx(4.0)

    def test_calibration_buckets(self, temp_store, calculator):
        """Test confidence calibration bucketing."""
        # Low confidence (1-3): 1 round, 0% accuracy
        temp_store.save_round(create_mock_round(
            confidence=2,
            detection_correct=False
        ))

        # Medium confidence (4-6): 2 rounds, 50% accuracy
        temp_store.save_round(create_mock_round(
            confidence=5,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=5,
            detection_correct=False
        ))

        # High confidence (7-8): 4 rounds, 75% accuracy
        temp_store.save_round(create_mock_round(
            confidence=7,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=7,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=8,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=8,
            detection_correct=False
        ))

        # Very high confidence (9-10): 3 rounds, 100% accuracy
        temp_store.save_round(create_mock_round(
            confidence=10,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=9,
            detection_correct=True
        ))
        temp_store.save_round(create_mock_round(
            confidence=9,
            detection_correct=True
        ))

        metrics = calculator.calculate_all_metrics()

        # Check that we have all buckets
        buckets = {b.confidence_range: b for b in metrics.calibration.buckets}

        assert len(buckets) == 4

        # Low confidence bucket
        assert buckets["1-3 (Low)"].num_predictions == 1
        assert buckets["1-3 (Low)"].accuracy == pytest.approx(0.0)

        # Medium confidence bucket
        assert buckets["4-6 (Medium)"].num_predictions == 2
        assert buckets["4-6 (Medium)"].accuracy == pytest.approx(0.5)

        # High confidence bucket
        assert buckets["7-8 (High)"].num_predictions == 4
        assert buckets["7-8 (High)"].accuracy == pytest.approx(0.75)

        # Very high confidence bucket
        assert buckets["9-10 (Very High)"].num_predictions == 3
        assert buckets["9-10 (Very High)"].accuracy == pytest.approx(1.0)

    def test_calibration_error(self, temp_store, calculator):
        """Test calibration error calculation."""
        # Perfectly calibrated: confidence = accuracy
        # Confidence 5/10 (0.5), accuracy 50%
        temp_store.save_round(create_mock_round(confidence=5, detection_correct=True))
        temp_store.save_round(create_mock_round(confidence=5, detection_correct=False))

        # Confidence 8/10 (0.8), accuracy 80%
        for i in range(4):
            temp_store.save_round(create_mock_round(confidence=8, detection_correct=True))
        temp_store.save_round(create_mock_round(confidence=8, detection_correct=False))

        metrics = calculator.calculate_all_metrics()

        # With perfect calibration, error should be close to 0
        assert metrics.calibration.calibration_error < 0.1

    def test_brier_score(self, temp_store, calculator):
        """Test Brier score calculation."""
        # Perfect predictions: 10 -> correct, 1 -> incorrect
        temp_store.save_round(create_mock_round(confidence=10, detection_correct=True))
        temp_store.save_round(create_mock_round(confidence=1, detection_correct=False))

        metrics = calculator.calculate_all_metrics()

        # Brier score = mean((predicted - actual)^2)
        # Round 1: (1.0 - 1.0)^2 = 0
        # Round 2: (0.1 - 0.0)^2 = 0.01
        # Average: 0.005
        assert metrics.calibration.brier_score == pytest.approx(0.005)

    def test_calculate_condition_metrics(self, temp_store, calculator):
        """Test calculating metrics for a specific condition."""
        # Add rounds for specific condition
        for i in range(8):
            temp_store.save_round(create_mock_round(
                strategy="baseline",
                category="science",
                question_style="curious",
                detection_correct=True
            ))
        for i in range(2):
            temp_store.save_round(create_mock_round(
                strategy="baseline",
                category="science",
                question_style="curious",
                detection_correct=False
            ))

        # Calculate metrics for this condition (using pipe delimiter)
        condition_metrics = calculator.calculate_condition_metrics("baseline|science|curious")

        assert condition_metrics is not None
        assert condition_metrics.total_rounds == 10
        assert condition_metrics.judge_accuracy == pytest.approx(0.8)
        assert condition_metrics.strategy == "baseline"
        assert condition_metrics.category == "science"
        assert condition_metrics.question_style == "curious"

    def test_calculate_condition_metrics_not_found(self, temp_store, calculator):
        """Test condition metrics for non-existent condition."""
        result = calculator.calculate_condition_metrics("nonexistent|condition|id")
        assert result is None
