"""Metrics calculation for experiment analysis.

This module provides statistical analysis of experimental results:
- Judge accuracy and performance
- Fibber success rates
- Confidence calibration
- Condition-based breakdowns
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import defaultdict

from .models import Round
from .storage import ResultStore, RoundFilters


@dataclass
class ConditionMetrics:
    """Metrics for a specific experimental condition.

    Attributes:
        condition_id: Unique condition identifier
        strategy: Storyteller strategy used
        category: Fact category used
        question_style: Judge question style used
        total_rounds: Number of rounds in this condition
        judge_accuracy: Proportion of correct detections
        fibber_success_rate: Proportion where fibber evaded detection
        false_accusation_rate: Proportion of incorrect accusations
        avg_confidence: Average confidence (1-10)
        avg_confidence_when_correct: Avg confidence on correct guesses
        avg_confidence_when_wrong: Avg confidence on incorrect guesses
    """

    condition_id: str
    strategy: str
    category: str
    question_style: str
    total_rounds: int
    judge_accuracy: float
    fibber_success_rate: float
    false_accusation_rate: float
    avg_confidence: float
    avg_confidence_when_correct: float
    avg_confidence_when_wrong: float


@dataclass
class CalibrationBucket:
    """Confidence calibration bucket.

    Attributes:
        confidence_range: Range label (e.g., "7-8")
        num_predictions: Number of predictions in this bucket
        accuracy: Actual accuracy for this confidence range
        avg_confidence: Average confidence value
    """

    confidence_range: str
    num_predictions: int
    accuracy: float
    avg_confidence: float


@dataclass
class CalibrationMetrics:
    """Confidence calibration analysis.

    Attributes:
        buckets: List of calibration buckets
        calibration_error: Mean absolute calibration error
        brier_score: Brier score (lower is better)
    """

    buckets: List[CalibrationBucket]
    calibration_error: float
    brier_score: float


@dataclass
class NShotMetrics:
    """N-shot performance analysis (one-shot, two-shot, etc).

    Tracks how judge accuracy evolves with more information.

    Attributes:
        shot_number: Number of Q&A exchanges seen (1 = one-shot, 2 = two-shot, etc)
        total_guesses: Total number of intermediate guesses at this shot
        accuracy: Accuracy at this shot level
        avg_confidence: Average confidence at this shot level
    """

    shot_number: int
    total_guesses: int
    accuracy: float
    avg_confidence: float


@dataclass
class ExperimentMetrics:
    """Comprehensive metrics for an entire experiment.

    Attributes:
        total_rounds: Total number of rounds
        overall_judge_accuracy: Overall judge accuracy
        overall_fibber_success: Overall fibber success rate
        overall_false_accusation: Overall false accusation rate
        by_condition: Metrics broken down by condition
        by_strategy: Metrics broken down by strategy
        by_category: Metrics broken down by category
        by_question_style: Metrics broken down by question style
        by_temperature: Metrics broken down by judge temperature
        calibration: Confidence calibration metrics
        n_shot_performance: Performance at each Q&A level (one-shot, two-shot, etc)
    """

    total_rounds: int
    overall_judge_accuracy: float
    overall_fibber_success: float
    overall_false_accusation: float
    by_condition: List[ConditionMetrics]
    by_strategy: Dict[str, float]  # strategy -> accuracy
    by_category: Dict[str, float]  # category -> accuracy
    by_question_style: Dict[str, float]  # question_style -> accuracy
    by_temperature: Dict[float, float]  # temperature -> accuracy
    calibration: CalibrationMetrics
    n_shot_performance: List[NShotMetrics]


class MetricsCalculator:
    """Calculate and aggregate experimental metrics.

    This class provides comprehensive statistical analysis of experiment results,
    including accuracy, success rates, and confidence calibration.
    """

    def __init__(self, store: ResultStore):
        """Initialize metrics calculator.

        Args:
            store: Result store to query for rounds
        """
        self.store = store

    def calculate_all_metrics(self) -> ExperimentMetrics:
        """Calculate comprehensive metrics for all rounds.

        Returns:
            Complete metrics analysis
        """
        all_rounds = self._get_all_rounds()

        if not all_rounds:
            return self._empty_metrics()

        # Calculate overall metrics
        total_rounds = len(all_rounds)
        overall_accuracy = self._calculate_accuracy(all_rounds)
        overall_fibber_success = 1.0 - overall_accuracy
        overall_false_accusation = self._calculate_false_accusation_rate(all_rounds)

        # Calculate by-condition metrics
        by_condition = self._calculate_by_condition(all_rounds)

        # Calculate by-dimension metrics
        by_strategy = self._calculate_by_dimension(all_rounds, 'strategy')
        by_category = self._calculate_by_dimension(all_rounds, 'category')
        by_question_style = self._calculate_by_dimension(all_rounds, 'question_style')
        by_temperature = self._calculate_by_temperature(all_rounds)

        # Calculate calibration
        calibration = self._calculate_calibration(all_rounds)

        # Calculate n-shot performance
        n_shot_performance = self._calculate_n_shot_performance(all_rounds)

        return ExperimentMetrics(
            total_rounds=total_rounds,
            overall_judge_accuracy=overall_accuracy,
            overall_fibber_success=overall_fibber_success,
            overall_false_accusation=overall_false_accusation,
            by_condition=by_condition,
            by_strategy=by_strategy,
            by_category=by_category,
            by_question_style=by_question_style,
            by_temperature=by_temperature,
            calibration=calibration,
            n_shot_performance=n_shot_performance
        )

    def calculate_condition_metrics(self, condition_id: str) -> Optional[ConditionMetrics]:
        """Calculate metrics for a specific condition.

        Args:
            condition_id: Condition identifier (format: strategy|category|question_style)

        Returns:
            Metrics for the condition, or None if no rounds found
        """
        # Parse condition_id to get filters (using pipe delimiter)
        parts = condition_id.split('|')
        if len(parts) != 3:
            return None

        strategy, category, question_style = parts

        filters = RoundFilters(
            strategy=strategy,
            category=category,
            question_style=question_style
        )

        rounds = self.store.query_rounds(filters)

        if not rounds:
            return None

        return self._condition_metrics_from_rounds(
            condition_id=condition_id,
            strategy=strategy,
            category=category,
            question_style=question_style,
            rounds=rounds
        )

    def _get_all_rounds(self) -> List[Round]:
        """Get all rounds from store."""
        round_ids = self.store.list_rounds()
        return [self.store.get_round(rid) for rid in round_ids]

    def _calculate_accuracy(self, rounds: List[Round]) -> float:
        """Calculate judge accuracy."""
        if not rounds:
            return 0.0

        correct = sum(1 for r in rounds if r.outcome.detection_correct)
        return correct / len(rounds)

    def _calculate_false_accusation_rate(self, rounds: List[Round]) -> float:
        """Calculate false accusation rate."""
        if not rounds:
            return 0.0

        false_accusations = sum(1 for r in rounds if r.outcome.false_accusation)
        return false_accusations / len(rounds)

    def _calculate_by_condition(self, rounds: List[Round]) -> List[ConditionMetrics]:
        """Calculate metrics grouped by condition."""
        # Group rounds by condition (strategy, category, question_style tuple as key)
        by_condition = defaultdict(list)

        for round_obj in rounds:
            # Get condition identifier from round
            strategy = round_obj.setup.storytellers[0].strategy
            category = round_obj.setup.fact_category
            question_style = round_obj.setup.judge.question_style

            # Use tuple as key to avoid parsing issues with underscores
            condition_key = (strategy, category, question_style)
            by_condition[condition_key].append(round_obj)

        # Calculate metrics for each condition
        condition_metrics = []

        for (strategy, category, question_style), condition_rounds in by_condition.items():
            # Create condition_id for display/identification
            condition_id = f"{strategy}|{category}|{question_style}"

            metrics = self._condition_metrics_from_rounds(
                condition_id=condition_id,
                strategy=strategy,
                category=category,
                question_style=question_style,
                rounds=condition_rounds
            )

            condition_metrics.append(metrics)

        return sorted(condition_metrics, key=lambda x: x.condition_id)

    def _condition_metrics_from_rounds(
        self,
        condition_id: str,
        strategy: str,
        category: str,
        question_style: str,
        rounds: List[Round]
    ) -> ConditionMetrics:
        """Calculate metrics for a set of rounds."""
        total_rounds = len(rounds)
        accuracy = self._calculate_accuracy(rounds)
        fibber_success = 1.0 - accuracy
        false_accusation = self._calculate_false_accusation_rate(rounds)

        # Calculate average confidence
        confidences = [r.verdict.confidence for r in rounds]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Calculate confidence when correct vs wrong
        correct_rounds = [r for r in rounds if r.outcome.detection_correct]
        wrong_rounds = [r for r in rounds if not r.outcome.detection_correct]

        avg_confidence_correct = (
            sum(r.verdict.confidence for r in correct_rounds) / len(correct_rounds)
            if correct_rounds else 0.0
        )
        avg_confidence_wrong = (
            sum(r.verdict.confidence for r in wrong_rounds) / len(wrong_rounds)
            if wrong_rounds else 0.0
        )

        return ConditionMetrics(
            condition_id=condition_id,
            strategy=strategy,
            category=category,
            question_style=question_style,
            total_rounds=total_rounds,
            judge_accuracy=accuracy,
            fibber_success_rate=fibber_success,
            false_accusation_rate=false_accusation,
            avg_confidence=avg_confidence,
            avg_confidence_when_correct=avg_confidence_correct,
            avg_confidence_when_wrong=avg_confidence_wrong
        )

    def _calculate_by_temperature(self, rounds: List[Round]) -> Dict[float, float]:
        """Calculate accuracy breakdown by judge temperature.

        Args:
            rounds: List of rounds to analyze

        Returns:
            Dict mapping temperature -> accuracy
        """
        by_temp = defaultdict(list)

        for round_obj in rounds:
            temp = round_obj.setup.judge.temperature
            by_temp[temp].append(round_obj)

        return {
            temp: self._calculate_accuracy(temp_rounds)
            for temp, temp_rounds in sorted(by_temp.items())
        }

    def _calculate_by_dimension(
        self,
        rounds: List[Round],
        dimension: str
    ) -> Dict[str, float]:
        """Calculate accuracy grouped by a dimension.

        Args:
            rounds: List of rounds
            dimension: 'strategy', 'category', or 'question_style'

        Returns:
            Dictionary mapping dimension values to accuracy
        """
        by_dim = defaultdict(list)

        for round_obj in rounds:
            if dimension == 'strategy':
                key = round_obj.setup.storytellers[0].strategy
            elif dimension == 'category':
                key = round_obj.setup.fact_category
            elif dimension == 'question_style':
                key = round_obj.setup.judge.question_style
            else:
                continue

            by_dim[key].append(round_obj)

        # Calculate accuracy for each group
        result = {}
        for key, group_rounds in by_dim.items():
            result[key] = self._calculate_accuracy(group_rounds)

        return result

    def _calculate_calibration(self, rounds: List[Round]) -> CalibrationMetrics:
        """Calculate confidence calibration metrics.

        Calibration measures how well confidence scores match actual accuracy.
        Well-calibrated: 80% confidence → 80% accuracy
        """
        if not rounds:
            return CalibrationMetrics(buckets=[], calibration_error=0.0, brier_score=0.0)

        # Create buckets for confidence ranges
        buckets = [
            (1, 3, "1-3 (Low)"),
            (4, 6, "4-6 (Medium)"),
            (7, 8, "7-8 (High)"),
            (9, 10, "9-10 (Very High)")
        ]

        bucket_metrics = []
        total_calibration_error = 0.0
        brier_score = 0.0

        for min_conf, max_conf, label in buckets:
            # Get rounds in this confidence range
            bucket_rounds = [
                r for r in rounds
                if min_conf <= r.verdict.confidence <= max_conf
            ]

            if not bucket_rounds:
                continue

            # Calculate metrics for this bucket
            accuracy = self._calculate_accuracy(bucket_rounds)
            avg_conf = sum(r.verdict.confidence for r in bucket_rounds) / len(bucket_rounds)

            # Normalize confidence to 0-1 scale
            avg_conf_normalized = avg_conf / 10.0

            # Calibration error: |confidence - accuracy|
            calibration_error = abs(avg_conf_normalized - accuracy)
            total_calibration_error += calibration_error * len(bucket_rounds)

            bucket_metrics.append(CalibrationBucket(
                confidence_range=label,
                num_predictions=len(bucket_rounds),
                accuracy=accuracy,
                avg_confidence=avg_conf
            ))

        # Calculate mean calibration error
        mean_calibration_error = total_calibration_error / len(rounds) if rounds else 0.0

        # Calculate Brier score: mean squared error of predictions
        for round_obj in rounds:
            predicted_prob = round_obj.verdict.confidence / 10.0
            actual = 1.0 if round_obj.outcome.detection_correct else 0.0
            brier_score += (predicted_prob - actual) ** 2

        brier_score /= len(rounds)

        return CalibrationMetrics(
            buckets=bucket_metrics,
            calibration_error=mean_calibration_error,
            brier_score=brier_score
        )

    def _calculate_n_shot_performance(self, rounds: List[Round]) -> List[NShotMetrics]:
        """Calculate performance at each Q&A level (one-shot, two-shot, etc).

        Args:
            rounds: List of all rounds

        Returns:
            List of n-shot metrics, one per Q&A level
        """
        # Group guesses by shot number
        guesses_by_shot: Dict[int, List[tuple]] = defaultdict(list)

        for round_obj in rounds:
            # Get the true fibber ID
            fibber_id = round_obj.outcome.fibber_id

            # Process each intermediate guess
            for guess in round_obj.intermediate_guesses:
                is_correct = (guess.accused_id == fibber_id) if fibber_id else False
                guesses_by_shot[guess.after_qa_number].append(
                    (is_correct, guess.confidence)
                )

        # Calculate metrics for each shot level
        n_shot_metrics = []
        for shot_number in sorted(guesses_by_shot.keys()):
            guesses = guesses_by_shot[shot_number]
            total = len(guesses)
            correct = sum(1 for is_correct, _ in guesses if is_correct)
            accuracy = correct / total if total > 0 else 0.0
            avg_confidence = sum(conf for _, conf in guesses) / total if total > 0 else 0.0

            n_shot_metrics.append(NShotMetrics(
                shot_number=shot_number,
                total_guesses=total,
                accuracy=accuracy,
                avg_confidence=avg_confidence
            ))

        return n_shot_metrics

    def _empty_metrics(self) -> ExperimentMetrics:
        """Return empty metrics when no rounds are available."""
        return ExperimentMetrics(
            total_rounds=0,
            overall_judge_accuracy=0.0,
            overall_fibber_success=0.0,
            overall_false_accusation=0.0,
            by_condition=[],
            by_strategy={},
            by_category={},
            by_question_style={},
            by_temperature={},
            calibration=CalibrationMetrics(buckets=[], calibration_error=0.0, brier_score=0.0),
            n_shot_performance=[]
        )
