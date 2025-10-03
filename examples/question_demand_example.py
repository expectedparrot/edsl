"""
QuestionDemand: A new question type for collecting demand curves.

This example demonstrates how to use QuestionDemand to ask language models
about their purchasing behavior at different price points.
"""

from edsl.questions import QuestionDemand

print("=" * 80)
print("QuestionDemand - Demand Curve Question Type")
print("=" * 80)
print()

# Example 1: Basic coffee demand
print("Example 1: Basic Coffee Demand")
print("-" * 80)
q1 = QuestionDemand(
    question_name="coffee_demand",
    question_text="How many cups of coffee would you buy per week at each price?",
    prices=[1.0, 2.0, 3.0, 4.0, 5.0]
)

print(f"Question: {q1.question_text}")
print(f"Prices: {q1.prices}")
print()

# Simulate an answer
answer = q1._simulate_answer()
print(f"Simulated answer: {answer['answer']}")
print()

# Translate to readable format
translated = q1._translate_answer_code_to_answer(answer['answer'], {})
print("Demand curve:")
for item in translated:
    for price, quantity in item.items():
        print(f"  {price}: {quantity} cups/week")
print()
print()

# Example 2: Apple pricing at a farmers market
print("Example 2: Farmers Market Apple Demand")
print("-" * 80)
q2 = QuestionDemand(
    question_name="apple_demand",
    question_text="You're at a farmers market. How many apples would you buy at each price?",
    prices=[0.50, 1.00, 1.50, 2.00, 2.50, 3.00]
)

print(f"Question: {q2.question_text}")
print(f"Price range: ${min(q2.prices):.2f} - ${max(q2.prices):.2f}")
print(f"Number of price points: {len(q2.prices)}")
print()
print()

# Example 3: Validation examples
print("Example 3: Validation")
print("-" * 80)
q3 = QuestionDemand.example()

# Valid answer
valid_answer = {"answer": [10, 8, 6, 4]}
try:
    validated = q3._validate_answer(valid_answer)
    print(f"✓ Valid answer accepted: {validated['answer']}")
except Exception as e:
    print(f"✗ Error: {e}")

# Invalid: negative quantity
invalid_answer = {"answer": [10, -5, 6, 4]}
try:
    validated = q3._validate_answer(invalid_answer)
    print(f"✗ Should have rejected: {validated['answer']}")
except Exception as e:
    print(f"✓ Correctly rejected negative quantity")

# Invalid: wrong number of quantities
invalid_answer2 = {"answer": [10, 8, 6]}
try:
    validated = q3._validate_answer(invalid_answer2)
    print(f"✗ Should have rejected: {validated['answer']}")
except Exception as e:
    print(f"✓ Correctly rejected wrong quantity count")

print()
print()

# Example 4: Using with scenarios (conceptual)
print("Example 4: Using with Different Scenarios")
print("-" * 80)
print("""
You can use QuestionDemand with scenarios to test different contexts:

from edsl import QuestionDemand, ScenarioList

q = QuestionDemand(
    question_name="product_demand",
    question_text="How many units of {{ product }} would you buy at each price?",
    prices=[1.0, 2.0, 3.0, 4.0, 5.0]
)

scenarios = ScenarioList([
    Scenario({"product": "coffee"}),
    Scenario({"product": "apples"}),
    Scenario({"product": "notebooks"})
])

# This would ask about demand curves for different products
# results = q.by(scenarios).run()
""")
print()

# Example 5: Serialization
print("Example 5: Serialization")
print("-" * 80)
serialized = q1.to_dict()
print("Serialized question:")
for key in ['question_name', 'question_text', 'question_type', 'prices']:
    print(f"  {key}: {serialized[key]}")
print()

from edsl.questions import QuestionBase
deserialized = QuestionBase.from_dict(serialized)
print(f"Successfully deserialized: {deserialized.question_name}")
print()
print()

# Summary
print("=" * 80)
print("Summary")
print("=" * 80)
print("""
QuestionDemand is designed for economic research and understanding
price sensitivity. Key features:

✓ Specify multiple price points
✓ Collect quantities demanded at each price
✓ Validate non-negative quantities
✓ Automatic formatting as demand curves
✓ Full integration with EDSL scenarios and agents

Usage:
    from edsl import QuestionDemand

    q = QuestionDemand(
        question_name="my_demand",
        question_text="How many would you buy at each price?",
        prices=[1.0, 2.0, 3.0, 4.0, 5.0]
    )

    # Run with a model
    # result = q.by(Model()).run()
""")
