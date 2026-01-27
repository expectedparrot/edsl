#!/usr/bin/env python3
"""
Test gemini-2.5-flash through our EDSLAdapter (with the fix).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.edsl_adapter import EDSLAdapter
from src.config.schema import LLMConfig
from src.prompts.judge import JudgeQuestionPrompt

print("="*70)
print("Testing gemini-2.5-flash through EDSLAdapter")
print("="*70)

try:
    # Create adapter
    adapter = EDSLAdapter(LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0))

    # Create a judge question prompt
    prompt = JudgeQuestionPrompt(
        target_id="A",
        story_content="Scientists discovered a new species of deep-sea fish that glows in the dark.",
        question_number=1,
        total_questions=1,
        question_style="curious"
    )

    prompt_text = prompt.render()

    print("\nTest: Generating question with gemini-2.5-flash (using agent traits)")
    print("-"*70)

    result = adapter.generate_question(
        prompt_text=prompt_text,
        target_storyteller_id="A",
        question_number=1,
        model_name="gemini-2.5-flash",  # Override to use Gemini
        temperature=1.0
    )

    print(f"✅ SUCCESS!")
    print(f"   Question: {result['content'][:200]}")
    print(f"   Model: {result.get('model', 'unknown')}")

except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
