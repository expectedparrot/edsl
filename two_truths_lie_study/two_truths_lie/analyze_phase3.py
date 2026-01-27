#!/usr/bin/env python3
"""
Comprehensive Phase 3 analysis with comparison to Phases 1 and 2.
"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore


def analyze_phase3():
    """Analyze Phase 3 flagship models."""
    print("\n" + "="*70)
    print("PHASE 3: FLAGSHIP MODELS - FINAL RESULTS")
    print("="*70 + "\n")

    store = ResultStore("results/phase3_flagship")
    round_ids = store.list_rounds()

    print(f"Total rounds completed: {len(round_ids)}/240 ({len(round_ids)/240*100:.1f}%)")
    print(f"Failed rounds: {240 - len(round_ids)}\n")

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

            # Extract model and role
            parts = condition_id.split('_')
            if len(parts) >= 4:
                model_name = '_'.join(parts[2:-1])
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

    # Display results
    print("MODEL PERFORMANCE:")
    print("-" * 70)

    results = {}
    for model_name in sorted(model_stats.keys()):
        stats = model_stats[model_name]

        judge_acc = (stats['judge']['correct'] / stats['judge']['total'] * 100) if stats['judge']['total'] > 0 else 0
        story_acc = (stats['storyteller']['correct'] / stats['storyteller']['total'] * 100) if stats['storyteller']['total'] > 0 else 0
        overall_acc = (stats['overall']['correct'] / stats['overall']['total'] * 100) if stats['overall']['total'] > 0 else 0

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

        print(f"\n{model_name}:")
        print(f"  Total rounds: {stats['overall']['total']}/60 ({stats['overall']['total']/60*100:.0f}%)")
        print(f"  Judge:        {stats['judge']['total']}/30, {judge_acc:.1f}% accuracy, {judge_conf:.1f} avg confidence")
        print(f"  Storyteller:  {stats['storyteller']['total']}/30, {story_acc:.1f}% accuracy, {story_conf:.1f} avg confidence")
        print(f"  Overall:      {overall_acc:.1f}% accuracy")

    return results


def compare_all_phases():
    """Compare performance across all three phases."""
    print("\n\n" + "="*70)
    print("CROSS-PHASE COMPARISON: ALL MODELS")
    print("="*70 + "\n")

    # Collect all models from all phases
    all_models = {}

    # Phase 1
    try:
        store1 = ResultStore("results/phase1_older")
        for round_id in store1.list_rounds():
            result = store1.get_round(round_id)
            condition_id = result.setup.condition_id or ""
            if "phase1" in condition_id:
                parts = condition_id.split('_')
                if len(parts) >= 4:
                    model = '_'.join(parts[2:-1])
                    role = parts[-1]

                    key = f"[P1] {model}"
                    if key not in all_models:
                        all_models[key] = {'judge': [], 'storyteller': []}
                    all_models[key][role].append(result.outcome.detection_correct)
    except:
        pass

    # Phase 2
    try:
        store2 = ResultStore("results/phase2_small")
        for round_id in store2.list_rounds():
            result = store2.get_round(round_id)
            condition_id = result.setup.condition_id or ""
            if "phase2" in condition_id:
                parts = condition_id.split('_')
                if len(parts) >= 4:
                    model = '_'.join(parts[2:-1])
                    role = parts[-1]

                    key = f"[P2] {model}"
                    if key not in all_models:
                        all_models[key] = {'judge': [], 'storyteller': []}
                    all_models[key][role].append(result.outcome.detection_correct)
    except:
        pass

    # Phase 3
    try:
        store3 = ResultStore("results/phase3_flagship")
        for round_id in store3.list_rounds():
            result = store3.get_round(round_id)
            condition_id = result.setup.condition_id or ""
            if "phase3" in condition_id:
                parts = condition_id.split('_')
                if len(parts) >= 4:
                    model = '_'.join(parts[2:-1])
                    role = parts[-1]

                    key = f"[P3] {model}"
                    if key not in all_models:
                        all_models[key] = {'judge': [], 'storyteller': []}
                    all_models[key][role].append(result.outcome.detection_correct)
    except:
        pass

    # Calculate accuracies
    model_accs = {}
    for model, roles in all_models.items():
        judge_acc = (sum(roles['judge']) / len(roles['judge']) * 100) if roles['judge'] else 0
        story_acc = (sum(roles['storyteller']) / len(roles['storyteller']) * 100) if roles['storyteller'] else 0
        overall = roles['judge'] + roles['storyteller']
        overall_acc = (sum(overall) / len(overall) * 100) if overall else 0

        model_accs[model] = {
            'overall': overall_acc,
            'judge': judge_acc,
            'storyteller': story_acc,
            'rounds': len(overall)
        }

    # Sort by overall accuracy
    sorted_models = sorted(model_accs.items(), key=lambda x: x[1]['overall'], reverse=True)

    print("OVERALL ACCURACY RANKING (ALL PHASES):")
    print("-" * 70)
    for i, (model, stats) in enumerate(sorted_models, 1):
        print(f"{i:2d}. {model:55s} {stats['overall']:5.1f}% ({stats['rounds']} rounds)")

    print("\n\nTOP 5 JUDGE PERFORMERS:")
    print("-" * 70)
    sorted_judge = sorted(model_accs.items(), key=lambda x: x[1]['judge'], reverse=True)[:5]
    for i, (model, stats) in enumerate(sorted_judge, 1):
        print(f"{i}. {model:55s} {stats['judge']:5.1f}%")

    print("\n\nTOP 5 STORYTELLER PERFORMERS:")
    print("-" * 70)
    sorted_story = sorted(model_accs.items(), key=lambda x: x[1]['storyteller'], reverse=True)[:5]
    for i, (model, stats) in enumerate(sorted_story, 1):
        print(f"{i}. {model:55s} {stats['storyteller']:5.1f}%")


def main():
    """Run complete analysis."""
    phase3_results = analyze_phase3()
    compare_all_phases()

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
