#!/usr/bin/env python3
"""
Real EXA API Test Script

This script tests the actual EXA integration to verify it's working correctly.
"""

import os
import sys
import traceback
from pathlib import Path

# Add the edsl directory to the Python path
edsl_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(edsl_root))

def test_exa_integration():
    """Test the EXA integration with real API calls."""

    print("🔍 TESTING REAL EXA INTEGRATION")
    print("=" * 50)

    # Step 1: Load environment properly
    try:
        from dotenv import load_dotenv, find_dotenv

        # Try multiple locations for .env file
        possible_env_files = [
            edsl_root / ".env",
            edsl_root / ".env.local",
            edsl_root / ".env.current",
            Path.cwd() / ".env"
        ]

        env_file = None
        for possible_file in possible_env_files:
            if possible_file.exists():
                env_file = str(possible_file)
                break

        if not env_file:
            env_file = find_dotenv()

        print(f"Loading environment from: {env_file}")
        load_dotenv(env_file)

        api_key = os.environ.get('EXA_API_KEY')
        if api_key:
            print(f"✓ EXA_API_KEY found: {api_key[:8]}...")
        else:
            print("❌ No EXA_API_KEY found in environment")
            return False

    except Exception as e:
        print(f"❌ Environment loading failed: {e}")
        return False

    # Step 2: Test library import
    try:
        import exa_py
        print(f"✓ exa-py library available (version: {getattr(exa_py, '__version__', 'unknown')})")
    except ImportError:
        print("❌ exa-py library not available - installing...")
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'exa-py'], check=True)
        print("✓ exa-py installed")

    # Step 3: Test EDSL import
    try:
        from edsl.scenarios import ScenarioList
        print("✓ EDSL ScenarioList imported successfully")
    except Exception as e:
        print(f"❌ EDSL import failed: {e}")
        return False

    # Step 4: Test basic EXA search
    try:
        print("\n🔍 Running test search: 'startup founders'")
        print("This should complete quickly...")

        scenarios = ScenarioList.from_exa(
            query="startup founders",
            count=2,  # Small count for quick test
            max_wait_time=60  # 1 minute timeout
        )

        print(f"\n✅ SUCCESS! Retrieved {len(scenarios)} scenarios")

        if len(scenarios) > 0:
            first = scenarios[0]
            print(f"\nFirst scenario data:")
            print(f"- Type: {type(first)}")
            print(f"- Keys: {sorted(first.keys())}")

            # Show key fields
            key_fields = ['name', 'position', 'company_name', 'description', 'exa_query']
            for field in key_fields:
                value = first.get(field, 'Not found')
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"- {field}: {value}")

            # Check if we got real data or just metadata
            if first.get('exa_message'):
                print(f"\n⚠️  Got metadata only: {first['exa_message']}")
                print(f"   Webset ID: {first.get('exa_webset_id')}")
                return False
            else:
                print(f"\n🎉 Got real data! EXA integration is working correctly!")
                return True
        else:
            print("❌ No scenarios returned")
            return False

    except Exception as e:
        print(f"❌ EXA search failed: {e}")
        traceback.print_exc()
        return False

def test_webset_retrieval():
    """Test retrieving data from an existing webset."""

    print("\n" + "=" * 50)
    print("🔍 TESTING WEBSET RETRIEVAL")

    try:
        from edsl.scenarios import ScenarioList

        # Test with a known webset ID (from previous successful search)
        # You can replace this with a real webset ID if you have one
        test_webset_id = "webset_01kcfwehfh6r300tqa4950c10c"  # From earlier tests

        print(f"Testing webset retrieval: {test_webset_id}")

        scenarios = ScenarioList.from_exa_webset(test_webset_id)

        print(f"✅ Retrieved {len(scenarios)} scenarios from webset")

        if len(scenarios) > 0:
            first = scenarios[0]
            if first.get('exa_message'):
                print(f"⚠️  Webset message: {first['exa_message']}")
            else:
                print(f"✅ Webset data: {first.get('name', 'No name')}")

        return True

    except Exception as e:
        print(f"❌ Webset retrieval failed: {e}")
        return False

def main():
    """Run all tests."""

    print("Starting EXA integration verification...")
    print("This will test with real API calls to verify everything works.\n")

    # Test 1: Basic integration
    test1_passed = test_exa_integration()

    # Test 2: Webset retrieval
    test2_passed = test_webset_retrieval()

    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print(f"✅ Basic EXA search: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"✅ Webset retrieval: {'PASSED' if test2_passed else 'FAILED'}")

    if test1_passed and test2_passed:
        print("\n🎉 EXA INTEGRATION IS WORKING CORRECTLY!")
        print("You can now use ScenarioList.from_exa() in your projects.")
    else:
        print("\n❌ EXA INTEGRATION HAS ISSUES")
        print("Check the error messages above for troubleshooting.")

    return test1_passed and test2_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)