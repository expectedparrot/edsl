"""CLI entry point for Two Truths and a Lie game."""

import argparse
import sys
import json
from pathlib import Path

from .config import (
    ModelConfig, GameConfig, ConditionConfig, ExperimentConfig,
    LLMConfig, get_mvp_config
)
from .engine import GameEngine
from .edsl_adapter import EDSLAdapter
from .facts.database import get_default_facts
from .logging_config import setup_logging, get_logger
from .runner import ExperimentRunner
from .storage import ResultStore
from .metrics import MetricsCalculator


def run_round(args):
    """Run a single game round."""
    # Setup logging
    log_file = Path(args.output_dir) / "logs" / "game.log" if args.output_dir else None
    setup_logging(level=args.log_level, log_file=log_file)
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("Two Truths and a Lie: Starting Single Round")
    logger.info("=" * 60)

    # Build condition from args
    judge_model = ModelConfig(
        name=args.model,
        temperature=args.temperature
    )
    storyteller_model = ModelConfig(
        name=args.model,
        temperature=args.temperature
    )
    game_config = GameConfig(
        num_storytellers=3,
        num_truth_tellers=2,
        questions_per_storyteller=args.questions,
        game_type=args.game_type
    )

    condition = ConditionConfig(
        judge_model=judge_model,
        storyteller_model=storyteller_model,
        game=game_config,
        storyteller_strategy=args.strategy,
        judge_question_style=args.question_style,
        fact_category=args.category
    )

    logger.info(f"Model: {args.model}")
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"Category: {args.category}")
    logger.info(f"Game type: {args.game_type}")

    # Create components
    adapter = EDSLAdapter(judge_model)
    facts = get_default_facts()
    engine = GameEngine(game_config, adapter, facts)

    # Run the round
    try:
        round_data = engine.run_round(condition)

        # Display results
        print("\n" + "=" * 60)
        print("ROUND COMPLETE")
        print("=" * 60)

        print(f"\nRound ID: {round_data.round_id}")
        print(f"Duration: {round_data.duration_seconds:.1f} seconds")

        print("\n--- STORYTELLERS ---")
        for storyteller in round_data.setup.storytellers:
            role_label = "TRUTH" if storyteller.is_truth_teller else "FIBBER"
            print(f"  {storyteller.id}: {role_label}")

        print("\n--- STORIES ---")
        for story in round_data.stories:
            storyteller = round_data.setup.get_storyteller(story.storyteller_id)
            role_label = "TRUTH" if storyteller.is_truth_teller else "FIBBER"
            print(f"\nStoryteller {story.storyteller_id} ({role_label}):")
            print(f"  Word count: {story.word_count}")
            print(f"  Preview: {story.get_preview(30)}")

        print("\n--- VERDICT ---")
        print(f"  Judge accused: Storyteller {round_data.verdict.accused_id}")
        print(f"  Confidence: {round_data.verdict.confidence}/10")
        print(f"  Reasoning: {round_data.verdict.reasoning[:200]}...")

        print("\n--- OUTCOME ---")
        if round_data.outcome.detection_correct:
            print("  CORRECT! Judge identified the fibber.")
        else:
            print(f"  INCORRECT! Judge accused {round_data.outcome.accused_id}, "
                  f"but fibber was {round_data.outcome.fibber_id}")

        # Save results if output_dir specified
        if args.output_dir:
            output_path = Path(args.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            result_file = output_path / f"round_{round_data.round_id}.json"
            with open(result_file, "w") as f:
                f.write(round_data.to_json())

            print(f"\nResults saved to: {result_file}")

        return 0

    except Exception as e:
        logger.error(f"Round failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        return 1


def show_facts(args):
    """Show available facts in the database."""
    facts = get_default_facts()

    print("\n" + "=" * 60)
    print("AVAILABLE FACTS")
    print("=" * 60)

    if args.category:
        categories = [args.category]
    else:
        categories = facts.categories

    for category in sorted(categories):
        print(f"\n--- {category.upper()} ---")
        category_facts = facts.get_facts_by_category(category)
        for fact in category_facts:
            print(f"\n  [{fact.id}] {fact.title}")
            print(f"  Strangeness: {fact.strangeness_rating}/10")
            print(f"  {fact.content[:150]}...")

    print(f"\nTotal facts: {len(facts)}")
    print(f"Categories: {', '.join(sorted(facts.categories))}")

    return 0


def run_experiment(args):
    """Run a full experiment."""
    # Setup logging
    log_file = Path(args.output_dir) / "logs" / "experiment.log"
    setup_logging(level=args.log_level, log_file=log_file)
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("Starting Experiment")
    logger.info("=" * 60)

    # Build experiment config
    config = ExperimentConfig(
        name=args.name,
        judge_model=LLMConfig(name=args.judge_model, temperature=args.judge_temperature),
        storyteller_model=LLMConfig(name=args.storyteller_model, temperature=args.storyteller_temperature),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=args.questions
        ),
        rounds_per_condition=args.rounds_per_condition,
        strategies=args.strategies,
        categories=args.categories,
        question_styles=args.question_styles,
        output_dir=args.output_dir
    )

    # Create components
    store = ResultStore(base_dir=config.output_dir)
    adapter = EDSLAdapter(config.judge_model)
    facts = get_default_facts()
    engine = GameEngine(config.game, adapter, facts)
    runner = ExperimentRunner(config, engine, store)

    # Show cost estimate
    conditions = runner.generate_conditions()
    cost_estimate = runner.estimate_cost(conditions)

    logger.info(f"\nExperiment: {config.name}")
    logger.info(f"Conditions: {len(conditions)}")
    logger.info(f"Rounds per condition: {config.rounds_per_condition}")
    logger.info(f"Total rounds: {cost_estimate.total_rounds}")
    logger.info(f"\nEstimated cost: ${cost_estimate.estimated_cost_usd:.2f}")
    logger.info(f"Estimated tokens: {cost_estimate.estimated_total_tokens:,}")

    if not args.yes:
        response = input("\nProceed with experiment? (y/n): ")
        if response.lower() != 'y':
            logger.info("Experiment cancelled")
            return 1

    # Run experiment
    try:
        results = runner.run_experiment()

        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Total rounds: {results.total_rounds}")
        print(f"Judge accuracy: {results.judge_accuracy:.1%}")
        print(f"Duration: {results.duration_seconds/60:.1f} minutes")
        print(f"Results: {results.results_dir}")

        return 0

    except KeyboardInterrupt:
        logger.info("\nExperiment interrupted by user")
        logger.info(f"Progress saved in checkpoint: {runner.checkpoint_dir}")
        logger.info("Use 'resume' command to continue")
        return 1


def resume_experiment(args):
    """Resume an experiment from checkpoint."""
    # Setup logging
    log_file = Path(args.checkpoint).parent.parent / "logs" / "experiment.log"
    setup_logging(level=args.log_level, log_file=log_file)
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("Resuming Experiment")
    logger.info("=" * 60)

    checkpoint_path = Path(args.checkpoint)

    if not checkpoint_path.exists():
        print(f"ERROR: Checkpoint file not found: {checkpoint_path}")
        return 1

    # Load checkpoint to get config
    with open(checkpoint_path, 'r') as f:
        checkpoint_data = json.load(f)

    output_dir = checkpoint_data["config"]["output_dir"]

    # Recreate components from config
    config = ExperimentConfig(
        name=checkpoint_data["config"]["name"],
        judge_model=LLMConfig(**checkpoint_data["config"]["judge_model"]),
        storyteller_model=LLMConfig(**checkpoint_data["config"]["storyteller_model"]),
        game=GameConfig(),
        rounds_per_condition=checkpoint_data["config"]["rounds_per_condition"],
        strategies=checkpoint_data["config"]["strategies"],
        categories=checkpoint_data["config"]["categories"],
        question_styles=checkpoint_data["config"]["question_styles"],
        output_dir=output_dir
    )

    store = ResultStore(base_dir=config.output_dir)
    adapter = EDSLAdapter(config.judge_model)
    facts = get_default_facts()
    engine = GameEngine(config.game, adapter, facts)
    runner = ExperimentRunner(config, engine, store)

    logger.info(f"Checkpoint: {checkpoint_path}")
    logger.info(f"Completed rounds: {checkpoint_data['completed_rounds']}")
    logger.info(f"Current condition: {checkpoint_data['current_condition_index'] + 1}/{checkpoint_data['total_conditions']}")

    # Resume
    try:
        results = runner.resume_experiment(str(checkpoint_path))

        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(f"Total rounds: {results.total_rounds}")
        print(f"Judge accuracy: {results.judge_accuracy:.1%}")
        print(f"Duration: {results.duration_seconds/60:.1f} minutes")

        return 0

    except Exception as e:
        logger.error(f"Resume failed: {e}", exc_info=True)
        return 1


def generate_report(args):
    """Generate metrics report from experiment results."""
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return 1

    # Load results and calculate metrics
    store = ResultStore(base_dir=str(results_dir))
    calculator = MetricsCalculator(store)
    metrics = calculator.calculate_all_metrics()

    print("\n" + "=" * 60)
    print("EXPERIMENT METRICS REPORT")
    print("=" * 60)

    print(f"\nTotal Rounds: {metrics.total_rounds}")

    print("\n--- OVERALL PERFORMANCE ---")
    print(f"Judge Accuracy: {metrics.overall_judge_accuracy:.1%}")
    print(f"Fibber Success Rate: {metrics.overall_fibber_success:.1%}")
    print(f"False Accusation Rate: {metrics.overall_false_accusation:.1%}")

    if metrics.by_strategy:
        print("\n--- BY STRATEGY ---")
        for strategy, accuracy in sorted(metrics.by_strategy.items()):
            print(f"  {strategy:20s}: {accuracy:.1%}")

    if metrics.by_category:
        print("\n--- BY CATEGORY ---")
        for category, accuracy in sorted(metrics.by_category.items()):
            print(f"  {category:20s}: {accuracy:.1%}")

    if metrics.by_question_style:
        print("\n--- BY QUESTION STYLE ---")
        for style, accuracy in sorted(metrics.by_question_style.items()):
            print(f"  {style:20s}: {accuracy:.1%}")

    if metrics.by_temperature:
        print("\n--- BY TEMPERATURE ---")
        for temp, accuracy in sorted(metrics.by_temperature.items()):
            print(f"  {temp:.1f}:              {accuracy:.1%}")

    if metrics.by_condition:
        print("\n--- BY CONDITION ---")
        for cond in metrics.by_condition:
            print(f"\n  {cond.condition_id}")
            print(f"    Rounds: {cond.total_rounds}")
            print(f"    Accuracy: {cond.judge_accuracy:.1%}")
            print(f"    Avg Confidence: {cond.avg_confidence:.1f}/10")
            print(f"    Confidence (correct): {cond.avg_confidence_when_correct:.1f}/10")
            print(f"    Confidence (wrong): {cond.avg_confidence_when_wrong:.1f}/10")

    print("\n--- CALIBRATION ---")
    print(f"Calibration Error: {metrics.calibration.calibration_error:.3f}")
    print(f"Brier Score: {metrics.calibration.brier_score:.3f}")
    print("\nConfidence Buckets:")
    for bucket in metrics.calibration.buckets:
        print(f"  {bucket.confidence_range:15s}: {bucket.num_predictions:3d} predictions, {bucket.accuracy:.1%} accuracy")

    # Save report to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(json.dumps({
                "total_rounds": metrics.total_rounds,
                "overall_judge_accuracy": metrics.overall_judge_accuracy,
                "overall_fibber_success": metrics.overall_fibber_success,
                "overall_false_accusation": metrics.overall_false_accusation,
                "by_strategy": metrics.by_strategy,
                "by_category": metrics.by_category,
                "by_question_style": metrics.by_question_style,
                "by_condition": [
                    {
                        "condition_id": c.condition_id,
                        "strategy": c.strategy,
                        "category": c.category,
                        "question_style": c.question_style,
                        "total_rounds": c.total_rounds,
                        "judge_accuracy": c.judge_accuracy,
                        "avg_confidence": c.avg_confidence
                    }
                    for c in metrics.by_condition
                ],
                "calibration": {
                    "calibration_error": metrics.calibration.calibration_error,
                    "brier_score": metrics.calibration.brier_score,
                    "buckets": [
                        {
                            "range": b.confidence_range,
                            "num_predictions": b.num_predictions,
                            "accuracy": b.accuracy
                        }
                        for b in metrics.calibration.buckets
                    ]
                }
            }, indent=2))

        print(f"\nReport saved to: {output_path}")

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Two Truths and a Lie: LLM Storytelling Challenge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a single round with default settings
  python -m src run-round

  # Run with specific model and strategy
  python -m src run-round --model claude-3-5-sonnet-20241022 --strategy source_heavy

  # Run with a specific fact category
  python -m src run-round --category history

  # Show available facts
  python -m src show-facts

  # Show facts in a specific category
  python -m src show-facts --category science
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-round command
    round_parser = subparsers.add_parser(
        "run-round",
        help="Run a single game round"
    )
    round_parser.add_argument(
        "--model", "-m",
        default="claude-3-5-sonnet-20241022",
        help="Model to use (default: claude-3-5-sonnet-20241022)"
    )
    round_parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=1.0,
        help="Temperature for generation (default: 1.0)"
    )
    round_parser.add_argument(
        "--strategy", "-s",
        default="baseline",
        choices=["baseline", "level_k_0", "level_k_1", "level_k_2",
                 "source_heavy", "source_light", "detail_granular",
                 "detail_general", "style_logical", "style_emotional"],
        help="Storytelling strategy (default: baseline)"
    )
    round_parser.add_argument(
        "--category", "-c",
        default="science",
        choices=["science", "history", "biology", "geography", "technology", "culture"],
        help="Fact category (default: science)"
    )
    round_parser.add_argument(
        "--question-style", "-q",
        default="curious",
        choices=["adversarial", "curious", "verification", "intuitive"],
        help="Judge's questioning style (default: curious)"
    )
    round_parser.add_argument(
        "--questions",
        type=int,
        default=3,
        help="Questions per storyteller (default: 3)"
    )
    round_parser.add_argument(
        "--game-type", "-g",
        default="standard",
        choices=["standard", "all_truth", "all_lies", "majority_lies"],
        help="Game configuration type (default: standard)"
    )
    round_parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Directory to save results"
    )
    round_parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    round_parser.set_defaults(func=run_round)

    # show-facts command
    facts_parser = subparsers.add_parser(
        "show-facts",
        help="Show available facts in the database"
    )
    facts_parser.add_argument(
        "--category", "-c",
        default=None,
        choices=["science", "history", "biology", "geography", "technology", "culture"],
        help="Show facts from a specific category"
    )
    facts_parser.set_defaults(func=show_facts)

    # run-experiment command
    experiment_parser = subparsers.add_parser(
        "run-experiment",
        help="Run a full multi-round experiment"
    )
    experiment_parser.add_argument(
        "--name", "-n",
        default="experiment",
        help="Experiment name (default: experiment)"
    )
    experiment_parser.add_argument(
        "--judge-model",
        default="claude-3-5-haiku-20241022",
        help="Model for judge (default: claude-3-5-haiku-20241022)"
    )
    experiment_parser.add_argument(
        "--storyteller-model",
        default="claude-3-5-haiku-20241022",
        help="Model for storytellers (default: claude-3-5-haiku-20241022)"
    )
    experiment_parser.add_argument(
        "--judge-temperature",
        type=float,
        default=0.7,
        help="Temperature for judge (default: 0.7)"
    )
    experiment_parser.add_argument(
        "--storyteller-temperature",
        type=float,
        default=1.0,
        help="Temperature for storytellers (default: 1.0)"
    )
    experiment_parser.add_argument(
        "--rounds-per-condition",
        type=int,
        default=10,
        help="Rounds per experimental condition (default: 10)"
    )
    experiment_parser.add_argument(
        "--strategies",
        nargs="+",
        default=["baseline"],
        choices=["baseline", "level_k_0", "level_k_1", "level_k_2",
                 "source_heavy", "source_light", "detail_granular",
                 "detail_general", "style_logical", "style_emotional"],
        help="Storytelling strategies to test (default: baseline)"
    )
    experiment_parser.add_argument(
        "--categories",
        nargs="+",
        default=["science"],
        choices=["science", "history", "biology", "geography", "technology", "culture"],
        help="Fact categories to test (default: science)"
    )
    experiment_parser.add_argument(
        "--question-styles",
        nargs="+",
        default=["curious"],
        choices=["adversarial", "curious", "verification", "intuitive"],
        help="Judge question styles to test (default: curious)"
    )
    experiment_parser.add_argument(
        "--questions",
        type=int,
        default=2,
        help="Questions per storyteller (default: 2)"
    )
    experiment_parser.add_argument(
        "--output-dir", "-o",
        default="results",
        help="Output directory (default: results)"
    )
    experiment_parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    experiment_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    experiment_parser.set_defaults(func=run_experiment)

    # resume command
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume an experiment from checkpoint"
    )
    resume_parser.add_argument(
        "checkpoint",
        help="Path to checkpoint file"
    )
    resume_parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    resume_parser.set_defaults(func=resume_experiment)

    # report command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate metrics report from experiment results"
    )
    report_parser.add_argument(
        "results_dir",
        help="Path to results directory"
    )
    report_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Save report to JSON file"
    )
    report_parser.set_defaults(func=generate_report)

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
