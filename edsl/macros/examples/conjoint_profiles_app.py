from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionNumerical, QuestionYesNo, QuestionFreeText
from edsl.agents import Agent

# 1. Initial Survey - Collect profile generation parameters
initial_survey = Survey(
    [
        QuestionNumerical(
            question_name="profile_count",
            question_text="How many conjoint profiles would you like to generate?",
            min_value=1,
            max_value=1000,
        ),
        QuestionYesNo(
            question_name="use_seed",
            question_text="Would you like to use a random seed for reproducible results?",
        ),
        QuestionNumerical(
            question_name="random_seed",
            question_text="What random seed would you like to use? (Enter any integer)",
            min_value=1,
            max_value=999999,
        ),
    ]
).add_skip_rule("random_seed", "{{ use_seed.answer }} == 'No'")

# 2. Agent for processing
conjoint_analyst = Agent(
    name="conjoint_generator",
    traits={
        "expertise": "conjoint analysis, profile generation",
        "task": "generating random product profiles from attribute definitions",
    },
)

# 3. Simple confirmation question
confirmation_question = QuestionFreeText(
    question_name="generation_confirmation",
    question_text="Conjoint profiles will be generated from the provided attributes. Please confirm: 'Ready to generate profiles'",
)

jobs_object = Survey([confirmation_question]).by(conjoint_analyst)

# 4. Standard output formatters (the actual profile generation will happen when apps are chained)
profiles_formatter = (
    OutputFormatter(description="Conjoint Profiles", output_type="edsl_object")
    .select("*")
    .to_scenario_list()
)

table_formatter = (
    OutputFormatter(description="Profiles Table", output_type="table")
    .select("*")
    .table()
)

summary_formatter = (
    OutputFormatter(description="Generation Summary", output_type="markdown")
    .select("scenario.profile_count", "answer.generation_confirmation")
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# 5. Create the standard EDSL macro
macro = Macro(
    application_name="conjoint_profiles_app",
    display_name="Conjoint Profiles Generator",
    short_description="Generates random product profiles for conjoint analysis from attribute definitions.",
    long_description="Generates random product profiles for conjoint analysis from attribute definitions (designed for macro chaining with >>)",
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
def chain_macros(conjoint_attributes, profile_count=10, random_seed=None):
    """
    Simulate the >> chaining workflow between conjoint_analysis and profile generation.

    Args:
        conjoint_attributes: ScenarioList from conjoint_analysis macro
        profile_count: Number of profiles to generate
        random_seed: Optional random seed

    Returns:
        ScenarioList with generated conjoint profiles
    """
    # This simulates what would happen with macro >> chaining
    # The conjoint_attributes would be piped from the first macro to this one

    # FIXME: create_conjoint_comparisons method doesn't exist on MacroRunOutput
    # This would need to be implemented when proper macro chaining is supported
    raise NotImplementedError(
        "create_conjoint_comparisons method not yet implemented. "
        "This macro is designed for future >> chaining support."
    )

    # profiles = conjoint_attributes.create_conjoint_comparisons(
    #     attribute_field='attribute',
    #     levels_field='levels',
    #     count=profile_count,
    #     random_seed=random_seed
    # )
    # return profiles


# 7. Demonstration of the workflow
def demonstrate_macro_chaining():
    """Demonstrate how the macros would work together with >> notation."""
    print("=== Demonstrating Macro Chaining Workflow ===\n")
    print("NOTE: This feature is not yet fully implemented.")
    print(
        "The create_conjoint_comparisons method needs to be added to support this workflow.\n"
    )

    # # Import the first macro
    # from conjoint_analysis import macro as conjoint_analysis_macro
    #
    # print("1. Step 1: conjoint_analysis macro identifies attributes")
    # conjoint_attributes = conjoint_analysis_macro.output(params={"product_name": "tablet"})
    # # Convert to list to check length
    # if hasattr(conjoint_attributes, '__len__'):
    #     attr_count = len(conjoint_attributes)
    # else:
    #     attr_count = "unknown"
    # print(f"   ✓ Found {attr_count} attributes")
    #
    # print("\n2. Step 2: conjoint_profiles_macro generates profiles (simulated >>)")
    # profiles = chain_macros(
    #     conjoint_attributes,
    #     profile_count=6,
    #     random_seed=42
    # )
    # # Convert to list to check length
    # if hasattr(profiles, '__len__'):
    #     profile_count = len(profiles)
    # else:
    #     profile_count = "unknown"
    # print(f"   ✓ Generated {profile_count} profiles")
    #
    # print("\n3. Sample generated profiles:")
    # for i, profile in enumerate(profiles[:2], 1):
    #     print(f"   Profile {i}:")
    #     for attr, value in profile.items():
    #         print(f"     {attr}: {value}")
    #     print()
    #
    # print("4. This workflow would be:")
    # print("   conjoint_analysis.macro >> conjoint_profiles.macro")
    # print("   (Where >> pipes the ScenarioList from first macro to second)")

    return None


# 8. Test the macro and workflow
if __name__ == "__main__":
    # Test the basic macro functionality
    print("=== Testing Conjoint Profile Generator Macro ===\n")

    print("1. Testing macro parameters collection...")
    macro_result = macro.output(
        params={"profile_count": 5, "use_seed": "Yes", "random_seed": 123},
        formatter_name="summary",
    )
    print(f"   ✓ Macro collected parameters: {macro_result}")

    print("\n" + "=" * 50)

    # Demonstrate the intended chaining workflow
    profiles = demonstrate_macro_chaining()

    print("\n=== Summary ===")
    print("✓ Created standalone EDSL macro for profile generation")
    print("✓ Macro collects generation parameters via survey")
    print(
        "✓ Designed for >> chaining with conjoint_analysis macro (pending implementation)"
    )
    print("✓ Will use ScenarioList.create_conjoint_comparisons() for generation")

    print("\nNext steps:")
    print("- Implement create_conjoint_comparisons() method")
    print("- Implement proper >> chaining mechanism in EDSL")
    print("- Chain: conjoint_analysis >> conjoint_profiles >> conjoint_survey")


# 9. Convenience function for direct usage (without macro chaining)
def generate_conjoint_profiles(product_name, profile_count=10, random_seed=None):
    """
    Convenience function that combines both macros in sequence.

    Args:
        product_name: Name of product to analyze
        profile_count: Number of profiles to generate
        random_seed: Optional random seed

    Returns:
        ScenarioList with generated profiles
    """
    # FIXME: Not yet implemented - requires create_conjoint_comparisons method
    raise NotImplementedError(
        "This feature requires the create_conjoint_comparisons method which is not yet implemented."
    )

    # from conjoint_analysis import macro as conjoint_analysis_macro
    #
    # # Step 1: Get attributes
    # attributes = conjoint_analysis_macro.output(params={"product_name": product_name})
    #
    # # Step 2: Generate profiles
    # profiles = chain_macros(attributes, profile_count, random_seed)
    #
    # return profiles
