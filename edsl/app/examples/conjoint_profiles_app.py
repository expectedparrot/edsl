import textwrap
from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionNumerical, QuestionYesNo, QuestionFreeText
from edsl.agents import Agent

# 1. Initial Survey - Collect profile generation parameters
initial_survey = Survey([
    QuestionNumerical(
        question_name="profile_count",
        question_text="How many conjoint profiles would you like to generate?",
        min_value=1,
        max_value=1000
    ),
    QuestionYesNo(
        question_name="use_seed",
        question_text="Would you like to use a random seed for reproducible results?"
    ),
    QuestionNumerical(
        question_name="random_seed",
        question_text="What random seed would you like to use? (Enter any integer)",
        min_value=1,
        max_value=999999
    )
]).add_skip_rule("random_seed", "{{ use_seed.answer }} == 'No'")

# 2. Agent for processing
conjoint_analyst = Agent(
    name="conjoint_generator",
    traits={
        "expertise": "conjoint analysis, profile generation",
        "task": "generating random product profiles from attribute definitions"
    }
)

# 3. Simple confirmation question
confirmation_question = QuestionFreeText(
    question_name="generation_confirmation",
    question_text="Conjoint profiles will be generated from the provided attributes. Please confirm: 'Ready to generate profiles'"
)

jobs_object = Survey([confirmation_question]).by(conjoint_analyst)

# 4. Standard output formatters (the actual profile generation will happen when apps are chained)
profiles_formatter = (
    OutputFormatter(description="Conjoint Profiles")
    .select("*")
    .to_scenario_list()
)

table_formatter = (
    OutputFormatter(description="Profiles Table")
    .select("*")
    .table()
)

summary_formatter = (
    OutputFormatter(description="Generation Summary")
    .select("scenario.profile_count", "answer.generation_confirmation")
    .to_markdown()
)

# 5. Create the standard EDSL app
app = App(
    application_name="Conjoint Profile Generator",
    description="Generates random product profiles for conjoint analysis from attribute definitions (designed for app chaining with >>)",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "profiles": profiles_formatter,
        "table": table_formatter,
        "summary": summary_formatter,
    },
    default_formatter_name="profiles",
)

# 6. Wrapper function that demonstrates the intended >> chaining workflow
def chain_apps(conjoint_attributes, profile_count=10, random_seed=None):
    """
    Simulate the >> chaining workflow between conjoint_analysis and profile generation.

    Args:
        conjoint_attributes: ScenarioList from conjoint_analysis app
        profile_count: Number of profiles to generate
        random_seed: Optional random seed

    Returns:
        ScenarioList with generated conjoint profiles
    """
    # This simulates what would happen with app >> chaining
    # The conjoint_attributes would be piped from the first app to this one

    profiles = conjoint_attributes.create_conjoint_comparisons(
        attribute_field='attribute',
        levels_field='levels',
        count=profile_count,
        random_seed=random_seed
    )

    return profiles

# 7. Demonstration of the workflow
def demonstrate_app_chaining():
    """Demonstrate how the apps would work together with >> notation."""
    print("=== Demonstrating App Chaining Workflow ===\n")

    # Import the first app
    from conjoint_analysis import app as conjoint_analysis_app

    print("1. Step 1: conjoint_analysis app identifies attributes")
    conjoint_attributes = conjoint_analysis_app.output(params={"product_name": "tablet"})
    print(f"   ✓ Found {len(conjoint_attributes)} attributes")

    print("\n2. Step 2: conjoint_profiles_app generates profiles (simulated >>)")
    profiles = chain_apps(
        conjoint_attributes,
        profile_count=6,
        random_seed=42
    )
    print(f"   ✓ Generated {len(profiles)} profiles")

    print("\n3. Sample generated profiles:")
    for i, profile in enumerate(profiles[:2], 1):
        print(f"   Profile {i}:")
        for attr, value in profile.items():
            print(f"     {attr}: {value}")
        print()

    print("4. This workflow would be:")
    print("   conjoint_analysis.app >> conjoint_profiles.app")
    print("   (Where >> pipes the ScenarioList from first app to second)")

    return profiles

# 8. Test the app and workflow
if __name__ == "__main__":
    # Test the basic app functionality
    print("=== Testing Conjoint Profile Generator App ===\n")

    print("1. Testing app parameters collection...")
    app_result = app.output(
        params={
            'profile_count': 5,
            'use_seed': 'Yes',
            'random_seed': 123
        },
        formatter_name="summary"
    )
    print(f"   ✓ App collected parameters: {app_result}")

    print("\n" + "="*50)

    # Demonstrate the intended chaining workflow
    profiles = demonstrate_app_chaining()

    print(f"\n=== Summary ===")
    print("✓ Created standalone EDSL app for profile generation")
    print("✓ App collects generation parameters via survey")
    print("✓ Ready for >> chaining with conjoint_analysis app")
    print("✓ Uses ScenarioList.create_conjoint_comparisons() for generation")
    print(f"✓ Can generate {len(profiles)} profiles from conjoint attributes")

    print("\nNext steps:")
    print("- Implement proper >> chaining mechanism in EDSL")
    print("- Chain: conjoint_analysis >> conjoint_profiles >> conjoint_survey")

# 9. Convenience function for direct usage (without app chaining)
def generate_conjoint_profiles(product_name, profile_count=10, random_seed=None):
    """
    Convenience function that combines both apps in sequence.

    Args:
        product_name: Name of product to analyze
        profile_count: Number of profiles to generate
        random_seed: Optional random seed

    Returns:
        ScenarioList with generated profiles
    """
    from conjoint_analysis import app as conjoint_analysis_app

    # Step 1: Get attributes
    attributes = conjoint_analysis_app.output(params={"product_name": product_name})

    # Step 2: Generate profiles
    profiles = chain_apps(attributes, profile_count, random_seed)

    return profiles