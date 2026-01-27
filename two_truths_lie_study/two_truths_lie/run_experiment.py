#!/opt/homebrew/bin/python3.11
"""Run a small experiment to test the ExperimentRunner."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.schema import ExperimentConfig, LLMConfig, GameConfig
from src.runner import ExperimentRunner
from src.engine import GameEngine
from src.storage import ResultStore
from src.edsl_adapter import EDSLAdapter
from src.facts import get_default_facts
from src.logging_config import setup_logging, get_logger


def main():
    """Run a 16-round experiment."""
    # Setup logging
    setup_logging(level="INFO")
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("Starting 16-Round Experiment")
    logger.info("=" * 60)

    # Create config
    # 2 strategies × 2 categories × 1 question_style = 4 conditions
    # 4 rounds per condition = 16 total rounds
    config = ExperimentConfig(
        name="test_16_rounds",
        judge_model=LLMConfig(
            name="claude-3-5-haiku-20241022",
            temperature=0.7
        ),
        storyteller_model=LLMConfig(
            name="claude-3-5-haiku-20241022",
            temperature=1.0
        ),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=2  # Reduced to save costs
        ),
        rounds_per_condition=4,
        strategies=["baseline", "level_k_0"],
        categories=["science", "history"],
        question_styles=["curious"],
        output_dir="results/test_experiment"
    )

    # Create components
    store = ResultStore(base_dir=config.output_dir)
    adapter = EDSLAdapter(config.judge_model)
    facts = get_default_facts()
    engine = GameEngine(config.game, adapter, facts)

    # Create runner
    runner = ExperimentRunner(config, engine, store)

    # Show cost estimate
    conditions = runner.generate_conditions()
    cost_estimate = runner.estimate_cost(conditions)

    logger.info("")
    logger.info("Experiment Configuration:")
    logger.info(f"  Conditions: {len(conditions)}")
    logger.info(f"  Rounds per condition: {config.rounds_per_condition}")
    logger.info(f"  Total rounds: {cost_estimate.total_rounds}")
    logger.info("")
    logger.info("Cost Estimate:")
    logger.info(f"  Estimated tokens: {cost_estimate.estimated_total_tokens:,}")
    logger.info(f"  Estimated cost: ${cost_estimate.estimated_cost_usd:.2f}")
    logger.info("")

    # Confirm
    response = input("Proceed with experiment? (y/n): ")
    if response.lower() != 'y':
        logger.info("Experiment cancelled.")
        return 1

    # Run experiment
    logger.info("")
    logger.info("Starting experiment execution...")
    logger.info("")

    results = runner.run_experiment()

    # Display summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("EXPERIMENT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total rounds: {results.total_rounds}")
    logger.info(f"Judge accuracy: {results.judge_accuracy:.1%}")
    logger.info(f"Duration: {results.duration_seconds/60:.1f} minutes")
    logger.info(f"Results saved to: {results.results_dir}")
    logger.info("")

    # Show per-condition results
    summary = store.get_summary()
    logger.info("Breakdown by model:")
    for model, count in summary.rounds_by_model.items():
        logger.info(f"  {model}: {count} rounds")

    logger.info("")
    logger.info("Next steps:")
    logger.info("  - View detailed results: ls -lh results/test_experiment/rounds/")
    logger.info("  - View checkpoint: cat results/test_experiment/checkpoints/checkpoint_test_16_rounds.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
