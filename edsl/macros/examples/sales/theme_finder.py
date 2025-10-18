"""
Theme Finder App for EDSL

A comprehensive app that extracts themes from free text responses using an iterative
LLM-based approach with generation, consolidation, validation, and refinement phases.
"""

import textwrap
from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import (
    QuestionList,
    QuestionFreeText,
    QuestionEDSLObject,
    QuestionCheckBox,
)
from edsl.agents import Agent
from edsl import ScenarioList


# =============================================================================
# Phase 1: Initial Theme Generation
# =============================================================================


def create_theme_generation_app():
    """
    Takes a ScenarioList with 'response_text' field and generates initial themes
    from chunks of responses.

    Input: ScenarioList with 'response_text' field
    Output: ScenarioList with generated themes (label, description, indicators)
    """

    initial_survey = Survey(
        [
            QuestionEDSLObject(
                question_name="responses",
                question_text="Provide the responses to analyze",
                expected_object_type="ScenarioList",
            )
        ]
    )

    # Question to generate themes from a chunk of responses
    theme_generation_question = QuestionList(
        question_name="generated_themes",
        question_text=textwrap.dedent(
            """
        Analyze the following responses and identify the main themes present.
        For each theme, provide a dictionary with:
        - 'label': A concise, descriptive theme name (2-4 words)
        - 'description': A brief explanation of what this theme captures
        - 'indicators': Key phrases or concepts that signal this theme

        Responses to analyze:
        {{ scenario.response_chunk }}

        Generate 5-8 distinct themes that capture the key ideas expressed.
        Return as a list of dictionaries.

        Example format:
        [
            {
                "label": "Cost concerns",
                "description": "Responses expressing worry about price or affordability",
                "indicators": ["expensive", "too much", "can't afford", "price"]
            },
            ...
        ]
        """
        ),
    )

    # Create chunks from the input scenarios and process in parallel
    jobs_object = Survey([theme_generation_question]).to_jobs()

    # Output formatter: collect all themes into a list
    theme_list_formatter = (
        OutputFormatter(description="Generated Themes")
        .select("answer.generated_themes")
        .to_list()
    )

    return Macro(
        application_name="theme_generator",
        display_name="Theme Generator",
        short_description="Generates initial themes from response chunks.",
        long_description="This application analyzes chunks of text responses and generates initial themes by identifying patterns and common topics.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"themes": theme_list_formatter},
        default_formatter_name="themes",
    )


# =============================================================================
# Phase 2: Theme Consolidation
# =============================================================================


def create_theme_consolidation_app():
    """
    Takes a list of themes and consolidates them to target number.

    Input: List of theme dictionaries
    Output: Consolidated list of themes
    """

    initial_survey = Survey(
        [
            QuestionFreeText(
                question_name="themes_json",
                question_text="Provide themes as JSON string",
            ),
            QuestionFreeText(
                question_name="target_n",
                question_text="Target number of themes",
            ),
        ]
    )

    consolidation_question = QuestionList(
        question_name="consolidated_themes",
        question_text=textwrap.dedent(
            """
        You have many candidate themes that need consolidation to approximately {{ scenario.target_n }} themes.

        Current themes:
        {{ scenario.themes_json }}

        Task:
        1. Identify which themes are similar or overlapping
        2. Merge similar themes into unified themes
        3. Ensure each merged theme is distinct from others
        4. Aim for approximately {{ scenario.target_n }} final themes

        For each consolidated theme provide a dictionary with:
        - 'label': Concise descriptive name (2-4 words)
        - 'description': Clear explanation of what this theme captures
        - 'indicators': Key phrases/concepts that signal this theme
        - 'merged_from': List of original theme labels that were combined (if any)

        Return as a list of dictionaries.
        """
        ),
    )

    jobs_object = Survey([consolidation_question]).to_jobs()

    consolidated_formatter = (
        OutputFormatter(description="Consolidated Themes")
        .select("answer.consolidated_themes")
        .to_list()
        .__getitem__(0)
    )

    return Macro(
        application_name="theme_consolidator",
        display_name="Theme Consolidator",
        short_description="Consolidates themes to target number.",
        long_description="This application takes a list of candidate themes and consolidates them to a target number by merging similar themes and ensuring distinctiveness.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"consolidated": consolidated_formatter},
        default_formatter_name="consolidated",
    )


