#!/usr/bin/env python3
"""
Deep dive into DeepSeek's performance to understand the perfect 100% accuracy.

Analyzes:
- Response patterns
- Confidence calibration
- Reasoning quality
- Comparison with other models
"""

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from src.storage import ResultStore


def analyze_deepseek_verdicts():
    """Analyze DeepSeek's verdicts in detail."""
    print("\n" + "="*70)
    print("DEEPSEEK INVESTIGATION: WHY 100% ACCURACY?")
    print("="*70 + "\n")

    store = ResultStore("results/phase2_small")

    # Find DeepSeek judge rounds
    deepseek_rounds = []
    for round_id in store.list_rounds():
        result = store.get_round(round_id)
        if "deepseek-chat_judge" in (result.setup.condition_id or ""):
            deepseek_rounds.append((round_id, result))

    print(f"Analyzing {len(deepseek_rounds)} DeepSeek judge rounds\n")

    if not deepseek_rounds:
        print("No DeepSeek judge rounds found")
        return

    # Analyze patterns
    accused_counts = Counter()
    confidence_scores = []
    reasoning_lengths = []

    print("ROUND-BY-ROUND ANALYSIS:")
    print("-" * 70)

    for i, (round_id, result) in enumerate(deepseek_rounds, 1):
        # Find the liar from storytellers
        actual_liar = next(s.id for s in result.setup.storytellers if s.role == "fibber")
        accused = result.verdict.accused_id
        confidence = result.verdict.confidence
        reasoning = result.verdict.reasoning
        correct = result.outcome.detection_correct

        accused_counts[accused] += 1
        confidence_scores.append(confidence)
        reasoning_lengths.append(len(reasoning.split()))

        status = "✅" if correct else "❌"
        print(f"Round {i:2d}: Liar={actual_liar}, Accused={accused}, "
              f"Confidence={confidence}, Correct={status}")

        # Show reasoning for first 3 rounds
        if i <= 3:
            print(f"  Reasoning: {reasoning[:150]}...")
            print()

    # Statistics
    print("\n" + "="*70)
    print("DEEPSEEK PATTERNS:")
    print("="*70 + "\n")

    print("Accused Distribution:")
    for accused, count in accused_counts.most_common():
        print(f"  Storyteller {accused}: {count} times ({count/len(deepseek_rounds)*100:.1f}%)")

    print(f"\nConfidence Statistics:")
    print(f"  Mean: {sum(confidence_scores)/len(confidence_scores):.1f}")
    print(f"  Min:  {min(confidence_scores)}")
    print(f"  Max:  {max(confidence_scores)}")
    print(f"  Range: {max(confidence_scores) - min(confidence_scores)}")

    print(f"\nReasoning Length (words):")
    print(f"  Mean: {sum(reasoning_lengths)/len(reasoning_lengths):.1f}")
    print(f"  Min:  {min(reasoning_lengths)}")
    print(f"  Max:  {max(reasoning_lengths)}")

    # Check if there's a bias
    expected_distribution = len(deepseek_rounds) / 3  # Should be ~10 each for A, B, C
    print(f"\nBias Analysis:")
    print(f"  Expected per storyteller: {expected_distribution:.1f}")
    for accused, count in accused_counts.items():
        deviation = abs(count - expected_distribution)
        print(f"  {accused}: {count} (deviation: {deviation:.1f})")

    # Compare with other models
    print("\n" + "="*70)
    print("COMPARISON WITH OTHER MODELS:")
    print("="*70 + "\n")

    compare_models = [
        ("claude-3-7-sonnet-20250219_judge", "Claude 3.7 Sonnet"),
        ("gpt-4o-mini_judge", "GPT-4o-mini"),
        ("claude-3-5-haiku-20241022_judge", "Claude 3.5 Haiku"),
    ]

    for condition_pattern, model_name in compare_models:
        model_rounds = []
        for round_id in store.list_rounds():
            result = store.get_round(round_id)
            if condition_pattern in (result.setup.condition_id or ""):
                model_rounds.append(result)

        if model_rounds:
            correct = sum(1 for r in model_rounds if r.outcome.detection_correct)
            avg_conf = sum(r.verdict.confidence for r in model_rounds) / len(model_rounds)
            accuracy = correct / len(model_rounds) * 100

            # Accused distribution
            accused = Counter(r.verdict.accused_id for r in model_rounds)

            print(f"{model_name}:")
            print(f"  Accuracy: {accuracy:.1f}% ({correct}/{len(model_rounds)})")
            print(f"  Avg confidence: {avg_conf:.1f}")
            print(f"  Accused dist: {dict(accused)}")
            print()

    return deepseek_rounds


