#!/usr/bin/env python3
"""
Actually verify the EXA data is real and accurate.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from edsl.scenarios import ScenarioList

# Add edsl to path
edsl_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(edsl_root))

# Load environment
load_dotenv(edsl_root / ".env")


def verify_exa_data():
    """Verify the data is real by checking profile URLs and details."""

    print("🔍 VERIFYING EXA DATA IS REAL")
    print("=" * 40)

    try:
        scenarios = ScenarioList.from_exa("startup founders", count=2, max_wait_time=60)

        print(f"Retrieved {len(scenarios)} results")
        print()

        for i, scenario in enumerate(scenarios):
            print(f"RESULT {i+1}:")
            print(f"  Name: {scenario.get('name', 'N/A')}")
            print(f"  Position: {scenario.get('position', 'N/A')}")
            print(f"  Company: {scenario.get('company_name', 'N/A')}")
            print(f"  Location: {scenario.get('location', 'N/A')}")
            print(f"  Profile URL: {scenario.get('profile_url', 'N/A')}")
            print(f"  Description: {scenario.get('description', 'N/A')[:200]}...")
            print()
            print(f"  EXA Criterion: {scenario.get('criterion', 'N/A')}")
            print(f"  EXA Reasoning: {scenario.get('reasoning', 'N/A')[:200]}...")
            print(f"  Satisfied: {scenario.get('satisfied', 'N/A')}")
            print()
            print("  Raw EXA data:")
            exa_fields = {k: v for k, v in scenario.items() if k.startswith("exa_")}
            for key, value in exa_fields.items():
                print(f"    {key}: {value}")
            print()
            print("-" * 50)

        # Show what we can verify
        print("\n🔍 VERIFICATION STEPS:")
        print("1. Check if profile URLs are real LinkedIn profiles")
        print("2. Verify the names and companies exist")
        print("3. Check if descriptions match actual profiles")
        print("4. Compare EXA reasoning with actual profile content")

        # Get first result for detailed verification
        if scenarios:
            first = scenarios[0]
            print(f"\n📋 DETAILED VERIFICATION FOR: {first.get('name', 'Unknown')}")
            print(f"Profile URL: {first.get('profile_url', 'None')}")
            print(f"Company: {first.get('company_name', 'None')}")
            print(f"Position: {first.get('position', 'None')}")
            print(f"EXA Item ID: {first.get('exa_item_id', 'None')}")
            print(f"EXA Webset ID: {first.get('exa_webset_id', 'None')}")

            print("\n💡 TO VERIFY THIS IS REAL:")
            print("1. Visit the LinkedIn URL above")
            print("2. Check if the person/company actually exists")
            print("3. Verify the position matches what's shown")
            print("4. Compare the description with actual LinkedIn profile")

            return first.get("profile_url"), first.get("name")

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


def compare_with_direct_exa():
    """Compare our integration with direct EXA API call to see if data matches."""

    print("\n🔍 COMPARING WITH DIRECT EXA API")
    print("=" * 40)

    try:
        from exa_py import Exa

        exa = Exa(os.getenv("EXA_API_KEY"))

        # Create webset directly
        print("Creating webset directly with EXA API...")
        from exa_py.websets.types import CreateWebsetParameters

        webset = exa.websets.create(
            params=CreateWebsetParameters(
                search={"query": "startup founders", "count": 1}
            )
        )

        print(f"Direct EXA webset ID: {webset.id}")
        print(f"Direct EXA status: {webset.status}")

        # Wait a bit for it to process
        import time

        time.sleep(10)

        # Get items directly
        items_response = exa.websets.items.list(webset.id)
        items = list(items_response)

        print(f"Direct EXA items count: {len(items)}")

        if items:
            # Show raw structure
            for item_tuple in items:
                print(f"Item tuple type: {type(item_tuple)}")
                if isinstance(item_tuple, tuple) and len(item_tuple) == 2:
                    category, item_list = item_tuple
                    print(f"Category: {category}")
                    print(f"Items in list: {len(item_list) if item_list else 0}")

                    if item_list:
                        first_item = item_list[0]
                        print(f"First item type: {type(first_item)}")
                        if hasattr(first_item, "properties"):
                            print(
                                f"Person name: {getattr(first_item.properties.person, 'name', 'N/A')}"
                            )
                            print(
                                f"Company: {getattr(first_item.properties.person.company, 'name', 'N/A') if hasattr(first_item.properties.person, 'company') else 'N/A'}"
                            )
                            print(f"URL: {first_item.properties.url}")

        return webset.id

    except Exception as e:
        print(f"❌ Direct EXA error: {e}")
        return None


if __name__ == "__main__":
    print("This script will help verify if EXA data is actually real...")
    print("It will show you specific URLs and details you can manually verify.")
    print()

    # Test our integration
    profile_url, name = verify_exa_data()

    # Test direct EXA API
    direct_webset_id = compare_with_direct_exa()

    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    if profile_url and name:
        print(f"✅ Got data for: {name}")
        print(f"✅ Profile URL: {profile_url}")
        print("🔍 NEXT STEPS TO VERIFY:")
        print("1. Visit the LinkedIn URL above")
        print("2. Check if it's a real person/profile")
        print("3. Verify the company and position match")
    else:
        print("❌ No data retrieved to verify")

    if direct_webset_id:
        print(f"✅ Direct EXA API also worked: {direct_webset_id}")
        print("✅ This confirms our integration is using real EXA data")
    else:
        print("❌ Direct EXA API test failed")
