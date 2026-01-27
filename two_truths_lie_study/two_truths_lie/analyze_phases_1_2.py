#!/usr/bin/env python3
"""
Comprehensive analysis of Phase 1 and Phase 2 results.

Shows absolute performance and relative comparisons across all models.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore


def analyze_phase(phase_name: str, results_dir: str):
    """Analyze a single phase and return statistics."""
    print(f"\n{'='*70}")
    print(f"{phase_name.upper()} RESULTS")
    print(f"{'='*70}\n")

    store = ResultStore(results_dir)
    round_ids = store.list_rounds()

    if not round_ids:
        print(f"❌ No results found in {results_dir}")
        return None

    print(f"Total rounds: {len(round_ids)}\n")

    # Organize by model and role
    model_stats = defaultdict(lambda: {
        'judge': {'total': 0, 'correct': 0, 'confidences': []},
        'storyteller': {'total': 0, 'correct': 0, 'confidences': []},
        'overall': {'total': 0, 'correct': 0}
    })

    for round_id in round_ids:
        try:
            result = store.get_round(round_id)
            condition_id = result.setup.condition_id or "unknown"

            # Extract model and role from condition_id
            # Format: "phase1_older_gpt-3.5-turbo_judge" or "phase2_small_model_role"
            parts = condition_id.split('_')
            if len(parts) >= 4:
                model_name = '_'.join(parts[2:-1])  # Everything between phase and role
                role = parts[-1]
            else:
                continue

            # Record stats
            correct = result.outcome.detection_correct
            confidence = result.verdict.confidence if result.verdict else 0

            model_stats[model_name][role]['total'] += 1
            model_stats[model_name][role]['confidences'].append(confidence)
            model_stats[model_name]['overall']['total'] += 1

            if correct:
                model_stats[model_name][role]['correct'] += 1
                model_stats[model_name]['overall']['correct'] += 1

        except Exception as e:
            print(f"Warning: Error processing {round_id}: {e}")
            continue

    # Calculate and display statistics
    results = {}

    for model_name in sorted(model_stats.keys()):
        stats = model_stats[model_name]

        # Calculate accuracies
        judge_acc = (stats['judge']['correct'] / stats['judge']['total'] * 100) if stats['judge']['total'] > 0 else 0
        story_acc = (stats['storyteller']['correct'] / stats['storyteller']['total'] * 100) if stats['storyteller']['total'] > 0 else 0
        overall_acc = (stats['overall']['correct'] / stats['overall']['total'] * 100) if stats['overall']['total'] > 0 else 0

        # Calculate average confidences
        judge_conf = sum(stats['judge']['confidences']) / len(stats['judge']['confidences']) if stats['judge']['confidences'] else 0
        story_conf = sum(stats['storyteller']['confidences']) / len(stats['storyteller']['confidences']) if stats['storyteller']['confidences'] else 0

        results[model_name] = {
            'judge_accuracy': judge_acc,
            'storyteller_accuracy': story_acc,
            'overall_accuracy': overall_acc,
            'judge_confidence': judge_conf,
            'storyteller_confidence': story_conf,
            'judge_rounds': stats['judge']['total'],
            'storyteller_rounds': stats['storyteller']['total'],
            'total_rounds': stats['overall']['total']
        }

        print(f"{model_name}:")
        print(f"  Total rounds: {stats['overall']['total']}")
        print(f"  Judge:        {stats['judge']['total']} rounds, {judge_acc:.1f}% accuracy, {judge_conf:.1f} avg confidence")
        print(f"  Storyteller:  {stats['storyteller']['total']} rounds, {story_acc:.1f}% accuracy, {story_conf:.1f} avg confidence")
        print(f"  Overall:      {overall_acc:.1f}% accuracy")
        print()

    return results


def compare_models(phase1_results, phase2_results):
    """Compare models across phases."""
    print(f"\n{'='*70}")
    print("CROSS-PHASE COMPARISON")
    print(f"{'='*70}\n")

    # Combine all models
    all_models = {}

    if phase1_results:
        for model, stats in phase1_results.items():
            all_models[f"[P1] {model}"] = stats

    if phase2_results:
        for model, stats in phase2_results.items():
            all_models[f"[P2] {model}"] = stats

    # Sort by overall accuracy
    sorted_models = sorted(all_models.items(), key=lambda x: x[1]['overall_accuracy'], reverse=True)

    print("OVERALL ACCURACY RANKING:")
    print("-" * 70)
    for i, (model, stats) in enumerate(sorted_models, 1):
        print(f"{i:2d}. {model:50s} {stats['overall_accuracy']:5.1f}%")

    print("\n\nJUDGE PERFORMANCE RANKING:")
    print("-" * 70)
    sorted_judge = sorted(all_models.items(), key=lambda x: x[1]['judge_accuracy'], reverse=True)
    for i, (model, stats) in enumerate(sorted_judge, 1):
        if stats['judge_rounds'] > 0:
            print(f"{i:2d}. {model:50s} {stats['judge_accuracy']:5.1f}% ({stats['judge_rounds']} rounds)")

    print("\n\nSTORYTELLER PERFORMANCE RANKING:")
    print("-" * 70)
    sorted_story = sorted(all_models.items(), key=lambda x: x[1]['storyteller_accuracy'], reverse=True)
    for i, (model, stats) in enumerate(sorted_story, 1):
        if stats['storyteller_rounds'] > 0:
            print(f"{i:2d}. {model:50s} {stats['storyteller_accuracy']:5.1f}% ({stats['storyteller_rounds']} rounds)")


def summary_statistics(phase1_results, phase2_results):
    """Show summary statistics."""
    print(f"\n{'='*70}")
    print("SUMMARY STATISTICS")
    print(f"{'='*70}\n")

    all_results = {}
    if phase1_results:
        all_results.update({f"[P1] {k}": v for k, v in phase1_results.items()})
    if phase2_results:
        all_results.update({f"[P2] {k}": v for k, v in phase2_results.items()})

    if not all_results:
        print("No results available")
        return

    # Calculate aggregate stats
    judge_accs = [v['judge_accuracy'] for v in all_results.values() if v['judge_rounds'] > 0]
    story_accs = [v['storyteller_accuracy'] for v in all_results.values() if v['storyteller_rounds'] > 0]
    overall_accs = [v['overall_accuracy'] for v in all_results.values() if v['total_rounds'] > 0]

    print(f"Models tested: {len(all_results)}")
    print(f"\nOverall Accuracy:")
    print(f"  Mean:    {sum(overall_accs)/len(overall_accs):.1f}%")
    print(f"  Median:  {sorted(overall_accs)[len(overall_accs)//2]:.1f}%")
    print(f"  Range:   {min(overall_accs):.1f}% - {max(overall_accs):.1f}%")

    print(f"\nJudge Role:")
    print(f"  Mean accuracy:    {sum(judge_accs)/len(judge_accs):.1f}%")
    print(f"  Best:  {max(judge_accs):.1f}%")
    print(f"  Worst: {min(judge_accs):.1f}%")

    print(f"\nStoryteller Role:")
    print(f"  Mean accuracy:    {sum(story_accs)/len(story_accs):.1f}%")
    print(f"  Best:  {max(story_accs):.1f}%")
    print(f"  Worst: {min(story_accs):.1f}%")

    # Best and worst performers
    print(f"\n\nBEST PERFORMERS:")
    print("-" * 70)
    best_overall = max(all_results.items(), key=lambda x: x[1]['overall_accuracy'])
    print(f"Overall:     {best_overall[0]:50s} {best_overall[1]['overall_accuracy']:.1f}%")

    best_judge = max(all_results.items(), key=lambda x: x[1]['judge_accuracy'] if x[1]['judge_rounds'] > 0 else 0)
    print(f"Judge:       {best_judge[0]:50s} {best_judge[1]['judge_accuracy']:.1f}%")

    best_story = max(all_results.items(), key=lambda x: x[1]['storyteller_accuracy'] if x[1]['storyteller_rounds'] > 0 else 0)
    print(f"Storyteller: {best_story[0]:50s} {best_story[1]['storyteller_accuracy']:.1f}%")


def main():
    """Main analysis function."""
    print("\n" + "="*70)
    print("COMPREHENSIVE ANALYSIS: PHASES 1 & 2")
    print("="*70)

    # Analyze Phase 1
    phase1_results = analyze_phase("Phase 1: Older Models", "results/phase1_older")

    # Analyze Phase 2
    phase2_results = analyze_phase("Phase 2: Small/Fast Models", "results/phase2_small")

    # Compare across phases
    compare_models(phase1_results, phase2_results)

    # Summary statistics
    summary_statistics(phase1_results, phase2_results)

    print("\n" + "="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