# =============================================================================
# Phase 3: Response Labeling
# =============================================================================


def create_labeling_app(theme_labels=None):
    """
    Labels responses with applicable themes using checkboxes.

    Input: ScenarioList with 'response_text' and theme_labels for checkboxes
    Output: ScenarioList with 'identified_themes' field added

    Args:
        theme_labels: List of theme label strings to use as checkbox options.
                     If None, will use a generic question asking for theme labels.
    """

    initial_survey = Survey(
        [
            QuestionEDSLObject(
                question_name="responses",
                question_text="Provide responses to label",
                expected_object_type="ScenarioList",
            ),
            QuestionFreeText(
                question_name="themes_guide",
                question_text="Provide the theme guide as formatted text",
            ),
        ]
    )

    # If theme_labels provided, use QuestionCheckBox for better UX
    # Otherwise fall back to QuestionList
    if theme_labels:
        labeling_question = QuestionCheckBox(
            question_name="identified_themes",
            question_text=textwrap.dedent(
                """
            Select ALL themes that apply to this response.

            Response: "{{ scenario.response_text }}"

            Theme Descriptions:
            {{ scenario.themes_guide }}

            Select all that apply (can be 0, 1, or multiple):
            """
            ),
            question_options=theme_labels,
            min_selections=0,  # Allow no selections
        )
    else:
        # Fallback to QuestionList when theme_labels not known in advance
        labeling_question = QuestionList(
            question_name="identified_themes",
            question_text=textwrap.dedent(
                """
            Label the following response with ALL applicable themes.

            Response: "{{ scenario.response_text }}"

            Available Themes:
            {{ scenario.themes_guide }}

            Which themes are present in this response?
            - Return a list of theme labels (just the labels, not full dictionaries)
            - Include all themes that clearly apply
            - Return an empty list [] if no themes apply
            - A response can have 0, 1, or multiple themes

            Return format: ["theme1", "theme2", ...]
            """
            ),
        )

    # Process each response in the ScenarioList in parallel
    jobs_object = Survey([labeling_question]).to_jobs()

    # Return the original ScenarioList with the new field added
    labeled_formatter = (
        OutputFormatter(description="Labeled Responses")
        .select("scenario.*", "answer.identified_themes")
        .to_scenario_list()
    )

    return Macro(
        application_name="response_labeler",
        display_name="Response Labeler",
        short_description="Labels responses with themes.",
        long_description="This application labels individual responses with applicable themes from a provided theme set, enabling theme-based analysis of text data.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"labeled": labeled_formatter},
        default_formatter_name="labeled",
    )


# =============================================================================
# Phase 4: Theme Validation & Refinement Analysis
# =============================================================================


def create_theme_validation_app():
    """
    Analyzes theme usage and suggests refinements.

    Input: Labeled responses ScenarioList
    Output: Dictionary with usage statistics and refinement suggestions
    """

    initial_survey = Survey(
        [
            QuestionEDSLObject(
                question_name="labeled_responses",
                question_text="Provide labeled responses",
                expected_object_type="ScenarioList",
            ),
            QuestionFreeText(
                question_name="themes_json",
                question_text="Provide themes as JSON",
            ),
        ]
    )

    validation_question = QuestionFreeText(
        question_name="validation_report",
        question_text=textwrap.dedent(
            """
        Analyze the theme distribution and suggest refinements.

        Theme usage statistics:
        {{ scenario.theme_stats }}

        Sample of responses for each theme:
        {{ scenario.theme_samples }}

        Analyze:
        1. Identify underused themes (< 2% usage) - suggest merge or remove
        2. Identify overused themes (> 30% usage) - suggest split into sub-themes
        3. Identify themes that always co-occur - suggest merge
        4. Assess if responses without themes need a new theme

        Provide a structured report with:
        - Overall assessment (good/needs refinement)
        - Specific actions to take (merge X with Y, split Z into A and B, etc.)
        - Estimated final theme count after refinements

        Return as a detailed text report.
        """
        ),
    )

    jobs_object = Survey([validation_question]).to_jobs()

    report_formatter = (
        OutputFormatter(description="Validation Report")
        .select("answer.validation_report")
        .to_list()
        .__getitem__(0)
    )

    return Macro(
        application_name="theme_validator",
        display_name="Theme Validator",
        short_description="Validates themes and suggests refinements.",
        long_description="This application analyzes theme usage patterns and suggests refinements such as merging underused themes or splitting overused ones.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"report": report_formatter},
        default_formatter_name="report",
    )


