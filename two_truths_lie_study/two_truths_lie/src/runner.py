"""Experiment runner for systematic multi-round execution.

This module orchestrates full experimental runs with:
- Condition enumeration
- Cost estimation
- Progress tracking
- Checkpointing and resumption
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import logging
from datetime import datetime
import itertools

from .config.schema import ExperimentConfig, ConditionConfig, LLMConfig, GameConfig
from .engine import GameEngine
from .storage import ResultStore
from .models import Round

logger = logging.getLogger(__name__)


@dataclass
class CostEstimate:
    """Estimated API costs for an experiment.

    Attributes:
        total_rounds: Total number of rounds to run
        estimated_tokens_per_round: Estimated tokens per round
        estimated_total_tokens: Total estimated tokens
        estimated_cost_usd: Estimated cost in USD
        breakdown_by_model: Cost breakdown per model
    """

    total_rounds: int
    estimated_tokens_per_round: int
    estimated_total_tokens: int
    estimated_cost_usd: float
    breakdown_by_model: Dict[str, float]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ExperimentCheckpoint:
    """Checkpoint for resuming experiments.

    Attributes:
        experiment_name: Name of the experiment
        total_conditions: Total number of conditions
        rounds_per_condition: Rounds per condition
        completed_rounds: Number of completed rounds
        completed_conditions: List of completed condition IDs
        current_condition_index: Index of current condition
        timestamp: When checkpoint was created
        config: Full experiment configuration
    """

    experiment_name: str
    total_conditions: int
    rounds_per_condition: int
    completed_rounds: int
    completed_conditions: List[str]
    current_condition_index: int
    timestamp: str
    config: Dict[str, Any]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ExperimentCheckpoint":
        """Load from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class ExperimentResults:
    """Results summary for a completed experiment.

    Attributes:
        experiment_name: Name of the experiment
        total_rounds: Total rounds executed
        total_conditions: Number of unique conditions
        duration_seconds: Total execution time
        judge_accuracy: Overall judge accuracy
        results_dir: Directory containing results
        checkpoint_path: Path to final checkpoint
    """

    experiment_name: str
    total_rounds: int
    total_conditions: int
    duration_seconds: float
    judge_accuracy: float
    results_dir: str
    checkpoint_path: Optional[str] = None


