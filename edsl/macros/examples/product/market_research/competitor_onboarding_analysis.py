"""
Competitor Onboarding UX Analysis App

An EDSL app that researches and analyzes competitors' user onboarding processes.
Based on the OpenAI Academy prompt: "Research how 3 key competitors structure
their onboarding flow for new users. Include screenshots, key steps, and points
of friction or delight."
"""

import textwrap
from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionMultipleChoice, QuestionNumerical
from edsl.agents import Agent


# 1. Initial Survey - Collect parameters for onboarding analysis
initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="industry_or_product",
            question_text="What industry or product category should we analyze? (e.g., 'SaaS project management tools', 'mobile banking apps', 'e-commerce platforms')",
        ),
        QuestionFreeText(
            question_name="specific_competitors",
            question_text="List specific competitors to analyze (comma-separated). Leave blank to let the AI suggest competitors based on your industry.",
        ),
        QuestionNumerical(
            question_name="number_of_competitors",
            question_text="How many competitors should be analyzed?",
            min_value=2,
            max_value=5,
        ),
        QuestionMultipleChoice(
            question_name="analysis_focus",
            question_text="What aspect of onboarding should we focus on?",
            question_options=[
                "Overall user journey and flow",
                "Information collection and data gathering",
                "Feature introduction and education",
                "Activation and engagement tactics",
                "All aspects comprehensively",
            ],
        ),
    ]
)


# 2. Processing Agent - UX Research Expert
ux_research_agent = Agent(
    name="ux_research_expert",
    traits={
        "expertise": "UX research, competitive analysis, and onboarding optimization",
        "persona": textwrap.dedent(
            """
            You are a senior UX researcher with deep expertise in competitive analysis and
            user onboarding optimization. You understand user psychology, conversion funnels,
            and can identify friction points and moments of delight in user experiences.
            You provide detailed, actionable insights based on thorough analysis.
        """
        ),
    },
)


# 3. Competitor Research Question
research_competitors_question = QuestionFreeText(
    question_name="competitor_research",
    question_text=textwrap.dedent(
        """
        Research {{ scenario.number_of_competitors }} key competitors in {{ scenario.industry_or_product }}.

        {% if scenario.specific_competitors %}
        Focus on these specific competitors: {{ scenario.specific_competitors }}
        {% else %}
        Select the most relevant and well-known competitors in this space.
        {% endif %}

        For each competitor, analyze their onboarding flow focusing on: {{ scenario.analysis_focus }}.

        For each competitor, provide:
        1. Company name and brief description
        2. Key onboarding steps (step-by-step breakdown)
        3. Information they collect from users
        4. How they introduce features/value proposition
        5. Points of friction (where users might get stuck or confused)
        6. Points of delight (smooth, engaging, or clever experiences)
        7. Estimated time to complete onboarding
        8. Notable design patterns or techniques used

        Structure your analysis clearly with headers for each competitor.
    """
    ),
)


# 4. Comparative Analysis Question
comparative_analysis_question = QuestionFreeText(
    question_name="comparative_analysis",
    question_text=textwrap.dedent(
        """
        Based on your research of competitors' onboarding flows:
        {{ competitor_research.answer }}

        Provide a comparative analysis that includes:

        1. **Common Patterns**: What onboarding approaches do most competitors use?
        2. **Unique Differentiators**: What unique onboarding strategies stand out?
        3. **Friction Points**: What are the most common sources of user friction?
        4. **Best Practices**: What are the most effective onboarding techniques observed?
        5. **Opportunities**: Based on this analysis, what onboarding improvements or innovations could be pursued?

        Present this as a strategic analysis that could inform onboarding decisions.
    """
    ),
)


# 5. Actionable Recommendations Question
recommendations_question = QuestionFreeText(
    question_name="actionable_recommendations",
    question_text=textwrap.dedent(
        """
        Based on the competitive analysis:
        {{ comparative_analysis.answer }}

        And the original competitor research:
        {{ competitor_research.answer }}

        Provide 5-7 specific, actionable recommendations for improving onboarding in the {{ scenario.industry_or_product }} space.

        For each recommendation:
        - Describe the specific improvement
        - Explain which competitor(s) inspired this recommendation
        - Estimate the potential impact (high/medium/low)
        - Suggest implementation complexity (easy/medium/hard)
        - Provide any relevant metrics to track success

        Format as a numbered list with clear, implementable actions.
    """
    ),
)


# 6. Jobs Pipeline
onboarding_analysis_pipeline = Survey(
    [
        research_competitors_question,
        comparative_analysis_question,
        recommendations_question,
    ]
).by(ux_research_agent)


# 7. Output Formatters

# Comprehensive markdown report
comprehensive_report = (
    OutputFormatter(
        description="Comprehensive Onboarding Analysis Report", output_type="markdown"
    )
    .select(
        "scenario.industry_or_product",
        "answer.competitor_research",
        "answer.comparative_analysis",
        "answer.actionable_recommendations",
    )
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# Executive summary for quick review
executive_summary = (
    OutputFormatter(description="Executive Summary", output_type="markdown")
    .select(
        "scenario.industry_or_product",
        "answer.comparative_analysis",
        "answer.actionable_recommendations",
    )
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# Raw data for further analysis
raw_data_output = (
    OutputFormatter(description="Raw Analysis Data", output_type="table")
    .select("scenario.*", "answer.*")
    .table()
)


# 8. Complete App Instance
app = Macro(
    application_name="competitor_onboarding_analysis",
    display_name="Competitor Onboarding Analysis",
    short_description="Research and analyze competitors' user onboarding processes to identify best practices, friction points, and opportunities for improvement.",
    long_description="This application researches and analyzes competitors' user onboarding processes to identify best practices, friction points, and opportunities for improvement. It provides comprehensive competitive analysis with actionable insights for UX optimization.",
    initial_survey=initial_survey,
    jobs_object=onboarding_analysis_pipeline,
    output_formatters={
        "comprehensive": comprehensive_report,
        "summary": executive_summary,
        "raw": raw_data_output,
    },
    default_formatter_name="comprehensive",
)


# 9. Test Example
if __name__ == "__main__":
    # Test the app with sample parameters
    print("Running Competitor Onboarding Analysis App...")

    results = app.output(
        params={
            "industry_or_product": "SaaS project management tools",
            "specific_competitors": "Asana, Trello, Monday.com",
            "number_of_competitors": 3,
            "analysis_focus": "All aspects comprehensively",
        },
        verbose=True,
    )

    print("\n" + "=" * 50)
    print("COMPETITOR ONBOARDING ANALYSIS RESULTS")
    print("=" * 50)
    print(results)
