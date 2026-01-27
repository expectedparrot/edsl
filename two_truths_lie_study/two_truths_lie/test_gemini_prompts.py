#!/usr/bin/env python3
"""
Test gemini-2.5-flash with actual game prompts to identify the breaking point.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edsl import QuestionFreeText, Model, Agent

GEMINI_MODEL = "gemini-2.5-flash"


def test_without_agent():
    """Test with just the model, no agent."""
    print("\n" + "="*70)
    print("Test 1: Judge Question Prompt WITHOUT Agent")
    print("="*70)

    prompt = """You are the JUDGE in a game called "Why Would I Lie?"

STORYTELLER A'S STORY:
Scientists discovered a new species of deep-sea fish that glows in the dark.

This is question 1 of 1 for Storyteller A.

Ask ONE focused question that will help you determine if this storyteller is telling
the truth or fabricating their story. Be direct and specific.

Your question for Storyteller A:"""

    try:
        question = QuestionFreeText(
            question_text=prompt,
            question_name="test_question"
        )
        model = Model(GEMINI_MODEL)

        print("Running question...")
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        answer = results.select("answer.test_question").first()

        if answer:
            print(f"✅ SUCCESS")
            print(f"   Answer: {answer[:200]}")
            return True
        else:
            print(f"❌ FAILED: Got None response")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def test_with_agent():
    """Test with agent traits (role: judge)."""
    print("\n" + "="*70)
    print("Test 2: Judge Question Prompt WITH Agent")
    print("="*70)

    prompt = """You are the JUDGE in a game called "Why Would I Lie?"

STORYTELLER A'S STORY:
Scientists discovered a new species of deep-sea fish that glows in the dark.

This is question 1 of 1 for Storyteller A.

Ask ONE focused question that will help you determine if this storyteller is telling
the truth or fabricating their story. Be direct and specific.

Your question for Storyteller A:"""

    try:
        question = QuestionFreeText(
            question_text=prompt,
            question_name="test_question"
        )
        model = Model(GEMINI_MODEL)
        agent = Agent(traits={"role": "judge"})

        print("Running question with agent...")
        results = question.by(agent).by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        answer = results.select("answer.test_question").first()

        if answer:
            print(f"✅ SUCCESS")
            print(f"   Answer: {answer[:200]}")
            return True
        else:
            print(f"❌ FAILED: Got None response")
            # Try to see what's in the results
            print(f"   Results keys: {list(results.to_dict().keys())}")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_long_prompt():
    """Test with a very long prompt (3 stories)."""
    print("\n" + "="*70)
    print("Test 3: Long Prompt (3 Stories)")
    print("="*70)

    story_a = "Story A: " + " ".join(["word"] * 300)
    story_b = "Story B: " + " ".join(["word"] * 300)
    story_c = "Story C: " + " ".join(["word"] * 300)

    prompt = f"""You are the JUDGE in a game.

STORYTELLER A: {story_a}

STORYTELLER B: {story_b}

STORYTELLER C: {story_c}

Ask a question for Storyteller A:"""

    try:
        question = QuestionFreeText(
            question_text=prompt,
            question_name="test_question"
        )
        model = Model(GEMINI_MODEL)

        print(f"Prompt length: {len(prompt)} chars, {len(prompt.split())} words")
        print("Running long question...")
        results = question.by(model).run(
            use_api_proxy=True,
            offload_execution=False,
            progress_bar=False
        )

        answer = results.select("answer.test_question").first()

        if answer:
            print(f"✅ SUCCESS")
            print(f"   Answer: {answer[:100]}")
            return True
        else:
            print(f"❌ FAILED: Got None response")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("GEMINI PROMPT COMPATIBILITY TEST")
    print("="*70)
    print(f"\nTesting {GEMINI_MODEL} with various prompt configurations...")

    test1 = test_without_agent()
    test2 = test_with_agent()
    test3 = test_with_long_prompt()

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"  Without Agent:  {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"  With Agent:     {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"  Long Prompt:    {'✅ PASS' if test3 else '❌ FAIL'}")

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)

    if test1 and test2:
        print("✅ gemini-2.5-flash works with our judge prompts!")
        print("   Problem may be elsewhere in the code flow.")
    elif test1 and not test2:
        print("❌ gemini-2.5-flash fails when using Agent traits")
        print("   Fix: Remove agent traits from gemini calls")
    elif not test1:
        print("❌ gemini-2.5-flash fails with judge role prompts")
        print("   Fix: Simplify prompts or skip Gemini in Phase 2")

    print()
    return 0 if (test1 and test2) else 1


if __name__ == "__main__":
    sys.exit(main())
