#!/usr/bin/env python3
"""
Analyze baseline experiment results and generate comparison report.

This script processes results from the baseline model category comparison experiment,
generating aggregate statistics and visualizations.

Usage:
    # Analyze single phase results
    python analyze_baseline_results.py results/phase1_older

    # Analyze combined results from multiple phases
    python analyze_baseline_results.py results/phase1_older results/phase2_small

    # Analyze all phases at once
    python analyze_baseline_results.py results/phase*
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
import json

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore
from src.models import Round


def load_results_from_directory(results_dir: str) -> pd.DataFrame:
    """Load experiment results from a directory into DataFrame.

    Args:
        results_dir: Path to results directory

    Returns:
        DataFrame with round data
    """
    store = ResultStore(results_dir)
    round_ids = store.list_rounds()

    if not round_ids:
        print(f"Warning: No rounds found in {results_dir}")
        return pd.DataFrame()

    data = []
    for round_id in round_ids:
        try:
            round_obj = store.get_round(round_id)

            # Extract condition metadata from condition_id if available
            condition_id = round_obj.setup.condition_id or ""
            condition_parts = condition_id.split("_")

            # Parse condition_id format: phase{N}_{category}_{model}_{role}
            if len(condition_parts) >= 4:
                phase_str = condition_parts[0]  # e.g., "phase1"
                model_category = condition_parts[1]
                test_model = condition_parts[2]
                test_role = condition_parts[3]

                # Extract phase number
                phase_num = int(phase_str.replace("phase", ""))
            else:
                # Fallback if condition_id doesn't match expected format
                phase_num = None
                model_category = "unknown"
                test_model = round_obj.setup.judge.model
                test_role = "judge"  # Assume judge if unclear

            row = {
                "round_id": round_obj.round_id,
                "phase": phase_num,
                "model_category": model_category,
                "test_model": test_model,
                "test_role": test_role,
                "judge_model": round_obj.setup.judge.model,
                "storyteller_model": round_obj.setup.storytellers[0].model,
                "fact_category": round_obj.setup.fact_category or "random",
                "detection_correct": round_obj.outcome.detection_correct,
                "judge_confidence": round_obj.verdict.confidence,
                "fibber_evasion": not round_obj.outcome.detection_correct,
                "num_qa_exchanges": len(round_obj.qa_exchanges),
                "duration_seconds": round_obj.duration_seconds,
                "timestamp": round_obj.timestamp,
            }

            data.append(row)

        except Exception as e:
            print(f"Warning: Failed to load round {round_id}: {e}")
            continue

    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} rounds from {results_dir}")

    return df


def load_combined_results(directories: List[str]) -> pd.DataFrame:
    """Load and combine results from multiple directories.

    Args:
        directories: List of result directory paths

    Returns:
        Combined DataFrame
    """
    dfs = []
    for directory in directories:
        df = load_results_from_directory(directory)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        raise ValueError("No results found in any directory")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal combined: {len(combined)} rounds")

    return combined


def calculate_category_metrics(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Calculate performance metrics by model category.

    Args:
        df: DataFrame with round data

    Returns:
        Dictionary mapping category to metrics
    """
    results = {}

    for category in df["model_category"].unique():
        category_df = df[df["model_category"] == category]

        # Judge performance (when test_role == "judge")
        judge_df = category_df[category_df["test_role"] == "judge"]
        judge_accuracy = judge_df["detection_correct"].mean() if len(judge_df) > 0 else None

        # Fibber performance (when test_role == "storyteller")
        fibber_df = category_df[category_df["test_role"] == "storyteller"]
        fibber_evasion = fibber_df["fibber_evasion"].mean() if len(fibber_df) > 0 else None

        # Overall metrics
        results[category] = {
            "judge_accuracy": judge_accuracy,
            "fibber_evasion": fibber_evasion,
            "confidence_mean": category_df["judge_confidence"].mean(),
            "confidence_std": category_df["judge_confidence"].std(),
            "n_judge_rounds": len(judge_df),
            "n_fibber_rounds": len(fibber_df),
            "n_total": len(category_df),
        }

    return results


