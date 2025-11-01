import textwrap
from edsl.macros import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionList
from edsl.agents import Agent
from edsl.scenarios import ScenarioList

# 1. Initial Survey
initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="product_name",
            question_text="What product would you like to analyze for conjoint analysis?",
        )
    ]
)

# 2. Agent
conjoint_analyst = Agent(
    name="conjoint_analyst",
    traits={
        "expertise": "conjoint analysis, market research, product attributes",
        "analytical_skills": "systematic decomposition of products into components and levels",
    },
)

# 3. Multi-stage analysis questions
# Stage 1: Get components
components_question = QuestionList(
    question_name="components",
    question_text=textwrap.dedent(
        """
    For the product "{{ scenario.product_name }}", identify the key components/attributes
    that would be relevant for a conjoint analysis. These should be the main features
    or characteristics that consumers would consider when making a purchase decision.

    Return a list of 4-8 component names (e.g., ["price", "brand", "color", "size"]).
    Each component should be a short, clear attribute name.
    """
    ),
)

# Stage 2: Get potential levels for each component
levels_question = QuestionList(
    question_name="potential_levels",
    question_text=textwrap.dedent(
        """
    For the product "{{ scenario.product_name }}" and its component "{{ scenario.component }}",
    identify all the potential levels (options) that this component could have in a conjoint study.

    Consider:
    - Current market options
    - Realistic alternatives consumers might choose between
    - Levels that would create meaningful trade-offs

    Return a list of 3-5 levels for this component.
    Example for "price": ["$50", "$75", "$100", "$125"]
    Example for "color": ["Black", "White", "Blue", "Red"]

    Component: {{ scenario.component }}
    """
    ),
)

# Stage 3: Identify current level
current_level_question = QuestionFreeText(
    question_name="current_level",
    question_text=textwrap.dedent(
        """
    For the product "{{ scenario.product_name }}" and its component "{{ scenario.component }}",
    what is the current/default level for this specific product?

    Potential levels for this component are: {{ scenario.potential_levels }}

    Choose the most representative current level from those potential levels.
    Return just the level value (e.g., "$75" or "Blue" or "Medium").

    Component: {{ scenario.component }}
    Product: {{ scenario.product_name }}
    """
    ),
)

# 4. Complex jobs pipeline
# This follows the pattern from auto_survey.py
job = (
    Survey([components_question])
    .to_jobs()
    .by(conjoint_analyst)
    .select("answer.components", "scenario.product_name")
    .to_scenario_list()
    .expand("components")
    .rename({"components": "component"})
    .to(Survey([levels_question]).by(conjoint_analyst))
    .select("answer.potential_levels", "scenario.component", "scenario.product_name")
    .to(Survey([current_level_question]).by(conjoint_analyst))
)

# 5. Output formatters
table_formatter = (
    OutputFormatter(name="Dimensions and Levels Table", output_type="table")
    .select("scenario.component", "scenario.potential_levels", "answer.current_level")
    .rename(
        {
            "scenario.component": "Component",
            "scenario.potential_levels": "Levels",
            "answer.current_level": "Current Level",
        }
    )
    .table()
)

structured_formatter = (
    OutputFormatter(name="Structured Results", output_type="ScenarioList")
    .select(
        "scenario.component",
        "scenario.potential_levels",
        "answer.current_level",
        "scenario.product_name",
    )
    .to_scenario_list()
)

scenario_list_formatter = (
    OutputFormatter(name="Conjoint Scenario List", output_type="ScenarioList")
    .select("scenario.component", "scenario.potential_levels", "answer.current_level")
    .rename(
        {
            "scenario.component": "attribute",
            "scenario.potential_levels": "levels",
            "answer.current_level": "current_level",
        }
    )
    .to_scenario_list()
)

markdown_formatter = (
    OutputFormatter(name="Analysis Preview (Markdown)", output_type="markdown")
    .select("scenario.component", "scenario.potential_levels", "answer.current_level")
    .rename(
        {
            "scenario.component": "Component",
            "scenario.potential_levels": "Levels",
            "answer.current_level": "Current Level",
        }
    )
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# 6. Complete Macro
macro = Macro(
    application_name="conjoint_analysis",
    display_name="Conjoint Analysis",
    short_description="Perform conjoint analysis on preferences.",
    long_description="This application conducts conjoint analysis to understand how respondents value different attributes of a product or service by analyzing trade-offs in preference judgments.",
    initial_survey=initial_survey,
    jobs_object=job,
    output_formatters={
        "scenario_list": scenario_list_formatter,
        "table": table_formatter,
        "structured": structured_formatter,
        "markdown": markdown_formatter,
    },
    default_formatter_name="scenario_list",
)

# 7. Test with example
if __name__ == "__main__":
    result = macro.output(
        params={
            "product_name": """
    Expected Parrot helps teams simulate their customers to improve pricing and other critical business decisions.
    The company offers:
    - EDSL: An open-source package for designing AI agents and simulating surveys and experiments with them
    - Polly: A no-code UI for running simulations interactively
    - Storage and versioning of results
    - Custom notebooks and templates for pricing and other experiments
    - Support designing agents representing your customers or stakeholders
         """
        },
        verbose=True,
    )
    print(result)
