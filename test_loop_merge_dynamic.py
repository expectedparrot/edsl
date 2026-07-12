"""End-to-end test for dynamic Loop & Merge on the new runner.

Uses the canned `test` model so it needs no API keys. The source question
(`QuestionList`) returns a real list; the runner should inject one follow-up
(`QuestionFreeText`) task per returned item and surface them in Results.
"""
from edsl import QuestionList, QuestionFreeText, Survey, Model, Scenario


def main():
    # Source question whose answer is the loop set.
    q_source = QuestionList(
        question_name="departments",
        question_text="List the departments in a company.",
    )
    # Follow-up template (NOT added to the survey) referencing the current item.
    q_follow = QuestionFreeText(
        question_name="head",
        question_text="Who is the head of the {{ loop_item }} department?",
    )

    survey = Survey([q_source]).add_loop_merge(
        source="departments", templates=q_follow, item_key="loop_item"
    )

    # Canned answers: source returns 3 items; follow-ups get a per-item canned answer.
    canned = {
        "departments": ["Engineering", "Sales", "Marketing"],
        # follow-up names are mangled: head_departments_0/1/2
        "head_departments_0": "Ada Lovelace",
        "head_departments_1": "Grace Hopper",
        "head_departments_2": "Katherine Johnson",
    }
    model = Model("test", canned_response=canned)

    print("Running dynamic Loop & Merge job on the test model...")
    results = survey.by(model).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    cols = results.columns
    print("\n--- Results columns ---")
    for c in sorted(cols):
        print("  ", c)

    # The source answer
    depts = results.select("departments").to_list()
    print("\ndepartments answer:", depts)

    # The injected follow-up answers
    injected = [c for c in cols if c.startswith("answer.head_departments_")]
    print("injected follow-up columns:", sorted(injected))

    ok = True
    if not injected:
        print("\nFAIL: no injected follow-up columns found in Results.")
        ok = False
    else:
        for c in sorted(injected):
            key = c.split(".", 1)[1]
            vals = results.select(key).to_list()
            print(f"  {key} = {vals}")

    # Assertions
    expected_injected = {
        "answer.head_departments_0",
        "answer.head_departments_1",
        "answer.head_departments_2",
    }
    missing = expected_injected - set(injected)
    if missing:
        print(f"\nFAIL: missing injected columns: {missing}")
        ok = False

    if ok:
        vals = {
            c.split(".", 1)[1]: results.select(c.split(".", 1)[1]).to_list()[0]
            for c in expected_injected
        }
        if (
            vals.get("head_departments_0") == "Ada Lovelace"
            and vals.get("head_departments_1") == "Grace Hopper"
            and vals.get("head_departments_2") == "Katherine Johnson"
        ):
            print("\nPASS: all 3 injected follow-up answers present and correct.")
        else:
            print(f"\nFAIL: injected answers wrong: {vals}")
            ok = False

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
