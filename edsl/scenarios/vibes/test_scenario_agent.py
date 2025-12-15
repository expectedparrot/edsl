#!/usr/bin/env python3
"""
Simple test script for the ScenarioAgent functionality.

This script tests the new intelligent from_vibes method to ensure it works
with different strategies and provides appropriate feedback.
"""

import sys
import os

# Add the edsl package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def test_scenario_agent():
    """Test the ScenarioAgent with different strategies."""

    try:
        from edsl.scenarios.scenario_list import ScenarioList

        print("🧪 Testing ScenarioList.from_vibes intelligent agent...")
        print("=" * 60)

        # Test 1: AI-only strategy (most likely to work)
        print("\n📝 Test 1: AI-only strategy")
        print("-" * 30)
        try:
            sl = ScenarioList.from_vibes(
                "5 fruits and their colors",
                strategy="ai_only",
                generator_count=5,
                verbose=True
            )
            print(f"✅ AI-only test passed! Created {len(sl)} scenarios")
            print("Sample data:", sl[0] if len(sl) > 0 else "No data")
        except Exception as e:
            print(f"❌ AI-only test failed: {e}")

        # Test 2: Fast strategy (Wikipedia then AI)
        print("\n📝 Test 2: Fast strategy")
        print("-" * 30)
        try:
            sl = ScenarioList.from_vibes(
                "European countries",
                strategy="fast",
                verbose=True
            )
            print(f"✅ Fast strategy test passed! Created {len(sl)} scenarios")
            print("Sample data:", sl[0] if len(sl) > 0 else "No data")
        except Exception as e:
            print(f"❌ Fast strategy test failed: {e}")

        print("\n🎉 Testing complete!")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the correct directory")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scenario_agent()