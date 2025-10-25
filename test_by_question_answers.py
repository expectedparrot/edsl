"""Test script for enhanced QuestionAnalysis with terminal visualizations.

This script demonstrates the new rich-formatted __repr__ for QuestionAnalysis
which includes:
- Question details in formatted tables
- Answer statistics
- Terminal-based visualizations
- Available methods and outputs
"""

from edsl import Results

print()
print("=" * 100)
print(" " * 30 + "Enhanced QuestionAnalysis Demo")
print("=" * 100)
print()
print("This demo shows the new rich-formatted output when you analyze a question.")
print("The QuestionAnalysis object now displays:")
print("  • Question details (name, type, text, options)")
print("  • Answer statistics (counts, means, distributions)")
print("  • Terminal visualization (ASCII charts)")
print("  • Available methods and outputs")
print()
print("=" * 100)
print()

# Load example results
print("Loading example results...")
results = Results.example()

print(f"Found {len(results.question_names)} questions:")
for i, qname in enumerate(results.question_names, 1):
    print(f"  {i}. {qname}")
print()

print("=" * 100)
print("EXAMPLE 1: Analyzing 'how_feeling' question")
print("=" * 100)
print()
print("Code: qa = results.analyze('how_feeling')")
print("      print(qa)")
print()

qa = results.analyze('how_feeling')
print(qa)

print()
print("=" * 100)
print("EXAMPLE 2: Analyzing second question")
print("=" * 100)
print()

if len(results.question_names) > 1:
    second_q = list(results.question_names)[1]
    print(f"Code: qa2 = results.analyze('{second_q}')")
    print("      print(qa2)")
    print()

    qa2 = results.analyze(second_q)
    print(qa2)

print()
print("=" * 100)
print("EXAMPLE 3: Accessing specific outputs")
print("=" * 100)
print()
print("Once you have a QuestionAnalysis object, you can access specific outputs:")
print()
print("Code: qa.bar_chart_output")
print("Result: Returns an OutputWrapper with the chart")
print()
print("Code: qa.bar_chart_output.terminal_chart()")
print("Result: Shows full terminal visualization with more details")
print()

print("Let's try it:")
print()
qa.bar_chart_output.terminal_chart()

print()
print("=" * 100)
print("EXAMPLE 4: Listing available outputs programmatically")
print("=" * 100)
print()
print("Code: qa.list_outputs()")
print()
qa.list_outputs()

print()
print("=" * 100)
print("EXAMPLE 5: Accessing question metadata")
print("=" * 100)
print()
print(f"Code: qa.question_names")
print(f"Result: {qa.question_names}")
print()
print(f"Code: len(qa.outputs)")
print(f"Result: {len(qa.outputs)} outputs available")
print()

print()
print("=" * 100)
print("Key Features of the Enhanced QuestionAnalysis")
print("=" * 100)
print()
print("1. AUTOMATIC RICH FORMATTING")
print("   - Simply print() or display the QuestionAnalysis object")
print("   - No need to call special methods")
print()
print("2. QUESTION TYPE-SPECIFIC STATISTICS")
print("   - Multiple choice: Shows unique values, most common")
print("   - Numerical: Shows mean, median, std dev, range")
print("   - Checkbox: Shows total selections, avg per respondent")
print("   - Free text: Shows avg length, length range")
print()
print("3. EMBEDDED TERMINAL VISUALIZATIONS")
print("   - Bar charts for categorical data")
print("   - Histograms for numerical data")
print("   - Automatically adapts to question type")
print()
print("4. METHOD DISCOVERY")
print("   - Lists all available outputs and methods")
print("   - Shows helpful descriptions")
print("   - Includes usage tips")
print()
print("5. WORKS IN ANY TERMINAL")
print("   - SSH sessions")
print("   - Jupyter notebooks")
print("   - Scripts and automation")
print("   - CI/CD pipelines")
print()
print("=" * 100)
print("Requirements")
print("=" * 100)
print()
print("• termplotlib: pip install termplotlib")
print("• rich: pip install rich (usually already installed with edsl)")
print()
print("=" * 100)
