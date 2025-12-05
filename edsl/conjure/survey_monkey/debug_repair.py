#!/usr/bin/env python3
"""Debug script to test Excel date repair functionality with your actual data."""

import os
import sys


def debug_import_with_repair():
    """Debug the import process with repair enabled."""
    print("🔍 Debugging Excel Date Repair")
    print("=" * 50)

    # Try to find the actual CSV file you're using
    csv_files = [f for f in os.listdir(".") if f.endswith(".csv")]
    if not csv_files:
        print("❌ No CSV files found in current directory")
        print("Please run this script from the directory containing your CSV file")
        return

    print(f"📁 Found CSV files: {csv_files}")

    # Use the first CSV file found (or you can specify which one to use)
    csv_file = csv_files[0]
    print(f"🎯 Testing with: {csv_file}")

    try:
        from import_survey_monkey import ImportSurveyMonkey

        print("✅ ImportSurveyMonkey imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ImportSurveyMonkey: {e}")
        return

    print("\n" + "=" * 50)
    print("1️⃣ Testing WITHOUT repair (explicitly disabled)")
    print("=" * 50)

    try:
        # Test without repair first (explicitly disabled since default is now True)
        importer_no_repair = ImportSurveyMonkey(
            csv_file, verbose=True, repair_excel_dates=False
        )
        print("✅ Import without repair completed")

        # Check for potential date-like values
        survey = importer_no_repair.survey
        print(f"📊 Survey has {len(survey.questions)} questions")

        # Look for suspicious date-like options
        suspicious_options = []
        for question in survey.questions:
            if hasattr(question, "question_options") and question.question_options:
                for option in question.question_options:
                    if any(
                        month in option
                        for month in [
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec",
                        ]
                    ):
                        suspicious_options.append((question.question_name, option))

        if suspicious_options:
            print(f"🚨 Found {len(suspicious_options)} suspicious date-like options:")
            for q_name, option in suspicious_options:
                print(f"   {q_name}: '{option}'")
        else:
            print("✅ No suspicious date-like options found")

    except Exception as e:
        print(f"❌ Error in import without repair: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 50)
    print("2️⃣ Testing WITH repair (default behavior)")
    print("=" * 50)

    try:
        # Test with repair enabled (now the default)
        importer_with_repair = ImportSurveyMonkey(csv_file, verbose=True)
        print("✅ Import with repair completed")

        # Check what repairs were made
        repairs = importer_with_repair.get_excel_date_repairs()
        if repairs:
            print(f"🔧 Excel repairs applied: {len(repairs)}")
            for original, repaired in repairs.items():
                print(f"   '{original}' → '{repaired}'")
        else:
            print("ℹ️  No Excel repairs were applied")

        # Check what semantic orderings were made
        orderings = importer_with_repair.get_semantic_ordering_changes()
        if orderings:
            print(f"🎯 Semantic orderings applied: {len(orderings)}")
            for ordering in orderings:
                print(
                    f"   {ordering['question_identifier']}: {ordering['ordering_type']}"
                )
        else:
            print("ℹ️  No semantic orderings were applied")

        # Print the summaries
        print("\n" + "-" * 40)
        importer_with_repair.print_excel_date_repairs()
        print()
        importer_with_repair.print_semantic_ordering_changes()

        # Compare question options
        survey_repaired = importer_with_repair.survey
        print(f"\n📊 Repaired survey has {len(survey_repaired.questions)} questions")

        # Check if options actually changed
        options_changed = False
        for i, question in enumerate(survey_repaired.questions):
            if hasattr(question, "question_options") and question.question_options:
                original_question = survey.questions[i]
                if hasattr(original_question, "question_options"):
                    if question.question_options != original_question.question_options:
                        options_changed = True
                        print(
                            f"📝 Question '{question.question_name}' options changed:"
                        )
                        print(f"   Before: {original_question.question_options}")
                        print(f"   After:  {question.question_options}")

        if not options_changed:
            print("⚠️  No question options were changed")

    except Exception as e:
        print(f"❌ Error in import with repair: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 50)
    print("3️⃣ Testing Response Records")
    print("=" * 50)

    try:
        # Check if response records contain repaired values
        response_records = importer_with_repair._response_records
        print(f"📊 Found {len(response_records)} response records")

        # Sample the first few records
        sample_records = response_records[:3]
        for i, record in enumerate(sample_records):
            print(f"📝 Sample record {i+1}: {record}")

            # Check for suspicious date values in responses
            suspicious_responses = []
            for key, value in record.items():
                if isinstance(value, str):
                    if any(
                        month in value
                        for month in [
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec",
                        ]
                    ):
                        suspicious_responses.append((key, value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and any(
                            month in item
                            for month in [
                                "Jan",
                                "Feb",
                                "Mar",
                                "Apr",
                                "May",
                                "Jun",
                                "Jul",
                                "Aug",
                                "Sep",
                                "Oct",
                                "Nov",
                                "Dec",
                            ]
                        ):
                            suspicious_responses.append((key, item))

            if suspicious_responses:
                print(f"   🚨 Suspicious responses: {suspicious_responses}")

    except Exception as e:
        print(f"❌ Error checking response records: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_import_with_repair()
