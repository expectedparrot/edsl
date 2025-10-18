"""
Agent Blueprint Creator from Population Description

This macro creates an AgentBlueprint by identifying relevant dimensions for a
specified population (e.g., "Experienced Upwork freelancers").

The AgentBlueprint is created using the to_agent_blueprint() method, which internally
uses AgentBlueprint.from_scenario_list() to perform ETL operations on the LLM-generated
dimension data.

Alternative approaches for creating AgentBlueprints directly:
    
    # From explicit Dimension objects (cleanest, most control)
    from edsl.scenarios import AgentBlueprint, Dimension
    
    experience = Dimension(
        name="experience_level",
        description="Years of freelancing experience",
        values=["Beginner (0-1 years)", "Intermediate (2-5 years)", "Expert (5+ years)"]
    )
    specialization = Dimension(
        name="specialization", 
        description="Primary skill area",
        values=["Web development", "Mobile apps", "Data analysis", "Design"]
    )
    
    blueprint = AgentBlueprint.from_dimensions(experience, specialization, seed=42)
    
    # From a simple dictionary (quick prototyping)
    blueprint = AgentBlueprint.from_dimensions_dict({
        "experience_level": ["Beginner", "Intermediate", "Expert"],
        "specialization": ["Web dev", "Mobile", "Data", "Design"]
    }, seed=42)
"""

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText, QuestionNumerical


# Ask the model to identify relevant dimensions for the population
q_dimensions = QuestionList(
    question_name="dimensions",
    question_text="""What dimensions of a person would be most relevant for understanding
and differentiating members of this population: {{ scenario.population_description }}?

{% if scenario.additional_details %}
Additional context and focus areas: {{ scenario.additional_details }}
{% endif %}

Consider dimensions like demographics (age, gender, location), experience levels,
skills, motivations, work preferences, industry focus, etc. that would be meaningful
for this specific population.

Provide {{ scenario.num_dimensions }} dimensions that would be most valuable for
creating distinct personas within this group.""",
)

# For each dimension, ask for possible levels/values
q_levels = QuestionList(
    question_name="levels",
    question_text="""For this population: {{ scenario.population_description }}

One relevant dimension is: {{ scenario.dimensions }}

What are realistic and meaningful levels/values someone in this population could have for this dimension?

Provide 3-6 distinct levels that would create meaningful differentiation within this population.
For example:
- If dimension is "experience level": "Beginner (0-1 years)", "Intermediate (2-5 years)", "Expert (5+ years)"
- If dimension is "work preference": "Full-time contracts", "Part-time projects", "Hourly gigs"
- If dimension is "specialization": "Web development", "Mobile apps", "Data analysis", "Design"

Make the levels specific and relevant to {{ scenario.population_description }}.""",
)

# Ask for a concise machine-friendly dimension name
q_name = QuestionFreeText(
    question_name="dimension_name",
    question_text="""For this dimension: {{ scenario.dimensions }}

Provide a short snake_case identifier that captures the essence of this dimension.
Examples: experience_level, work_preference, specialization, location_type, rate_range

Return only the snake_case name.""",
)

# Ask for a brief description of the dimension
q_description = QuestionFreeText(
    question_name="dimension_description",
    question_text="""For this dimension: {{ scenario.dimensions }}

Provide a brief 1-2 sentence description explaining what this dimension represents
and why it's important for understanding {{ scenario.population_description }}.

Example: "Represents the freelancer's preferred working arrangement and commitment level,
which affects project selection and client relationships."

Keep it concise but informative.""",
)

# Build the jobs pipeline
jobs_object = (
    Survey([q_dimensions])
    .to_jobs()
    .select(
        "scenario.population_description",
        "scenario.additional_details",
        "scenario.num_dimensions",
        "answer.dimensions",
    )
    .expand("answer.dimensions")
    .to(Survey([q_levels, q_name, q_description]))
)

# Initial survey to collect user input
initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="population_description",
            question_text="Describe the population you want to create personas for (e.g., 'Experienced Upwork freelancers', 'Small business owners in tech', 'College students interested in sustainability')",
        ),
        QuestionNumerical(
            question_name="num_dimensions",
            question_text="How many dimensions should be used to characterize this population? (Recommended: 4-8)",
            min_value=2,
            max_value=15,
        ),
        QuestionFreeText(
            question_name="additional_details",
            question_text="(Optional) Any additional details about dimension focus, specific examples, or constraints you want to consider?",
        ),
    ]
)

# Output formatter to create AgentBlueprint
# Note: to_agent_blueprint() internally uses AgentBlueprint.from_scenario_list()
# which performs ETL operations to convert scenario data into Dimension objects.
# This is the appropriate method when dimensions are generated dynamically by LLMs.
output_formatter = (
    OutputFormatter(description="Agent Blueprint", output_type="edsl_object")
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .to_agent_blueprint(
        dimension_name_field="dimension_name",
        dimension_values_field="levels",
        dimension_description_field="dimension_description",
    )
)

agent_blueprint_table = (
    output_formatter.copy()
    .set_output_type("markdown")
    .table(tablefmt="github")
    .to_string()
)

macro = Macro(
    application_name="agent_blueprint_creator_from_population",
    display_name="Agent Blueprint Creator from Population",
    short_description="Create agent blueprints with defined traits.",
    long_description="This application helps create detailed agent blueprints by defining dimensions, traits, and characteristics for synthetic agents used in surveys and research studies.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "agent_blueprint": output_formatter,
        "markdown_table": agent_blueprint_table,
    },
    default_formatter_name="agent_blueprint",
)

if __name__ == "__main__":
    output = macro.output(
        params={
            "population_description": "Experienced Upwork freelancers",
            "num_dimensions": 8,
            "additional_details": """Focus on work preferences, skill specialization, and experience with different client types
        Should include details on country of residence and language proficiency and attitudes towards freelancing/Upwork.
        """,
        }
    )
    print(output)
