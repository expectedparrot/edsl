#!/usr/bin/env python3
"""
Baseline experiment comparing model categories in Two Truths and a Lie.

Sequential Testing Approach:
- Phase 1: Older models (3 models, ~$1.58)
- Phase 2: Small models (4 models, ~$3.29)
- Phase 3: Flagship models (4 models, ~$29.81) [OPTIONAL]

Usage:
    # Run Phase 1 (older models)
    python run_baseline_experiment.py --phase 1

    # Run Phase 2 (small models)
    python run_baseline_experiment.py --phase 2

    # Run Phase 3 (flagship models) - optional
    python run_baseline_experiment.py --phase 3

    # Run all phases
    python run_baseline_experiment.py --phase all

    # Estimate costs only (dry run)
    python run_baseline_experiment.py --phase 1 --dry-run

    # Custom rounds and cost limit
    python run_baseline_experiment.py --phase 1 --rounds 15 --cost-limit 2.0
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ConditionConfig, LLMConfig, GameConfig
from src.engine import GameEngine
from src.storage import ResultStore
from src.facts.database import get_default_facts
from src.edsl_adapter import EDSLAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Model categories based on EDSL catalog
MODEL_CATEGORIES = {
    "older": [
        "gpt-3.5-turbo",               # OpenAI legacy
        "claude-3-haiku-20240307",     # Early Claude
        "gemini-2.0-flash",            # Gemini 2.0 (replacing 1.5-pro which isn't in EDSL)
    ],
    "small": [
        "claude-3-7-sonnet-20250219",  # Fast Claude
        "gemini-2.5-flash",            # Fast Gemini
        "gpt-4o-mini",                 # Small OpenAI
        "claude-3-5-haiku-20241022",   # Smallest Claude
    ],
    "flagship": [
        "claude-opus-4-5-20251101",    # Latest Claude flagship
        "gpt-4-turbo",                 # OpenAI flagship
        "claude-sonnet-4-5-20250929",  # High-quality Claude
        "chatgpt-4o-latest",           # OpenAI latest
    ],
}

# Fixed baseline model for opposite role
BASELINE_MODEL = "claude-3-5-haiku-20241022"

# Cost estimates per 1M tokens (input, output)
MODEL_PRICING = {
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "gemini-1.5-pro": (1.25, 5.00),
    "claude-3-7-sonnet-20250219": (3.00, 15.00),
    "gemini-2.5-flash": (0.075, 0.30),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-haiku-20241022": (1.00, 5.00),
    "claude-opus-4-5-20251101": (15.00, 75.00),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "chatgpt-4o-latest": (5.00, 15.00),
}


@dataclass
class PhaseConfig:
    """Configuration for an experiment phase."""
    phase_number: int
    phase_name: str
    models: List[str]
    estimated_cost: float
    output_dir: str


def get_phase_config(phase: int, rounds: int = 30) -> PhaseConfig:
    """Get configuration for a specific phase.

    Args:
        phase: Phase number (1, 2, or 3)
        rounds: Rounds per condition

    Returns:
        PhaseConfig with models and estimated costs
    """
    if phase == 1:
        category = "older"
        name = "Older/Legacy Models"
        base_cost = 1.58
    elif phase == 2:
        category = "small"
        name = "Small/Fast Models"
        base_cost = 3.29
    elif phase == 3:
        category = "flagship"
        name = "Flagship Models"
        base_cost = 29.81
    else:
        raise ValueError(f"Invalid phase: {phase}. Must be 1, 2, or 3.")

    models = MODEL_CATEGORIES[category]
    # Scale cost by rounds (base is for 30 rounds)
    estimated_cost = base_cost * (rounds / 30.0)

    return PhaseConfig(
        phase_number=phase,
        phase_name=name,
        models=models,
        estimated_cost=estimated_cost,
        output_dir=f"results/phase{phase}_{category}"
    )


def create_baseline_condition(
    model_name: str,
    role: str,
    rounds_id: int = 0
) -> ConditionConfig:
    """Create a single baseline experimental condition.

    Args:
        model_name: Model to test
        role: Either "judge" or "storyteller"
        rounds_id: Identifier for tracking multiple rounds of same condition

    Returns:
        ConditionConfig for this experimental setup

    Note:
        fact_category is intentionally left as default in schema (will use random
        selection across all 99 facts during execution)
    """
    if role == "judge":
        judge_model = model_name
        storyteller_model = BASELINE_MODEL
    elif role == "storyteller":
        judge_model = BASELINE_MODEL
        storyteller_model = model_name
    else:
        raise ValueError(f"Invalid role: {role}. Must be 'judge' or 'storyteller'.")

    return ConditionConfig(
        judge_model=LLMConfig(name=judge_model, temperature=1.0),
        storyteller_model=LLMConfig(name=storyteller_model, temperature=1.0),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=1,  # 1-shot
            story_word_min=250,
            story_word_max=500,
            answer_word_min=25,
            answer_word_max=150,
            game_type="standard",
        ),
        storyteller_strategy="baseline",
        judge_question_style="curious",
        fact_category=None,  # None = random selection across all 99 facts
    )


def generate_phase_conditions(
    phase_config: PhaseConfig
) -> List[tuple[ConditionConfig, Dict[str, Any]]]:
    """Generate all conditions for a phase.

    Args:
        phase_config: Phase configuration

    Returns:
        List of (condition, metadata) tuples
    """
    conditions_with_metadata = []
    roles = ["judge", "storyteller"]

    for model_name in phase_config.models:
        for role in roles:
            condition = create_baseline_condition(model_name, role)

            metadata = {
                "phase": phase_config.phase_number,
                "phase_name": phase_config.phase_name,
                "model_category": "older" if phase_config.phase_number == 1 else
                                 "small" if phase_config.phase_number == 2 else "flagship",
                "test_model": model_name,
                "test_role": role,
            }

            conditions_with_metadata.append((condition, metadata))

    logger.info(f"Generated {len(conditions_with_metadata)} conditions for Phase {phase_config.phase_number}")
    return conditions_with_metadata


def estimate_condition_cost(
    condition: ConditionConfig,
    rounds: int = 1
) -> float:
    """Estimate cost for running a condition.

    Args:
        condition: Condition to estimate
        rounds: Number of rounds

    Returns:
        Estimated cost in USD
    """
    # Token estimates per round (conservative)
    tokens_per_round = 2000
    input_tokens = tokens_per_round * 0.4
    output_tokens = tokens_per_round * 0.6

    # Get pricing for both models
    judge_pricing = MODEL_PRICING.get(condition.judge_model.name, (3.0, 15.0))
    storyteller_pricing = MODEL_PRICING.get(condition.storyteller_model.name, (3.0, 15.0))

    # Judge costs (verdict generation is output-heavy)
    judge_cost = (
        (input_tokens * 0.3 / 1_000_000) * judge_pricing[0] +
        (output_tokens * 0.3 / 1_000_000) * judge_pricing[1]
    )

    # Storyteller costs (story generation is output-heavy)
    storyteller_cost = (
        (input_tokens * 0.7 / 1_000_000) * storyteller_pricing[0] +
        (output_tokens * 0.7 / 1_000_000) * storyteller_pricing[1]
    )

    return (judge_cost + storyteller_cost) * rounds


def estimate_phase_cost(
    phase_config: PhaseConfig,
    rounds: int = 30
) -> Dict[str, Any]:
    """Estimate total cost for a phase.

    Args:
        phase_config: Phase configuration
        rounds: Rounds per condition

    Returns:
        Cost breakdown dictionary
    """
    conditions = generate_phase_conditions(phase_config)
    total_cost = 0.0
    cost_by_model = {}

    for condition, metadata in conditions:
        condition_cost = estimate_condition_cost(condition, rounds)
        total_cost += condition_cost

        model = metadata["test_model"]
        cost_by_model[model] = cost_by_model.get(model, 0.0) + condition_cost

    total_rounds = len(conditions) * rounds

    return {
        "phase": phase_config.phase_number,
        "phase_name": phase_config.phase_name,
        "total_conditions": len(conditions),
        "rounds_per_condition": rounds,
        "total_rounds": total_rounds,
        "estimated_cost_usd": total_cost,
        "cost_by_model": cost_by_model,
    }


def run_phase_experiment(
    phase_config: PhaseConfig,
    rounds_per_condition: int = 30,
    cost_limit: float = 100.0,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Execute a phase of the baseline experiment.

    Args:
        phase_config: Phase configuration
        rounds_per_condition: Number of rounds per condition
        cost_limit: Maximum allowed cost in USD
        dry_run: If True, only estimate costs without running

    Returns:
        Results summary dictionary

    Raises:
        ValueError: If estimated cost exceeds limit
    """
    logger.info("=" * 70)
    logger.info(f"PHASE {phase_config.phase_number}: {phase_config.phase_name}")
    logger.info("=" * 70)

    # Estimate costs
    cost_estimate = estimate_phase_cost(phase_config, rounds_per_condition)

    logger.info(f"\nCost Estimate:")
    logger.info(f"  Total conditions: {cost_estimate['total_conditions']}")
    logger.info(f"  Rounds per condition: {cost_estimate['rounds_per_condition']}")
    logger.info(f"  Total rounds: {cost_estimate['total_rounds']}")
    logger.info(f"  Estimated cost: ${cost_estimate['estimated_cost_usd']:.2f}")

    logger.info(f"\n  Cost by model:")
    for model, cost in cost_estimate['cost_by_model'].items():
        logger.info(f"    {model}: ${cost:.2f}")

    # Check cost limit
    if cost_estimate['estimated_cost_usd'] > cost_limit:
        raise ValueError(
            f"Estimated cost ${cost_estimate['estimated_cost_usd']:.2f} "
            f"exceeds limit ${cost_limit:.2f}"
        )

    if dry_run:
        logger.info("\n[DRY RUN] Skipping execution")
        return cost_estimate

    # Generate conditions
    logger.info(f"\nGenerating conditions...")
    conditions_with_metadata = generate_phase_conditions(phase_config)

    # Initialize infrastructure
    logger.info(f"Initializing game engine and storage...")
    fact_db = get_default_facts()
    logger.info(f"Loaded {len(fact_db)} facts from database")

    output_dir = Path(phase_config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create a default game config (will be overridden by conditions)
    default_game_config = GameConfig()

    # Create EDSL adapter with baseline model (actual models come from conditions)
    adapter = EDSLAdapter(LLMConfig(name=BASELINE_MODEL, temperature=1.0))

    # Initialize engine and storage
    engine = GameEngine(default_game_config, adapter, fact_db)
    store = ResultStore(str(output_dir))

    # Run all conditions
    logger.info(f"\nStarting experiment execution...")
    logger.info(f"Output directory: {output_dir}")

    total_completed = 0
    total_correct = 0

    for idx, (condition, metadata) in enumerate(conditions_with_metadata, 1):
        logger.info(f"\nCondition {idx}/{len(conditions_with_metadata)}")
        logger.info(f"  Test model: {metadata['test_model']}")
        logger.info(f"  Test role: {metadata['test_role']}")

        condition_correct = 0

        # Run multiple rounds for this condition
        for round_num in range(rounds_per_condition):
            try:
                # Run the round (condition has fact_category=None for random selection)
                round_result = engine.run_round(condition)

                # Add metadata to setup for analysis
                condition_id = (
                    f"phase{metadata['phase']}_"
                    f"{metadata['model_category']}_"
                    f"{metadata['test_model']}_"
                    f"{metadata['test_role']}"
                )
                # Store condition_id in the setup (mutable after creation)
                round_result.setup.condition_id = condition_id

                # Store result
                store.save_round(round_result)

                total_completed += 1
                if round_result.outcome.detection_correct:
                    total_correct += 1
                    condition_correct += 1

                # Log every 10 rounds
                if (round_num + 1) % 10 == 0:
                    condition_accuracy = condition_correct / (round_num + 1)
                    logger.info(
                        f"    Round {round_num + 1}/{rounds_per_condition} "
                        f"(accuracy: {condition_accuracy:.1%})"
                    )

            except Exception as e:
                logger.error(f"    Round {round_num + 1} failed: {e}", exc_info=True)
                continue

        # Summary for this condition
        condition_accuracy = condition_correct / rounds_per_condition if rounds_per_condition > 0 else 0.0
        logger.info(f"  Condition accuracy: {condition_accuracy:.1%} ({condition_correct}/{rounds_per_condition})")

    # Final summary
    overall_accuracy = total_correct / total_completed if total_completed > 0 else 0.0

    logger.info("\n" + "=" * 70)
    logger.info(f"PHASE {phase_config.phase_number} COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total rounds completed: {total_completed}")
    logger.info(f"Overall judge accuracy: {overall_accuracy:.1%}")
    logger.info(f"Results saved to: {output_dir}")

    return {
        "phase": phase_config.phase_number,
        "phase_name": phase_config.phase_name,
        "total_rounds": total_completed,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "output_dir": str(output_dir),
        "cost_estimate": cost_estimate,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run baseline experiment comparing model categories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--phase",
        type=str,
        required=True,
        choices=["1", "2", "3", "all"],
        help="Phase to run (1=older, 2=small, 3=flagship, all=run all phases)"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=30,
        help="Rounds per condition (default: 30)"
    )
    parser.add_argument(
        "--cost-limit",
        type=float,
        default=100.0,
        help="Maximum cost in USD (default: 100.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate costs only, don't run experiment"
    )

    args = parser.parse_args()

    try:
        # Determine which phases to run
        if args.phase == "all":
            phases = [1, 2, 3]
        else:
            phases = [int(args.phase)]

        # Run each phase
        results = []
        for phase_num in phases:
            phase_config = get_phase_config(phase_num, args.rounds)

            result = run_phase_experiment(
                phase_config=phase_config,
                rounds_per_condition=args.rounds,
                cost_limit=args.cost_limit,
                dry_run=args.dry_run
            )

            results.append(result)

        # Overall summary for multi-phase runs
        if len(results) > 1:
            logger.info("\n" + "=" * 70)
            logger.info("ALL PHASES COMPLETE")
            logger.info("=" * 70)

            total_rounds = sum(r["total_rounds"] for r in results)
            total_cost = sum(r["cost_estimate"]["estimated_cost_usd"] for r in results)

            logger.info(f"Total rounds: {total_rounds}")
            logger.info(f"Total estimated cost: ${total_cost:.2f}")

            for result in results:
                logger.info(
                    f"\nPhase {result['phase']} ({result['phase_name']}): "
                    f"{result['overall_accuracy']:.1%} accuracy"
                )

    except KeyboardInterrupt:
        logger.info("\n\nExperiment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nExperiment failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
