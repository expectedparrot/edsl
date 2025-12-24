#!/usr/bin/env python3
"""
Demonstration of the vibe system for AI-powered question enhancement in Qualtrics imports.

This script shows how to use the vibe functionality to automatically improve
imported questions using AI agents.
"""

import tempfile
import csv
from pathlib import Path
from qualtrics import ImportQualtrics
from qualtrics.vibe import VibeConfig


def create_problematic_survey():
    """Create a test CSV with questions that could benefit from vibe processing."""

    headers = ["Q1", "Q2", "Q3", "Q4"]
    question_texts = [
        "whats ur name???",  # Bad grammar, punctuation
        "Rate our svc on scale 1-5 where 1=bad 5=good",  # Abbreviations, unclear
        "Do you like our product and would you recommend it and why or why not?",  # Multiple questions in one
        "Select ur fav color: Red Blue Green Yellow Orange Purple Pink",  # Bad formatting
    ]
    import_ids = [
        '{"ImportId":"QID1"}',
        '{"ImportId":"QID2"}',
        '{"ImportId":"QID3"}',
        '{"ImportId":"QID4"}',
    ]
    responses = [
        ["John", "3", "Yes, it's great and I'd recommend it", "Blue"],
        ["Jane", "4", "Good product, would recommend", "Red"],
        ["Bob", "2", "Not great, wouldn't recommend", "Green"],
    ]

    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(temp_file)

    writer.writerow(headers)
    writer.writerow(question_texts)
    writer.writerow(import_ids)

    for response in responses:
        writer.writerow(response)

    temp_file.close()
    return temp_file.name


def demo_without_vibe():
    """Demonstrate import without vibe processing."""
    print("=" * 60)
    print("DEMO 1: Import WITHOUT Vibe Processing")
    print("=" * 60)

    csv_file = create_problematic_survey()

    try:
        importer = ImportQualtrics(csv_file, verbose=True)
        survey = importer.survey

        print("\n--- Questions without vibe processing ---")
        for i, q in enumerate(survey.questions, 1):
            print(f"{i}. {q.question_name}: {q.question_text}")
            if hasattr(q, "question_options"):
                print(f"   Options: {q.question_options}")
            print()

    finally:
        Path(csv_file).unlink(missing_ok=True)


def demo_with_vibe():
    """Demonstrate import with vibe processing."""
    print("=" * 60)
    print("DEMO 2: Import WITH Vibe Processing")
    print("=" * 60)

    csv_file = create_problematic_survey()

    try:
        # Configure vibe processing
        vibe_config = VibeConfig(
            enabled=True,
            system_prompt="""You are an expert survey designer. Clean up and improve the following questions:

1. Fix grammar, spelling, and punctuation errors
2. Expand abbreviations (svc -> service, ur -> your, etc.)
3. Make questions clearer and more professional
4. Split compound questions into separate questions when appropriate
5. Format multiple choice options properly
6. Ensure question text is concise but complete

Provide improvements that make the survey more professional and easier to understand.""",
            max_concurrent=2,
            temperature=0.1,
        )

        importer = ImportQualtrics(csv_file, verbose=True, vibe_config=vibe_config)
        survey = importer.survey

        print("\n--- Questions with vibe processing ---")
        for i, q in enumerate(survey.questions, 1):
            print(f"{i}. {q.question_name}: {q.question_text}")
            if hasattr(q, "question_options"):
                print(f"   Options: {q.question_options}")
            print()

    finally:
        Path(csv_file).unlink(missing_ok=True)


def demo_custom_system_prompt():
    """Demonstrate vibe processing with custom system prompt."""
    print("=" * 60)
    print("DEMO 3: Custom System Prompt - Focus on Academic Style")
    print("=" * 60)

    csv_file = create_problematic_survey()

    try:
        # Custom academic-focused system prompt
        academic_prompt = """You are an academic researcher designing a formal research survey.

Transform questions to meet academic standards:
1. Use formal, professional language
2. Avoid colloquialisms and abbreviations
3. Ensure questions are unbiased and neutral
4. Use precise, scientific terminology where appropriate
5. Make questions suitable for peer review
6. Follow survey methodology best practices

Focus on clarity, neutrality, and academic rigor."""

        vibe_config = VibeConfig(
            enabled=True,
            system_prompt=academic_prompt,
            max_concurrent=2,
            temperature=0.05,  # Very low temperature for consistency
        )

        importer = ImportQualtrics(csv_file, verbose=True, vibe_config=vibe_config)
        survey = importer.survey

        print("\n--- Questions with academic-focused vibe processing ---")
        for i, q in enumerate(survey.questions, 1):
            print(f"{i}. {q.question_name}: {q.question_text}")
            if hasattr(q, "question_options"):
                print(f"   Options: {q.question_options}")
            print()

    finally:
        Path(csv_file).unlink(missing_ok=True)