class ExperimentRunner:
    """Orchestrates multi-round experiments with checkpointing.

    This class handles:
    - Generating all experimental conditions
    - Estimating costs before execution
    - Running experiments with progress logging
    - Checkpointing after each round for safe resumption
    - Resuming from checkpoints after interruption
    """

    def __init__(
        self,
        config: ExperimentConfig,
        engine: GameEngine,
        store: ResultStore
    ):
        """Initialize the experiment runner.

        Args:
            config: Experiment configuration
            engine: Game engine for running rounds
            store: Result store for persistence
        """
        self.config = config
        self.engine = engine
        self.store = store
        self.output_dir = Path(config.output_dir)
        self.checkpoint_dir = self.output_dir / "checkpoints"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def generate_conditions(self) -> List[ConditionConfig]:
        """Generate all condition combinations.

        Creates the Cartesian product of:
        - Strategies
        - Categories
        - Question styles

        Returns:
            List of all unique experimental conditions
        """
        conditions = []

        # Generate all combinations
        for strategy, category, question_style in itertools.product(
            self.config.strategies,
            self.config.categories,
            self.config.question_styles
        ):
            condition = ConditionConfig(
                judge_model=self.config.judge_model,
                storyteller_model=self.config.storyteller_model,
                game=self.config.game,
                storyteller_strategy=strategy,
                judge_question_style=question_style,
                fact_category=category
            )
            conditions.append(condition)

        logger.info(f"Generated {len(conditions)} unique conditions")
        return conditions

    def estimate_cost(self, conditions: List[ConditionConfig]) -> CostEstimate:
        """Estimate API costs before running.

        Uses rough estimates:
        - Story generation: ~500 tokens per story (3 stories)
        - Questions: ~200 tokens per question (3 storytellers × N questions)
        - Answers: ~150 tokens per answer (3 storytellers × N questions)
        - Verdict: ~800 tokens

        Args:
            conditions: List of conditions to estimate

        Returns:
            Cost estimate with breakdown
        """
        total_rounds = len(conditions) * self.config.rounds_per_condition
        questions_per_round = self.config.game.questions_per_storyteller * self.config.game.num_storytellers

        # Token estimates (conservative)
        tokens_per_story = 500
        tokens_per_question = 200
        tokens_per_answer = 150
        tokens_per_verdict = 800

        # Calculate per round
        story_tokens = tokens_per_story * self.config.game.num_storytellers
        qa_tokens = (tokens_per_question + tokens_per_answer) * questions_per_round
        verdict_tokens = tokens_per_verdict

        estimated_tokens_per_round = story_tokens + qa_tokens + verdict_tokens
        estimated_total_tokens = estimated_tokens_per_round * total_rounds

        # Cost estimation (using Claude 3.5 Haiku pricing as baseline)
        # Input: $0.80 / 1M tokens, Output: $4.00 / 1M tokens
        # Assume 60% output, 40% input
        input_tokens = estimated_total_tokens * 0.4
        output_tokens = estimated_total_tokens * 0.6

        input_cost = (input_tokens / 1_000_000) * 0.80
        output_cost = (output_tokens / 1_000_000) * 4.00
        estimated_cost_usd = input_cost + output_cost

        # Breakdown by model
        breakdown = {
            "judge_model": estimated_cost_usd * 0.4,  # ~40% of cost
            "storyteller_model": estimated_cost_usd * 0.6  # ~60% of cost
        }

        return CostEstimate(
            total_rounds=total_rounds,
            estimated_tokens_per_round=estimated_tokens_per_round,
            estimated_total_tokens=estimated_total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            breakdown_by_model=breakdown
        )

    def _create_checkpoint(
        self,
        conditions: List[ConditionConfig],
        current_condition_index: int,
        completed_rounds: int
    ) -> ExperimentCheckpoint:
        """Create a checkpoint.

        Args:
            conditions: All conditions
            current_condition_index: Index of current condition
            completed_rounds: Number of completed rounds

        Returns:
            Checkpoint object
        """
        # Generate condition IDs (hash of condition params)
        completed_condition_ids = []
        for i in range(current_condition_index):
            condition = conditions[i]
            condition_id = f"{condition.storyteller_strategy}_{condition.fact_category}_{condition.judge_question_style}"
            # Count how many rounds completed for this condition
            completed_condition_ids.append(condition_id)

        return ExperimentCheckpoint(
            experiment_name=self.config.name,
            total_conditions=len(conditions),
            rounds_per_condition=self.config.rounds_per_condition,
            completed_rounds=completed_rounds,
            completed_conditions=completed_condition_ids,
            current_condition_index=current_condition_index,
            timestamp=datetime.now().isoformat(),
            config=self._config_to_dict()
        )

    def _save_checkpoint(self, checkpoint: ExperimentCheckpoint) -> Path:
        """Save checkpoint to disk.

        Args:
            checkpoint: Checkpoint to save

        Returns:
            Path to saved checkpoint
        """
        checkpoint_path = self.checkpoint_dir / f"checkpoint_{checkpoint.experiment_name}.json"
        with open(checkpoint_path, 'w') as f:
            f.write(checkpoint.to_json())

        logger.info(f"Checkpoint saved: {checkpoint_path}")
        return checkpoint_path

    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for checkpointing."""
        return {
            "name": self.config.name,
            "judge_model": {
                "name": self.config.judge_model.name,
                "temperature": self.config.judge_model.temperature
            },
            "storyteller_model": {
                "name": self.config.storyteller_model.name,
                "temperature": self.config.storyteller_model.temperature
            },
            "rounds_per_condition": self.config.rounds_per_condition,
            "strategies": self.config.strategies,
            "categories": self.config.categories,
            "question_styles": self.config.question_styles,
            "output_dir": self.config.output_dir
        }

    def run_experiment(
        self,
        rounds_per_condition: Optional[int] = None,
        start_from_checkpoint: bool = False
    ) -> ExperimentResults:
        """Run full experiment with progress logging.

        Args:
            rounds_per_condition: Override config value if provided
            start_from_checkpoint: Whether to look for and resume from checkpoint

        Returns:
            Experiment results summary
        """
        start_time = datetime.now()

        if rounds_per_condition:
            self.config.rounds_per_condition = rounds_per_condition

        logger.info("=" * 60)
        logger.info(f"Starting experiment: {self.config.name}")
        logger.info("=" * 60)

        # Generate conditions
        conditions = self.generate_conditions()

        # Estimate cost
        cost_estimate = self.estimate_cost(conditions)
        logger.info(f"Cost estimate: ${cost_estimate.estimated_cost_usd:.2f} USD")
        logger.info(f"  Total rounds: {cost_estimate.total_rounds}")
        logger.info(f"  Estimated tokens: {cost_estimate.estimated_total_tokens:,}")

        # Check for existing checkpoint if requested
        starting_condition_idx = 0
        completed_rounds = 0

        if start_from_checkpoint:
            checkpoint_path = self.checkpoint_dir / f"checkpoint_{self.config.name}.json"
            if checkpoint_path.exists():
                logger.info(f"Resuming from checkpoint: {checkpoint_path}")
                with open(checkpoint_path, 'r') as f:
                    checkpoint = ExperimentCheckpoint.from_json(f.read())
                starting_condition_idx = checkpoint.current_condition_index
                completed_rounds = checkpoint.completed_rounds
                logger.info(f"Resuming from condition {starting_condition_idx + 1}/{len(conditions)}")
                logger.info(f"Already completed: {completed_rounds} rounds")

        # Run all conditions
        total_completed = completed_rounds

        for cond_idx in range(starting_condition_idx, len(conditions)):
            condition = conditions[cond_idx]

            logger.info("")
            logger.info(f"Condition {cond_idx + 1}/{len(conditions)}")
            logger.info(f"  Strategy: {condition.storyteller_strategy}")
            logger.info(f"  Category: {condition.fact_category}")
            logger.info(f"  Question style: {condition.judge_question_style}")

            # Run rounds for this condition
            for round_num in range(self.config.rounds_per_condition):
                logger.info(f"  Round {round_num + 1}/{self.config.rounds_per_condition}")

                try:
                    # Execute round
                    round_result = self.engine.run_round(condition)

                    # Save result
                    self.store.save_round(round_result)

                    total_completed += 1

                    # Log outcome
                    outcome_str = "✓ CORRECT" if round_result.outcome.detection_correct else "✗ INCORRECT"
                    logger.info(f"    {outcome_str} (confidence: {round_result.verdict.confidence}/10)")

                except Exception as e:
                    logger.error(f"    Round failed: {e}", exc_info=True)
                    # Continue with next round

                # Checkpoint after each round
                checkpoint = self._create_checkpoint(
                    conditions=conditions,
                    current_condition_index=cond_idx if round_num == self.config.rounds_per_condition - 1 else cond_idx,
                    completed_rounds=total_completed
                )
                self._save_checkpoint(checkpoint)

        # Calculate final metrics
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        summary = self.store.get_summary()

        logger.info("")
        logger.info("=" * 60)
        logger.info("Experiment Complete")
        logger.info("=" * 60)
        logger.info(f"Total rounds: {total_completed}")
        logger.info(f"Judge accuracy: {summary.judge_accuracy:.1%}")
        logger.info(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        logger.info(f"Results saved to: {self.output_dir}")

        return ExperimentResults(
            experiment_name=self.config.name,
            total_rounds=total_completed,
            total_conditions=len(conditions),
            duration_seconds=duration,
            judge_accuracy=summary.judge_accuracy,
            results_dir=str(self.output_dir),
            checkpoint_path=str(self.checkpoint_dir / f"checkpoint_{self.config.name}.json")
        )

    def resume_experiment(self, checkpoint_path: str) -> ExperimentResults:
        """Resume from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Experiment results summary
        """
        logger.info(f"Resuming experiment from: {checkpoint_path}")

        with open(checkpoint_path, 'r') as f:
            checkpoint = ExperimentCheckpoint.from_json(f.read())

        logger.info(f"Loaded checkpoint for: {checkpoint.experiment_name}")
        logger.info(f"Progress: {checkpoint.completed_rounds} rounds completed")

        # Run experiment starting from checkpoint
        return self.run_experiment(start_from_checkpoint=True)
