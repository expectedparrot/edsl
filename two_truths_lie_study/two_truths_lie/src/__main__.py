"""CLI entry point for Two Truths and a Lie game."""

import argparse
import sys
import json
from pathlib import Path

from .config import ModelConfig, GameConfig, ConditionConfig, get_mvp_config
from .engine import GameEngine
from .edsl_adapter import EDSLAdapter
from .facts.database import get_default_facts
from .logging_config import setup_logging, get_logger


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

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