def demo_vibe_config_options():
    """Demonstrate various vibe configuration options."""
    print("=" * 60)
    print("DEMO 4: Vibe Configuration Options")
    print("=" * 60)

    # Show different configuration approaches
    configs = [
        {"name": "Disabled", "config": VibeConfig(enabled=False)},
        {"name": "Default Settings", "config": VibeConfig()},
        {
            "name": "Fast Processing",
            "config": VibeConfig(
                max_concurrent=10, timeout_seconds=10, temperature=0.2
            ),
        },
        {
            "name": "Conservative Processing",
            "config": VibeConfig(max_concurrent=1, timeout_seconds=60, temperature=0.0),
        },
    ]

    for config_demo in configs:
        print(f"\n--- {config_demo['name']} ---")
        print(f"Enabled: {config_demo['config'].enabled}")
        print(f"Max concurrent: {config_demo['config'].max_concurrent}")
        print(f"Timeout: {config_demo['config'].timeout_seconds}s")
        print(f"Temperature: {config_demo['config'].temperature}")
        print(f"System prompt length: {len(config_demo['config'].system_prompt)} chars")


async def demo_async_processing():
    """Demonstrate direct async processing of survey questions."""
    print("=" * 60)
    print("DEMO 5: Direct Async Vibe Processing")
    print("=" * 60)

    from qualtrics.vibe import VibeProcessor
    from edsl import Survey
    from edsl.questions import QuestionFreeText, QuestionMultipleChoice

    # Create a survey programmatically
    questions = [
        QuestionFreeText(
            question_name="name_question", question_text="whats ur name???"
        ),
        QuestionMultipleChoice(
            question_name="rating_question",
            question_text="rate our svc",
            question_options=["bad", "ok", "good"],
        ),
    ]

    original_survey = Survey(questions)

    print("--- Original Survey ---")
    for q in original_survey.questions:
        print(f"{q.question_name}: {q.question_text}")
        if hasattr(q, "question_options"):
            print(f"  Options: {q.question_options}")

    # Process with vibe
    vibe_config = VibeConfig(enabled=True, max_concurrent=2)
    processor = VibeProcessor(vibe_config)

    print("\n--- Processing with vibe (async) ---")
    enhanced_survey = await processor.process_survey(original_survey)

    print("--- Enhanced Survey ---")
    for q in enhanced_survey.questions:
        print(f"{q.question_name}: {q.question_text}")
        if hasattr(q, "question_options"):
            print(f"  Options: {q.question_options}")


def main():
    """Run all demonstrations."""
    print("QUALTRICS VIBE SYSTEM DEMONSTRATION")
    print("AI-Powered Question Enhancement")
    print()

    # Demo 1: Without vibe
    demo_without_vibe()

    print("\n" + "=" * 80 + "\n")

    # Demo 2: With vibe
    demo_with_vibe()

    print("\n" + "=" * 80 + "\n")

    # Demo 3: Custom prompt
    demo_custom_system_prompt()

    print("\n" + "=" * 80 + "\n")

    # Demo 4: Config options
    demo_vibe_config_options()

    print("\n" + "=" * 80 + "\n")

    # Demo 5: Async processing
    print("Note: Demo 5 (async processing) requires running in async context")
    print("Use: asyncio.run(demo_async_processing())")

    print("\n🎉 All demonstrations completed!")
    print("\nKey takeaways:")
    print("- Vibe processing can significantly improve question quality")
    print("- System prompts allow customization for different use cases")
    print("- Processing is asynchronous for better performance")
    print("- Fallback to original questions if vibe processing fails")
    print("- Configurable concurrency and timeout settings")


if __name__ == "__main__":
    main()