# =============================================================================
# Phase 5: Theme Refinement Execution
# =============================================================================


def create_theme_refinement_app():
    """
    Executes refinement actions on themes based on validation report.

    Input: Current themes and refinement actions
    Output: Refined themes
    """

    initial_survey = Survey(
        [
            QuestionFreeText(
                question_name="themes_json",
                question_text="Current themes as JSON",
            ),
            QuestionFreeText(
                question_name="refinement_actions",
                question_text="Refinement actions from validation",
            ),
            QuestionFreeText(
                question_name="labeled_samples",
                question_text="Sample labeled responses for context",
            ),
        ]
    )

    refinement_question = QuestionList(
        question_name="refined_themes",
        question_text=textwrap.dedent(
            """
        Execute the following refinement actions on the themes.

        Current themes:
        {{ scenario.themes_json }}

        Refinement actions needed:
        {{ scenario.refinement_actions }}

        Sample labeled responses for context:
        {{ scenario.labeled_samples }}

        Task:
        1. Merge underused themes as suggested
        2. Split overused themes into specific sub-themes
        3. Remove themes that aren't adding value
        4. Ensure all theme labels remain clear and distinct

        Return the refined list of themes as dictionaries with:
        - 'label': Theme name
        - 'description': What it captures
        - 'indicators': Key signals

        Return as a list of dictionaries.
        """
        ),
    )

    jobs_object = Survey([refinement_question]).to_jobs()

    refined_formatter = (
        OutputFormatter(description="Refined Themes")
        .select("answer.refined_themes")
        .to_list()
        .__getitem__(0)
    )

    return Macro(
        application_name="theme_refiner",
        display_name="Theme Refiner",
        short_description="Refines themes based on usage analysis.",
        long_description="This application executes refinement actions on themes based on validation feedback, merging or splitting themes to improve the overall theme set quality.",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"refined": refined_formatter},
        default_formatter_name="refined",
    )


# =============================================================================
# Main Theme Finder App
# =============================================================================


def create_theme_finder_app():
    """
    Main orchestrator app that takes responses and generates themes.

    This is a simplified version that does one-pass theme generation.
    To label responses, use the labeling app separately.

    Input: ScenarioList with 'response_text' field
    Output: List of theme dictionaries
    """

    initial_survey = Survey(
        [
            QuestionEDSLObject(
                question_name="responses",
                question_text="Provide the responses to analyze as a ScenarioList with 'response_text' field",
                expected_object_type="ScenarioList",
            ),
            QuestionFreeText(
                question_name="target_theme_count",
                question_text="Target number of themes (default: 10)",
            ),
        ]
    )

    # Generate candidate themes from each response
    candidate_theme_question = QuestionList(
        question_name="candidate_themes",
        question_text=textwrap.dedent(
            """
        Analyze this response and identify 2-3 themes it relates to.

        Response: "{{ scenario.response_text }}"

        For each theme provide a dictionary with:
        - 'label': Concise theme name (2-4 words)
        - 'description': Brief explanation
        - 'indicators': Key phrases/words that signal this theme

        Think broadly - similar themes will be consolidated later.
        Return as a list of 2-3 theme dictionaries.

        Example format:
        [
            {"label": "Cost concerns", "description": "Worry about price", "indicators": "expensive, costly, price"},
            {"label": "Quality satisfaction", "description": "Positive quality feedback", "indicators": "well-made, durable, quality"}
        ]
        """
        ),
    )

    agent = Agent(
        name="theme_analyst",
        traits={
            "role": "Expert qualitative researcher specializing in thematic analysis",
            "skills": "Pattern recognition, semantic analysis, theme identification",
        },
    )

    # Process all responses in parallel to generate candidate themes
    jobs_object = Survey([candidate_theme_question]).to_jobs().by(agent)

    # Collect all candidate themes
    candidate_formatter = (
        OutputFormatter(description="Candidate Themes")
        .select("answer.candidate_themes")
        .expand("answer.candidate_themes")
        .to_scenario_list()
    )

    return Macro(
        application_name="theme_finder",
        display_name="Theme Finder",
        short_description="Generates candidate themes from all responses in parallel",
        long_description="Generates candidate themes from all responses in parallel",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"candidates": candidate_formatter},
        default_formatter_name="candidates",
        default_params={"target_theme_count": "10"},
    )


