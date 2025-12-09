"""Demo script for AnswersCompare class.

This script demonstrates how to use AnswersCompare to compute various
distance metrics between answer distributions from different survey populations.
"""

from edsl import Results
from edsl.comparisons import AnswersCompare

print()
print("=" * 80)
print(" " * 25 + "AnswersCompare Demo")
print("=" * 80)
print()
print("AnswersCompare computes statistical distance metrics between two")
print("QuestionAnalysis objects to measure how different their answer")
print("distributions are.")
print()
print("Available metrics:")
print("  • KL Divergence (asymmetric)")
print("  • Jensen-Shannon Divergence (symmetric)")
print("  • Hellinger Distance (metric)")
print("  • Total Variation Distance (L1)")
print("  • Chi-Squared")
print("  • Bhattacharyya Distance")
print()

# Load example results
print("=" * 80)
print("EXAMPLE 1: Comparing Full vs Subset Distributions")
print("=" * 80)
print()

results = Results.example()
print(f"Loaded {len(results)} survey results")
print(f"Question: {list(results.question_names)[0]}")
print()

# Analyze full results
qa_full = results.analyze('how_feeling')
print("Full dataset analysis:")
print(qa_full)
print()

# Create subset for comparison
results_subset = results[:2]
qa_subset = results_subset.analyze('how_feeling')
print(f"Subset dataset ({len(results_subset)} results):")
print(qa_subset)
print()

# Create comparison
print("=" * 80)
print("Creating AnswersCompare Object")
print("=" * 80)
print()
print("Code: compare = AnswersCompare(qa_full, qa_subset)")
compare = AnswersCompare(qa_full, qa_subset)
print(f"Created: {compare}")
print()

# Show summary with all metrics
print("=" * 80)
print("All Distance Metrics")
print("=" * 80)
print()
print("Code: compare.summary()")
print()
print(compare.summary())

# Access individual metrics
print("=" * 80)
print("EXAMPLE 2: Accessing Individual Metrics")
print("=" * 80)
print()

print("Code:")
print("  kl = compare.kl_divergence()")
print("  js = compare.jensen_shannon_divergence()")
print("  hellinger = compare.hellinger_distance()")
print()

kl = compare.kl_divergence()
js = compare.jensen_shannon_divergence()
hellinger = compare.hellinger_distance()

print(f"KL Divergence (qa1 → qa2): {kl:.4f}")
print(f"KL Divergence (qa2 → qa1): {compare.kl_divergence(reverse=True):.4f}")
print(f"Jensen-Shannon Divergence: {js:.4f}")
print(f"Hellinger Distance: {hellinger:.4f}")
print()

# Get all metrics as dict
print("=" * 80)
print("EXAMPLE 3: Get All Metrics as Dictionary")
print("=" * 80)
print()

print("Code: metrics = compare.all_metrics()")
metrics = compare.all_metrics()
print()
print("Metrics dictionary:")
for name, value in metrics.items():
    print(f"  {name:.<40} {value:.4f}")
print()

# Custom metric
print("=" * 80)
print("EXAMPLE 4: Custom Distance Metric")
print("=" * 80)
print()

print("You can define custom distance functions:")
print()
print("Code:")
print("  def max_difference(p, q):")
print("      return max(abs(p[k] - q[k]) for k in p.keys())")
print("  custom = compare.custom_metric(max_difference)")
print()

def max_difference(p, q):
    """Maximum absolute difference between probabilities."""
    return max(abs(p[k] - q[k]) for k in p.keys())

custom = compare.custom_metric(max_difference)
print(f"Custom metric (max difference): {custom:.4f}")
print()

# Interpretation guide
print("=" * 80)
print("Interpretation Guide")
print("=" * 80)
print()

print("Jensen-Shannon Divergence (recommended for general use):")
print("  0.00 - 0.05:  Very similar distributions")
print("  0.05 - 0.15:  Somewhat different")
print("  0.15 - 0.30:  Quite different")
print("  > 0.30:       Very different")
print()

print("Total Variation Distance:")
print("  0.00 - 0.10:  Very similar")
print("  0.10 - 0.25:  Somewhat different")
print("  0.25 - 0.50:  Quite different")
print("  > 0.50:       Very different")
print()

print("Hellinger Distance:")
print("  0.00 - 0.15:  Very similar")
print("  0.15 - 0.35:  Somewhat different")
print("  0.35 - 0.60:  Quite different")
print("  > 0.60:       Very different")
print()

# Use cases
print("=" * 80)
print("Common Use Cases")
print("=" * 80)
print()

print("1. A/B Testing")
print("   Compare control vs treatment group responses")
print()

print("2. Temporal Analysis")
print("   Track how answer distributions change over time")
print()

print("3. Demographic Comparison")
print("   Compare response patterns across different groups")
print()

print("4. Quality Control")
print("   Detect anomalous or suspicious response patterns")
print()

print("5. Intervention Effectiveness")
print("   Measure before/after distribution shifts")
print()

print("6. Model Comparison")
print("   Compare how different AI models respond to questions")
print()

print("=" * 80)
print("API Quick Reference")
print("=" * 80)
print()

print("from edsl.comparisons import AnswersCompare")
print()
print("# Create comparison")
print("compare = AnswersCompare(qa1, qa2)")
print()
print("# Get all metrics")
print("compare.summary()              # Rich formatted table")
print("compare.all_metrics()          # Dictionary of all metrics")
print()
print("# Individual metrics")
print("compare.kl_divergence()        # KL divergence (qa1 → qa2)")
print("compare.kl_divergence(reverse=True)  # KL divergence (qa2 → qa1)")
print("compare.jensen_shannon_divergence()  # Symmetric JS divergence")
print("compare.hellinger_distance()         # Hellinger distance")
print("compare.total_variation_distance()   # Total variation")
print("compare.chi_squared()                # Chi-squared statistic")
print("compare.bhattacharyya_distance()     # Bhattacharyya distance")
print()
print("# Custom metric")
print("compare.custom_metric(my_distance_fn)")
print()

print("=" * 80)