def compare_storyteller_performance():
    """Compare DeepSeek as storyteller vs other models."""
    print("\n" + "="*70)
    print("DEEPSEEK AS STORYTELLER:")
    print("="*70 + "\n")

    store = ResultStore("results/phase2_small")

    # Find rounds where DeepSeek was storyteller
    deepseek_story_rounds = []
    for round_id in store.list_rounds():
        result = store.get_round(round_id)
        if "deepseek-chat_storyteller" in (result.setup.condition_id or ""):
            deepseek_story_rounds.append(result)

    if not deepseek_story_rounds:
        print("No DeepSeek storyteller rounds found")
        return

    correct = sum(1 for r in deepseek_story_rounds if r.outcome.detection_correct)
    fooled = len(deepseek_story_rounds) - correct

    print(f"Total rounds: {len(deepseek_story_rounds)}")
    print(f"Judge detected lie: {correct} times ({correct/len(deepseek_story_rounds)*100:.1f}%)")
    print(f"DeepSeek fooled judge: {fooled} times ({fooled/len(deepseek_story_rounds)*100:.1f}%)")

    # Show examples of DeepSeek's lies
    print("\n" + "="*70)
    print("DEEPSEEK'S LYING STRATEGY (sample stories):")
    print("="*70 + "\n")

    liar_rounds = deepseek_story_rounds[:3]

    for i, result in enumerate(liar_rounds, 1):
        liar_id = next(s.id for s in result.setup.storytellers if s.role == "fibber")
        liar_story = next(s for s in result.stories if s.storyteller_id == liar_id)

        print(f"Example {i}: Storyteller {liar_id} (Liar)")
        print(f"Story: {liar_story.content[:300]}...")
        print(f"Detected: {'Yes' if result.outcome.detection_correct else 'No'}")
        print()


def main():
    """Run investigation."""
    deepseek_rounds = analyze_deepseek_verdicts()
    compare_storyteller_performance()

    print("\n" + "="*70)
    print("HYPOTHESIS:")
    print("="*70 + "\n")

    if deepseek_rounds and len(deepseek_rounds) == 30:
        correct = sum(1 for _, r in deepseek_rounds if r.outcome.detection_correct)
        if correct == 30:
            print("DeepSeek achieved 30/30 perfect accuracy. Possible explanations:\n")
            print("1. STRONG REASONING: DeepSeek models are known for reasoning ability")
            print("   - May have superior logical analysis")
            print("   - Better at detecting inconsistencies\n")

            print("2. TASK FAMILIARITY: May have seen similar tasks in training")
            print("   - Chinese training data might include deception games")
            print("   - Recent model = more diverse training data\n")

            print("3. STATISTICAL FLUKE: 30 rounds is small sample")
            print("   - Probability of 30/30 by chance: ~0.000015% (if 70% base rate)")
            print("   - But with good reasoning, not pure chance\n")

            print("4. OVERCONFIDENCE/OVERFITTING: Might be too certain")
            print("   - Check if confidence scores are calibrated")
            print("   - Compare reasoning quality vs other models\n")

            print("NEXT STEPS:")
            print("- Examine actual reasoning text quality")
            print("- Check if DeepSeek uses different reasoning patterns")
            print("- Run more rounds to validate (Phase 3 won't have DeepSeek though)")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    sys.exit(main())
