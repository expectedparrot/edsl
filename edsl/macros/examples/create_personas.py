"""
Persona Generator

This macro generates synthetic personas by analyzing survey questions and
creating an AgentBlueprint with appropriate dimensions and trait levels.

The AgentBlueprint is created using the to_agent_blueprint() method, which internally
uses AgentBlueprint.from_scenario_list() to perform ETL operations on the LLM-generated
dimension data, including probability weights for each level.

Alternative approaches for creating AgentBlueprints directly:
    
    # From explicit Dimension objects with weights
    from edsl.scenarios import AgentBlueprint, Dimension
    
    age = Dimension(
        name="age_range",
        description="Age bracket of respondent",
        values=[
            ("18-24", 0.15),    # (value, weight)
            ("25-34", 0.25),
            ("35-44", 0.25),
            ("45-54", 0.20),
            ("55+", 0.15)
        ]
    )
    
    blueprint = AgentBlueprint.from_dimensions(age, seed=42)
"""

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter, SurveyAttachmentFormatter

from edsl.surveys import Survey
from edsl.questions import (
    QuestionList,
    QuestionFreeText,
    QuestionEDSLObject,
    QuestionNumerical,
)

import textwrap

# Prompt the model for dimensions given each survey question
q = QuestionList(
    question_name="dimensions",
    question_text=textwrap.dedent(
        """\
What dimensions of a person would you need to know to predict how they  would answer this question: 
{{ scenario.question_text }}?
These dimensions should be thinks that could have 'levels' or 'values' that someone could have.
E.g., age, gender, education, income, location, industry, company size, etc.
Return only the dimensions that are relevant to the question.
"""
    ),
)

# For each proposed dimension, ask for possible levels
q_levels = QuestionList(
    question_name="levels",
    question_text="""We are constructing a persona for someone who answers this question: 
<question>
{{ scenario.question_text }}
</question>

One relevant dimension of a person is: 
<dimension>
{{ scenario.dimensions }}.
</dimension>

What are valid levels/values someone could have for this dimension?

For example, if the dimension is "age", the levels could be "18-24", "25-34", "35-44", "45-54", "55-64", "65+".
For example, if the dimension is "gender", the levels could be "male", "female", "other".
For example, if the dimension is "education", the levels could be "high school", "bachelor's degree", "master's degree", "doctorate".
For example, if the dimension is "income", the levels could be "0-10000", "10000-20000", "20000-30000", "30000-40000", "40000-50000", "50000+".
For example, if the dimension is "location", the levels could be "United States", "Canada", "United Kingdom", "Australia", "Other".
For example, if the dimension is "industry", the levels could be "technology", "finance", "healthcare", "education", "other".
For example, if the dimension is "company size", the levels could be "1-10", "11-50", "51-200", "201-1000", "1001-5000", "5001+".
""",
)

from edsl.questions import QuestionFreeText

q_description = QuestionFreeText(
    question_name="dimension_description",
    question_text="""We are constructing a persona for someone who answers this question: 
<question>
{{ scenario.question_text }}
</question>

One relevant dimension of a person is: 
<dimension>
{{ scenario.dimensions }}.
</dimension>

Provide a short description of this dimension, as it relates to the question.
""",
)

q_probs = QuestionList(
    question_name="probs",
    question_text="""For this dimension:
<dimension>
{{ scenario.dimensions }}.
</dimension>
The associated levels are: {{ levels.answer }}.

You MUST estimate the probability (as a decimal number between 0 and 1) that a random person would have each level for this dimension.

CRITICAL: Return ONLY numeric decimal values (like 0.5, 0.25, 0.1), NOT letters or categories.
The probabilities should roughly sum to 1.0 and be in the SAME ORDER as the levels listed above.

Examples of CORRECT responses:
- If levels are ['male', 'female'], return [0.5, 0.5]
- If levels are ['18-24', '25-34', '35-44', '45-54', '55+'], return [0.15, 0.25, 0.25, 0.20, 0.15]
- If levels are ['high school', 'bachelor', 'master', 'doctorate'], return [0.30, 0.45, 0.20, 0.05]

Return a list of NUMERIC decimals only, no text explanations.
""",
)

# Ask for a concise machine-friendly dimension name
q_name = QuestionFreeText(
    question_name="dimension_name",
    question_text="""For this dimension:
<dimension>
{{ scenario.dimensions }}.
</dimension>

Provide a short snake_case identifier (e.g., age_range, gender, education). Return only the name.""",
)

# Build the jobs pipeline: propose dimensions per question, expand, then ask levels and a name
jobs_object = (
    Survey([q])
    .to_jobs()
    .select("scenario.question_text", "answer.dimensions")
    .expand("answer.dimensions")
    .to(Survey([q_levels, q_name, q_probs, q_description]))
)

"""
Expected inputs (via initial_survey):
- A Survey to analyze (as an EDSL object)
- n: number of personas to generate
"""

