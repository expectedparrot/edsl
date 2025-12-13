#!/usr/bin/env python3
"""
Test the exact code you want to run and see how the vibe system performs.
"""


def test_real_case():
    """Test the exact Python code you specified."""
    print(
        "Testing: from edsl import Results; r = Results.from_qualtrics('ai_tracking_new.csv')"
    )
    print("=" * 70)

    try:
        # Your exact code
        from edsl import Results

        r = Results.from_qualtrics("ai_tracking_new.csv")

        print("\n" + "=" * 70)
        print("✅ SUCCESS! Import completed successfully")
        print(f"📋 Results object created with {len(r)} response records")

        # Show some basic info about what we got
        if hasattr(r, "survey") and r.survey and r.survey.questions:
            print(f"📝 Survey has {len(r.survey.questions)} questions")

            # Show question types to see if conversions happened
            type_counts = {}
            conversions_found = []

            for q in r.survey.questions:
                qtype = q.__class__.__name__
                type_counts[qtype] = type_counts.get(qtype, 0) + 1

                # Look for signs of conversions (LinearScale questions are likely conversions)
                if qtype == "QuestionLinearScale":
                    conversions_found.append(f"  {q.question_name}: {qtype}")
                    # Show the details of the linear scale
                    if hasattr(q, "question_options") and hasattr(q, "option_labels"):
                        print(f"    └─ Scale: {q.question_options}")
                        if q.option_labels:
                            print(f"    └─ Labels: {q.option_labels}")

            print(f"\n📊 Question type breakdown:")
            for qtype, count in sorted(type_counts.items()):
                print(f"   {qtype}: {count}")

            if conversions_found:
                print(f"\n🔄 Type conversions found:")
                for conversion in conversions_found:
                    print(conversion)
            else:
                print(f"\n💡 No type conversions detected in this run")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_real_case()