# =============================================================================
# Complete Multi-Stage Theme Finder
# =============================================================================


def create_complete_theme_finder():
    """
    Creates a complete theme finder that processes responses through all stages.
    This uses EDSL's parallel processing capabilities.
    """

    initial_survey = Survey(
        [
            QuestionEDSLObject(
                question_name="responses",
                question_text="ScenarioList with 'response_text' field",
                expected_object_type="ScenarioList",
            ),
            QuestionFreeText(
                question_name="target_themes",
                question_text="Target number of themes",
            ),
            QuestionFreeText(
                question_name="chunk_size",
                question_text="Chunk size for parallel processing",
            ),
        ]
    )

    # Multi-stage questions that will process in parallel

    # Stage 1: Generate themes from response chunks (parallel per chunk)
    chunk_theme_gen = QuestionList(
        question_name="chunk_themes",
        question_text=textwrap.dedent(
            """
        Analyze this chunk of responses and generate 5-8 themes.

        Responses (chunk {{ scenario.chunk_id }}):
        {{ scenario.response_chunk }}

        Return themes as list of dicts with label, description, indicators.
        """
        ),
    )

    # Stage 2: Consolidate all generated themes
    consolidate = QuestionList(
        question_name="consolidated_themes",
        question_text=textwrap.dedent(
            """
        Consolidate these themes to approximately {{ scenario.target_themes }} themes.

        Generated themes:
        {{ scenario.all_generated_themes }}

        Merge similar themes, ensure distinctiveness.
        Return as list of dicts with label, description, indicators.
        """
        ),
    )

    # Stage 3: Label each response (parallel per response)
    label_response = QuestionList(
        question_name="identified_themes",
        question_text=textwrap.dedent(
            """
        Label this response with applicable themes.

        Response: "{{ scenario.response_text }}"

        Themes:
        {{ scenario.theme_guide }}

        Return list of applicable theme labels: ["label1", "label2"]
        """
        ),
    )

    # Create analyst agent
    analyst = Agent(
        name="theme_analyst",
        traits={
            "expertise": "Qualitative research, thematic analysis, content analysis",
            "approach": "Systematic, iterative, data-driven",
        },
    )

    # Build the jobs pipeline
    # This processes chunks in parallel, consolidates, then labels in parallel
    jobs_object = (
        Survey([chunk_theme_gen])
        .to_jobs()
        .by(analyst)
        .select("answer.chunk_themes")
        .to_scenario_list()
        .expand("answer.chunk_themes")
        .to_list()
        # TODO: Feed to consolidation step
        # TODO: Then label all responses in parallel
    )

    labeled_formatter = (
        OutputFormatter(description="Labeled Responses")
        .select("scenario.response_text", "answer.identified_themes")
        .to_scenario_list()
    )

    return Macro(
        application_name="complete_theme_finder",
        display_name="Complete Theme Finder",
        short_description="Full theme extraction pipeline with generation, consolidation, and labeling",
        long_description="Full theme extraction pipeline with generation, consolidation, and labeling",
        initial_survey=initial_survey,
        jobs_object=jobs_object,
        output_formatters={"labeled": labeled_formatter},
        default_formatter_name="labeled",
        default_params={"target_themes": "10", "chunk_size": "50"},
    )


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    import json

    # Example: Create sample responses
    sample_responses = [
        "The product is too expensive for what it offers",
        "I love the quality and design, very satisfied",
        "Shipping took way too long, very disappointed",
        "Customer service was extremely helpful",
        "The features are confusing and hard to use",
        "Great value for money, highly recommend",
        "Poor quality materials, fell apart quickly",
        "Easy to use right out of the box",
        "Website checkout process was frustrating",
        "Exceeded my expectations in every way",
    ]

    responses_sl = ScenarioList.from_list("response_text", sample_responses)

    print("=" * 70)
    print("THEME FINDER PIPELINE DEMO")
    print("=" * 70)

    # =========================================================================
    # STEP 1: Generate candidate themes from all responses (in parallel)
    # =========================================================================
    print("\n[STEP 1] Generating candidate themes from all responses...")

    theme_generator = create_theme_finder_app()
    candidate_themes_output = theme_generator.output(
        {"responses": responses_sl, "target_theme_count": "5"}
    )

    # Access the candidates formatter result (which is a ScenarioList)
    candidate_themes_sl = candidate_themes_output.candidates
    print(
        f"✓ Generated {len(candidate_themes_sl)} candidate themes from {len(responses_sl)} responses"
    )

    # Convert ScenarioList to list of dicts for consolidation
    candidate_themes_list = [dict(s) for s in candidate_themes_sl]

    # =========================================================================
    # STEP 2: Consolidate candidate themes into final theme set
    # =========================================================================
    print("\n[STEP 2] Consolidating themes...")

    consolidator = create_theme_consolidation_app()

    # Prepare themes as JSON string and add metadata
    themes_json = json.dumps(candidate_themes_list, indent=2)

    consolidated_themes_output = consolidator.output(
        {"themes_json": themes_json, "target_n": "5"}
    )

    # Access the consolidated formatter result
    consolidated_themes = consolidated_themes_output.consolidated

    print(f"✓ Consolidated to {len(consolidated_themes)} final themes")
    print("\nFinal Themes:")
    for i, theme in enumerate(consolidated_themes, 1):
        print(
            f"  {i}. {theme.get('label', 'Unnamed')}: {theme.get('description', 'No description')}"
        )

    # =========================================================================
    # STEP 3: Create theme guide for labeling
    # =========================================================================
    print("\n[STEP 3] Preparing theme guide...")

    def format_themes_as_guide(themes):
        """Format themes into a readable guide for the labeling LLM."""
        guide_lines = []
        for i, theme in enumerate(themes, 1):
            guide_lines.append(f"{i}. {theme['label']}")
            guide_lines.append(f"   Description: {theme['description']}")
            guide_lines.append(f"   Indicators: {theme['indicators']}")
            guide_lines.append("")
        return "\n".join(guide_lines)

    themes_guide = format_themes_as_guide(consolidated_themes)

    # Extract theme labels for checkbox options
    theme_labels = [theme["label"] for theme in consolidated_themes]
    print(f"✓ Theme guide prepared with labels: {theme_labels}")

    # =========================================================================
    # STEP 4: Label all responses with final themes (in parallel)
    # =========================================================================
    print("\n[STEP 4] Labeling all responses with themes...")

    # Create labeler with theme labels for QuestionCheckBox
    labeler = create_labeling_app(theme_labels=theme_labels)

    # Add the theme guide to each scenario in the responses
    # We need to attach the guide as a scenario field
    responses_with_guide_sl = responses_sl.add_value("themes_guide", themes_guide)

    labeled_responses_output = labeler.output(
        {"responses": responses_with_guide_sl, "themes_guide": themes_guide}
    )

    # Access the labeled formatter result (which is a ScenarioList)
    labeled_responses_sl = labeled_responses_output.labeled

    print(f"✓ Labeled {len(labeled_responses_sl)} responses")

    # =========================================================================
    # FINAL RESULTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("FINAL LABELED RESPONSES")
    print("=" * 70)

    for i, scenario in enumerate(labeled_responses_sl, 1):
        response_text = scenario.get("response_text", "")
        themes = scenario.get("identified_themes", [])

        print(f'\n{i}. "{response_text}"')
        if themes:
            print(f"   Themes: {', '.join(themes)}")
        else:
            print("   Themes: (none)")

    # =========================================================================
    # STATISTICS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STATISTICS")
    print("=" * 70)

    # Count theme usage
    theme_counts = {}
    total_labels = 0
    for scenario in labeled_responses_sl:
        themes = scenario.get("identified_themes", [])
        total_labels += len(themes)
        for theme in themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    print(f"\nTotal responses: {len(labeled_responses_sl)}")
    print(f"Total theme labels applied: {total_labels}")
    print(
        f"Average themes per response: {total_labels / len(labeled_responses_sl):.2f}"
    )

    print("\nTheme usage:")
    for theme, count in sorted(theme_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(labeled_responses_sl)) * 100
        print(f"  {theme}: {count} ({pct:.1f}%)")

    # Count responses with no themes
    unlabeled = sum(1 for s in labeled_responses_sl if not s.get("identified_themes"))
    if unlabeled > 0:
        print(f"\nResponses with no themes: {unlabeled}")

    print("\n" + "=" * 70)
    print("✓ Pipeline complete! Final result: labeled_responses_sl")
    print("=" * 70)
