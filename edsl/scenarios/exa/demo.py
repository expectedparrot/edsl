"""
Quick demonstration of EXA integration with EDSL ScenarioLists.

This file shows the simplest way to get started with the EXA module.
"""

import os


def demo():
    """Demonstrate EXA integration usage."""

    print("🔍 EXA API Integration for EDSL Demo")
    print("=" * 40)

    # Check for API key
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        print("\n⚠️  No EXA_API_KEY found in environment.")
        print("   To run this demo with real API calls:")
        print("   export EXA_API_KEY='your-api-key'")
        print("\n📚 Documentation and examples available:")
        print("   - See README.md for comprehensive guide")
        print("   - See example_usage.py for detailed examples")
        print("   - See test_exa_loader.py for test patterns")
        return

    print(f"\n✅ EXA_API_KEY found: {api_key[:8]}...")

    try:
        from edsl.scenarios import ScenarioList

        # Example 1: Simple search
        print("\n1️⃣  Simple Search Example:")
        print(
            "   ScenarioList.from_exa('Sales leaders at fintech companies', count=10)"
        )

        scenarios = ScenarioList.from_exa(
            query="Sales leaders at fintech companies", count=10
        )

        print(f"   ✅ Created {len(scenarios)} scenarios")
        if scenarios:
            print(f"   📋 Sample keys: {list(scenarios[0].keys())}")

        # Example 2: Search with enrichments
        print("\n2️⃣  Advanced Search with Enrichments:")
        print("   ScenarioList.from_exa(query=..., criteria=..., enrichments=...)")

        scenarios_advanced = ScenarioList.from_exa(
            query="AI startup founders",
            criteria=[
                "founded an AI or ML company",
                "currently serves as CEO or founder",
            ],
            enrichments=[
                {"description": "Years of experience", "format": "number"},
                {"description": "Previous companies", "format": "list"},
            ],
            count=5,
        )

        print(f"   ✅ Created {len(scenarios_advanced)} scenarios")

        # Example 3: Load from webset
        print("\n3️⃣  Load from Existing Webset:")
        print("   ScenarioList.from_exa_webset('webset-id')")

        # Note: This would use the webset ID from the user's example
        # scenarios_webset = ScenarioList.from_exa_webset("01k6m4wn1aykv03jq3p4hxs2m9")

        print("   📋 (Replace with your actual webset ID)")

        print("\n🎉 Demo completed successfully!")
        print("\n📖 Next steps:")
        print("   - Explore example_usage.py for more examples")
        print("   - Read README.md for complete documentation")
        print("   - Integrate with EDSL Surveys and Questions")

    except ImportError as e:
        if "exa-py" in str(e):
            print("\n❌ exa-py library not installed")
            print("   Install with: pip install exa-py")
        else:
            print(f"\n❌ Import error: {e}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   Check your API key and internet connection")


if __name__ == "__main__":
    demo()
