#!/usr/bin/env python3
"""Quick test of the Excel date repair functionality."""

import os

def test_repair_directly():
    """Test the ExcelDateRepairer directly with sample data."""
    print("🧪 Testing ExcelDateRepairer directly")
    print("=" * 40)

    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return False

    try:
        from excel_date_repairer import ExcelDateRepairer
        print("✅ ExcelDateRepairer imported successfully")
    except Exception as e:
        print(f"❌ Failed to import: {e}")
        return False

    # Test with the exact values from your results
    test_options = ["5-Mar", "2-Jan", "More than 10", "0"]

    try:
        repairer = ExcelDateRepairer(verbose=True)
        print("✅ ExcelDateRepairer initialized")

        result = repairer.repair_question_options("test_question", test_options)

        print(f"\nOriginal options: {test_options}")
        print(f"Repaired options: {result.repaired_options}")

        if result.any_repairs_applied:
            print(f"✅ Applied {len(result.repairs_made)} repairs:")
            for repair in result.repairs_made:
                print(f"  '{repair.original}' → '{repair.repaired}' (confidence: {repair.confidence:.2f})")
        else:
            print("❌ No repairs were applied!")

        return result.any_repairs_applied

    except Exception as e:
        print(f"❌ Error during repair: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_import_usage():
    """Check how the import was actually used."""
    print("\n🔍 Checking ImportSurveyMonkey usage")
    print("=" * 40)

    print("Both Excel date repair AND semantic ordering are ENABLED BY DEFAULT:")
    print("  importer = ImportSurveyMonkey('file.csv')")
    print("  # repair_excel_dates=True, order_options_semantically=True by default")
    print("\nTo disable features if not needed:")
    print("  importer = ImportSurveyMonkey('file.csv',")
    print("                              repair_excel_dates=False,")
    print("                              order_options_semantically=False)")
    print("\nTo check what processing was applied:")
    print("  importer.print_excel_date_repairs()         # Show date repairs")
    print("  importer.print_semantic_ordering_changes()  # Show reorderings")
    print("  # or access programmatically:")
    print("  repairs = importer.get_excel_date_repairs()")
    print("  orderings = importer.get_semantic_ordering_changes()")

if __name__ == "__main__":
    success = test_repair_directly()
    check_import_usage()

    if success:
        print("\n✅ Direct repair test PASSED")
        print("The issue is likely that repair_excel_dates=True wasn't used during import")
    else:
        print("\n❌ Direct repair test FAILED")
        print("Check your OpenAI API setup or network connection")