def calculate_model_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate per-model performance metrics.

    Args:
        df: DataFrame with round data

    Returns:
        DataFrame with model-level metrics
    """
    model_metrics = []

    for test_model in df["test_model"].unique():
        model_df = df[df["test_model"] == test_model]

        for role in ["judge", "storyteller"]:
            role_df = model_df[model_df["test_role"] == role]

            if len(role_df) == 0:
                continue

            if role == "judge":
                accuracy = role_df["detection_correct"].mean()
                metric_name = "judge_accuracy"
                metric_value = accuracy
            else:
                evasion = role_df["fibber_evasion"].mean()
                metric_name = "fibber_evasion"
                metric_value = evasion

            model_metrics.append({
                "model": test_model,
                "role": role,
                "metric": metric_name,
                "value": metric_value,
                "n_rounds": len(role_df),
                "confidence_mean": role_df["judge_confidence"].mean(),
            })

    return pd.DataFrame(model_metrics)


def plot_category_comparison(df: pd.DataFrame, output_path: str):
    """Generate comparison visualizations across categories.

    Args:
        df: DataFrame with round data
        output_path: Path to save the plot
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Baseline Experiment: Model Category Comparison", fontsize=16, fontweight='bold')

    # Set style
    sns.set_palette("husl")

    # 1. Judge accuracy by category
    judge_df = df[df["test_role"] == "judge"]
    if len(judge_df) > 0:
        sns.barplot(
            data=judge_df,
            x="model_category",
            y="detection_correct",
            ax=axes[0, 0],
            estimator='mean',
            errorbar='ci'
        )
        axes[0, 0].set_title("Judge Detection Accuracy by Category")
        axes[0, 0].set_ylabel("Accuracy")
        axes[0, 0].set_xlabel("Model Category")
        axes[0, 0].axhline(1/3, color='red', linestyle='--', linewidth=1, label='Random Chance (33%)')
        axes[0, 0].legend()
        axes[0, 0].set_ylim(0, 1)

    # 2. Fibber evasion by category
    fibber_df = df[df["test_role"] == "storyteller"]
    if len(fibber_df) > 0:
        sns.barplot(
            data=fibber_df,
            x="model_category",
            y="fibber_evasion",
            ax=axes[0, 1],
            estimator='mean',
            errorbar='ci'
        )
        axes[0, 1].set_title("Fibber Evasion Rate by Category")
        axes[0, 1].set_ylabel("Evasion Rate")
        axes[0, 1].set_xlabel("Model Category")
        axes[0, 1].set_ylim(0, 1)

    # 3. Confidence distribution by category
    sns.boxplot(
        data=df,
        x="model_category",
        y="judge_confidence",
        ax=axes[1, 0]
    )
    axes[1, 0].set_title("Judge Confidence Distribution by Category")
    axes[1, 0].set_ylabel("Confidence (1-10)")
    axes[1, 0].set_xlabel("Model Category")
    axes[1, 0].set_ylim(1, 10)

    # 4. Per-model accuracy (top models only)
    model_metrics = calculate_model_metrics(df)
    judge_metrics = model_metrics[model_metrics["role"] == "judge"]

    if len(judge_metrics) > 0:
        # Sort by accuracy and take top 10
        top_models = judge_metrics.nlargest(min(10, len(judge_metrics)), "value")

        axes[1, 1].barh(top_models["model"], top_models["value"])
        axes[1, 1].set_xlabel("Judge Accuracy")
        axes[1, 1].set_title("Top Model Performance (Judge Role)")
        axes[1, 1].axvline(1/3, color='red', linestyle='--', linewidth=1)
        axes[1, 1].set_xlim(0, 1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved visualizations to: {output_path}")


def print_summary_report(df: pd.DataFrame, category_metrics: Dict[str, Dict[str, Any]]):
    """Print comprehensive summary report.

    Args:
        df: DataFrame with round data
        category_metrics: Category-level metrics
    """
    print("\n" + "=" * 70)
    print("BASELINE EXPERIMENT RESULTS SUMMARY")
    print("=" * 70)

    print(f"\nTotal Rounds: {len(df)}")
    print(f"Phases Included: {sorted(df['phase'].dropna().unique())}")
    print(f"Model Categories: {len(df['model_category'].unique())}")
    print(f"Unique Models Tested: {len(df['test_model'].unique())}")

    print("\n" + "-" * 70)
    print("PERFORMANCE BY MODEL CATEGORY")
    print("-" * 70)

    # Sort categories by judge accuracy for display
    sorted_categories = sorted(
        category_metrics.items(),
        key=lambda x: x[1]["judge_accuracy"] if x[1]["judge_accuracy"] is not None else 0,
        reverse=True
    )

    for category, metrics in sorted_categories:
        print(f"\n{category.upper()} MODELS:")

        if metrics["judge_accuracy"] is not None:
            print(f"  Judge Accuracy:  {metrics['judge_accuracy']:.1%} "
                  f"(n={metrics['n_judge_rounds']})")
        else:
            print(f"  Judge Accuracy:  N/A")

        if metrics["fibber_evasion"] is not None:
            print(f"  Fibber Evasion:  {metrics['fibber_evasion']:.1%} "
                  f"(n={metrics['n_fibber_rounds']})")
        else:
            print(f"  Fibber Evasion:  N/A")

        print(f"  Avg Confidence:  {metrics['confidence_mean']:.1f}/10 "
              f"(±{metrics['confidence_std']:.1f})")

    print("\n" + "-" * 70)
    print("TOP 5 MODELS (JUDGE ACCURACY)")
    print("-" * 70)

    model_metrics = calculate_model_metrics(df)
    judge_metrics = model_metrics[model_metrics["role"] == "judge"]

    if len(judge_metrics) > 0:
        top_5 = judge_metrics.nlargest(5, "value")

        for idx, row in top_5.iterrows():
            print(f"  {row['model']:<35} {row['value']:.1%} (n={row['n_rounds']})")

    print("\n" + "-" * 70)
    print("CONFIDENCE CALIBRATION")
    print("-" * 70)

    # Calculate accuracy by confidence level
    for conf_level in [1, 3, 5, 7, 10]:
        level_df = df[df["judge_confidence"] == conf_level]
        if len(level_df) > 0:
            accuracy = level_df["detection_correct"].mean()
            print(f"  Confidence {conf_level:2d}: {accuracy:.1%} accuracy (n={len(level_df)})")

    print("\n" + "=" * 70)


def export_to_csv(df: pd.DataFrame, output_path: str):
    """Export results to CSV for external analysis.

    Args:
        df: DataFrame with round data
        output_path: Path to save CSV
    """
    df.to_csv(output_path, index=False)
    print(f"\nExported raw data to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze baseline experiment results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "directories",
        nargs="+",
        help="Result directories to analyze"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output files (default: current directory)"
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip generating plots"
    )

    args = parser.parse_args()

    # Expand glob patterns if any
    directories = []
    for pattern in args.directories:
        path = Path(pattern)
        if path.exists() and path.is_dir():
            directories.append(str(path))
        else:
            # Try glob expansion
            matches = list(Path(".").glob(pattern))
            directories.extend([str(p) for p in matches if p.is_dir()])

    if not directories:
        print("Error: No valid directories found")
        sys.exit(1)

    print(f"Analyzing {len(directories)} directories...")
    for d in directories:
        print(f"  - {d}")

    try:
        # Load results
        df = load_combined_results(directories)

        # Calculate metrics
        category_metrics = calculate_category_metrics(df)

        # Print summary
        print_summary_report(df, category_metrics)

        # Generate visualizations
        if not args.no_plots:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            plot_path = output_dir / "baseline_comparison.png"
            plot_category_comparison(df, str(plot_path))

        # Export CSV
        csv_path = Path(args.output_dir) / "baseline_results.csv"
        export_to_csv(df, str(csv_path))

        print("\n✓ Analysis complete!")

    except Exception as e:
        print(f"\nError during analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
