"""Demo script for terminal_chart() functionality.

This script demonstrates how to use the new terminal_chart() method
to display ASCII-based visualizations in the terminal.
"""

from edsl import Results

print("=" * 70)
print("Terminal Chart Demo")
print("=" * 70)
print()
print("The terminal_chart() method creates ASCII visualizations that can")
print("be displayed in a terminal, which is useful for:")
print("  - Scripts and automation")
print("  - SSH sessions")
print("  - Environments without graphical display")
print("  - Quick data exploration")
print()
print("=" * 70)
print()

# Load example results
results = Results.example()

print("Available questions in example results:")
for i, qname in enumerate(results.question_names, 1):
    print(f"  {i}. {qname}")
print()

# Analyze the first question
print("Let's analyze the 'how_feeling' question:")
print()

analysis = results.analyze('how_feeling')

print("Available outputs for this analysis:")
analysis.list_outputs()
print()

print("Now let's generate a terminal visualization:")
print()

# Show the terminal chart
analysis.bar_chart_output.terminal_chart()

print()
print("=" * 70)
print("More Examples")
print("=" * 70)
print()

# If there's another question, show that too
if len(results.question_names) > 1:
    second_q = list(results.question_names)[1]
    print(f"Let's also look at '{second_q}':")
    print()

    analysis2 = results.analyze(second_q)
    analysis2.bar_chart_output.terminal_chart()

print()
print("=" * 70)
print("Usage Tips")
print("=" * 70)
print()
print("1. Access via analyze():")
print("   results.analyze('question_name').bar_chart_output.terminal_chart()")
print()
print("2. The method automatically adapts to question type:")
print("   - Multiple choice: Bar chart of frequencies")
print("   - Numerical: Histogram with statistics")
print("   - Checkbox: Selection frequency chart")
print("   - Free text: Response length distribution")
print()
print("3. Works with all question types in Results")
print()
print("4. Requires termplotlib: pip install termplotlib")
print()
print("=" * 70)
