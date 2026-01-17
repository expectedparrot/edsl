"""CLI for fact database generator."""

import argparse
import json
import sys
from pathlib import Path

from .schema import CATEGORIES, Fact
from .generator import MultiModelFactGenerator, BEST_MODELS
from ..logging_config import setup_logging, get_logger


def generate_facts(args):
    """Generate facts using multiple models."""
    setup_logging(level=args.log_level)
    logger = get_logger("facts_cli")

    logger.info("=" * 60)
    logger.info("FACT GENERATION")
    logger.info("=" * 60)

    # Determine models to use
    models = args.models if args.models else BEST_MODELS

    logger.info(f"Models: {', '.join(models)}")
    logger.info(f"Total facts to generate: {args.count}")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = MultiModelFactGenerator(models=models)

    if args.distribute_evenly:
        # Generate facts for all categories
        categories = args.categories if args.categories else CATEGORIES

        logger.info(f"Generating {args.count} facts per category")
        logger.info(f"Categories: {', '.join(categories)}")

        # When --distribute-evenly is used, --count means "per category"
        facts_per_category = args.count

        for category in categories:
            logger.info(f"\nGenerating facts for: {category}")

            facts = generator.generate_facts(
                category=category,
                count=facts_per_category,
                distribute_evenly=True
            )

            # Save to file
            output_file = output_dir / f"{category}.json"
            with open(output_file, 'w') as f:
                json.dump(facts, f, indent=2)

            logger.info(f"  Generated: {len(facts)} facts")
            logger.info(f"  Saved to: {output_file}")

        logger.info("\n" + "=" * 60)
        logger.info("GENERATION COMPLETE")
        logger.info("=" * 60)

    else:
        # Generate for specific category
        if not args.category:
            logger.error("Must specify --category when not using --distribute-evenly")
            return 1

        logger.info(f"Category: {args.category}")

        facts = generator.generate_facts(
            category=args.category,
            count=args.count,
            distribute_evenly=True
        )

        # Save to file
        output_file = output_dir / f"{args.category}.json"
        with open(output_file, 'w') as f:
            json.dump(facts, f, indent=2)

        logger.info(f"\nGenerated: {len(facts)} facts")
        logger.info(f"Saved to: {output_file}")

    return 0


def stats(args):
    """Show statistics for generated facts."""
    setup_logging(level=args.log_level)
    logger = get_logger("facts_cli")

    input_dir = Path(args.input)

    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return 1

    # Load all JSON files
    all_facts = []
    by_category = {}
    by_model = {}

    for json_file in input_dir.glob("*.json"):
        with open(json_file, 'r') as f:
            facts = json.load(f)

            if not isinstance(facts, list):
                logger.warning(f"Skipping {json_file.name}: not a list")
                continue

            for fact in facts:
                all_facts.append(fact)

                category = fact.get('category', 'unknown')
                by_category[category] = by_category.get(category, 0) + 1

                model = fact.get('model_generated_by', 'unknown')
                by_model[model] = by_model.get(model, 0) + 1

    # Print statistics
    print("\n" + "=" * 60)
    print("FACT GENERATION STATISTICS")
    print("=" * 60)
    print(f"\nTotal facts: {len(all_facts)}")

    print("\nBy Category:")
    for category, count in sorted(by_category.items()):
        print(f"  {category:30s}: {count:3d} facts")

    print("\nBy Model:")
    for model, count in sorted(by_model.items()):
        print(f"  {model:40s}: {count:3d} facts")

    return 0


def main():
    """Main entry point for fact database generator CLI."""
    parser = argparse.ArgumentParser(
        description="Fact Database Generator - Generate unusual-but-true facts using LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 110 facts (10 per category) with all 3 models
  python -m facts generate --count 10 --distribute-evenly --output data/raw/

  # Generate 20 facts for sports category
  python -m facts generate --category sports --count 20 --output data/raw/

  # View statistics
  python -m facts stats --input data/raw/
        """
    )

    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # generate command
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate facts using LLMs"
    )
    gen_parser.add_argument(
        "--category", "-c",
        choices=CATEGORIES,
        help="Single category to generate for"
    )
    gen_parser.add_argument(
        "--categories",
        nargs="+",
        choices=CATEGORIES,
        help="Multiple categories to generate for"
    )
    gen_parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Number of facts to generate (per category if --distribute-evenly)"
    )
    gen_parser.add_argument(
        "--models", "-m",
        nargs="+",
        help=f"Models to use (default: {' '.join(BEST_MODELS)})"
    )
    gen_parser.add_argument(
        "--distribute-evenly",
        action="store_true",
        help="Generate facts for all categories evenly"
    )
    gen_parser.add_argument(
        "--output", "-o",
        default="data/raw",
        help="Output directory for generated facts (default: data/raw)"
    )
    gen_parser.set_defaults(func=generate_facts)

    # stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show statistics for generated facts"
    )
    stats_parser.add_argument(
        "--input", "-i",
        default="data/raw",
        help="Input directory with generated facts (default: data/raw)"
    )
    stats_parser.set_defaults(func=stats)

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
