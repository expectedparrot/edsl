#!/usr/bin/env python3
"""
Test the specific MIT economists query that was having issues.
"""

import os
import sys
from pathlib import Path

# Add edsl to path
edsl_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(edsl_root))

# Load environment
from dotenv import load_dotenv

load_dotenv(edsl_root / ".env")

# Test the specific query
from edsl.scenarios import ScenarioList

print("🔍 TESTING: MIT Economists studying AI")
print("=" * 45)
print("This is the exact query that was timing out...")
print()

try:
    # Use a longer timeout and show what's happening
    scenarios = ScenarioList.from_exa(
        "Professors at MIT Sloan School of Management",
        count=15,
        max_wait_time=180,  # 3 minutes - longer for complex queries
    )

    print(f"\n✅ SUCCESS! Found {len(scenarios)} economists")

    for i, scenario in enumerate(scenarios):
        print(f"\n👨‍🏫 ECONOMIST {i+1}:")
        print(f"   Name: {scenario.get('name', 'Unknown')}")
        print(f"   Position: {scenario.get('position', 'Unknown')}")
        print(f"   Institution: {scenario.get('company_name', 'Unknown')}")
        print(f"   Location: {scenario.get('location', 'Unknown')}")

        desc = scenario.get("description", "No description")
        print(f"   Research: {desc[:150]}...")

except KeyboardInterrupt:
    print("\n⏹️  Search interrupted by user")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