initial_survey = Survey(
    [
        QuestionEDSLObject(
            question_name="input_survey",
            question_text="Provide the Survey to analyze",
            expected_object_type="Survey",
        ),
        QuestionNumerical(
            question_name="n",
            question_text="How many personas should be generated?",
        ),
    ]
)

# Output an AgentBlueprint using the answers
# Note: to_agent_blueprint() internally uses AgentBlueprint.from_scenario_list()
# This method handles the ETL process including probability weights (dimension_probs_field)
# which are used for weighted sampling when creating agents.

# Debug formatter to see the data before agent_blueprint conversion
debug_scenario_list = (
    OutputFormatter(
        description="Debug ScenarioList (before agent_blueprint)",
        output_type="ScenarioList",
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
)

agent_blueprint = (
    OutputFormatter(description="Agent Blueprint", output_type="AgentBlueprint")
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .to_agent_blueprint(
        dimension_name_field="dimension_name",
        dimension_values_field="levels",
        dimension_description_field="dimension_description",
        dimension_probs_field="probs",
        seed="1234",
    )
)

agent_list = agent_blueprint.copy().create_agent_list(
    n="{{params.n|int}}", strategy="probability", unique=True
)

agent_list_markdown = (
    agent_list.copy().set_output_type("markdown").table(tablefmt="github").to_string()
)

agent_list_rich = agent_list.copy().set_output_type("rich").table(tablefmt="rich")

# Markdown formatter that displays the persona dimensions and levels as a table
markdown_formatter = (
    OutputFormatter(
        description="Persona Dimensions Preview (Markdown)", output_type="markdown"
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .select("question_text", "dimension_name", "levels")
    .table(tablefmt="github")
    .to_string()
)

raw = OutputFormatter(description="Raw results", output_type="Results")

# Debug table to inspect the data
debug_table = (
    OutputFormatter(description="Debug Table (dimension data)", output_type="markdown")
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .select("dimension_name", "levels", "probs", "dimension_description")
    .table(tablefmt="github")
    .to_string()
)

# Debug: show all fields in the scenario list
debug_fields = (
    OutputFormatter(
        description="Debug: All fields in ScenarioList", output_type="markdown"
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .table(tablefmt="github")
    .to_string()
)

# Debug: Validate probs are numeric
debug_probs_validation = (
    OutputFormatter(
        description="Debug: Validate probs field types", output_type="ScenarioList"
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
)

macro = Macro(
    application_name="create_personas",
    display_name="Persona Generator",
    short_description="A persona generator.",
    long_description="This application generates synthetic personas by analyzing survey questions, identifying relevant dimensions, and creating agent blueprints with appropriate trait levels.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "agent_list": agent_list,
        "agent_list_markdown": agent_list_markdown,
        "agent_blueprint": agent_blueprint,
        "agent_list_rich": agent_list_rich,
        "debug_scenario_list": debug_scenario_list,
        "debug_table": debug_table,
        "debug_fields": debug_fields,
        "debug_probs_validation": debug_probs_validation,
        "raw": raw,
    },
    default_formatter_name="agent_blueprint",
    attachment_formatters=[
        # Convert the passed Survey into a ScenarioList and attach as scenarios
        SurveyAttachmentFormatter(
            description="Survey->ScenarioList", output_type="ScenarioList"
        ).to_scenario_list(
            remove_jinja2_syntax=True
        )
    ],
)

if __name__ == "__main__":
    from edsl import Survey

    # survey = Survey.pull("7e80e0dd-5d8a-4f91-afef-c06e9756c0a2")
    survey = Survey.pull("5cde9b3b-3548-418c-9500-074103a13eef")
    output = macro.output(
        params={
            "input_survey": survey,
            "n": 10,
        }
    )

    # Validate probs are numeric before trying to create agent_blueprint
    print("\n=== Validating probs field ===")
    sl = output.debug_probs_validation
    for i, scenario in enumerate(sl):
        dim_name = scenario.get("dimension_name", f"unknown_{i}")
        probs = scenario.get("probs", [])
        levels = scenario.get("levels", [])

        print(f"\nDimension: {dim_name}")
        print(
            f"  Levels ({len(levels)}): {levels[:3]}..."
            if len(levels) > 3
            else f"  Levels: {levels}"
        )
        print(
            f"  Probs ({len(probs)}): {probs[:3]}..."
            if len(probs) > 3
            else f"  Probs: {probs}"
        )

        # Check if all probs are numeric
        non_numeric = [p for p in probs if not isinstance(p, (int, float))]
        if non_numeric:
            print(f"  ⚠️  WARNING: Found non-numeric probs: {non_numeric}")

        # Check if lengths match
        if len(probs) != len(levels):
            print(
                f"  ⚠️  WARNING: Mismatch - {len(levels)} levels but {len(probs)} probs"
            )

    print("\n=== Creating agent blueprint ===")
    print(output.agent_list_rich)
