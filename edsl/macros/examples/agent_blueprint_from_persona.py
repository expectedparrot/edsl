"""
Agent Blueprint Creator from Persona

This macro extracts dimensions from an existing persona description and creates
an AgentBlueprint that can generate variations of similar personas.

The AgentBlueprint is created using the to_agent_blueprint() method, which internally
uses AgentBlueprint.from_scenario_list() to perform ETL operations on the LLM-generated
dimension data.

Alternative approaches for creating AgentBlueprints directly:
    
    # From explicit Dimension objects (cleanest)
    from edsl.scenarios import AgentBlueprint, Dimension
    
    politics = Dimension(name="politics", description="Political leaning", 
                        values=["left", "right", "center"])
    age = Dimension(name="age", description="Age group", 
                   values=["young", "old"])
    
    blueprint = AgentBlueprint.from_dimensions(politics, age, seed=42)
    
    # From a simple dictionary (quick)
    blueprint = AgentBlueprint.from_dimensions_dict({
        "politics": ["left", "right", "center"],
        "age": ["young", "old"]
    }, seed=42)
"""

from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText, QuestionNumerical


# Ask the model to identify dimensions from the persona description
q_dimensions = QuestionList(
    question_name="dimensions",
    question_text="""
Analyze the following persona/agent description and identify
the key dimensions that characterize this person:

<persona_description>
{{ scenario.persona_description }}
</persona_description>

{% if scenario.additional_details %}
Additional context: {{ scenario.additional_details }}
{% endif %}

We will be generating more personas that are similarly rich. 
We want to extract dimensions that are generalizable to a wider range of personas.

Extract dimensions like demographics (age, gender, location),
experience levels, skills, motivations, preferences, attitudes, or behavioral traits that
are explicitly mentioned or strongly implied in the description.

Provide {{ scenario.num_dimensions }} distinct dimensions that capture the essence of this persona.""",
)

# For each dimension, ask for possible levels/values
q_levels = QuestionList(
    question_name="levels",
    question_text="""Based on this persona description: {{ scenario.persona_description }}

You identified this dimension: {{ scenario.dimensions }}

What are realistic and meaningful levels/values that could vary across a population 
similar to this persona for this dimension?

Provide 3-6 distinct levels that would create meaningful differentiation. Include the 
level from the original persona if apparent.

For example:
- If dimension is "experience level": "Beginner (0-1 years)", "Intermediate (2-5 years)", "Expert (5+ years)"
- If dimension is "work preference": "Full-time contracts", "Part-time projects", "Hourly gigs"
- If dimension is "specialization": "Web development", "Mobile apps", "Data analysis", "Design"

Make the levels specific and realistic for creating a population with variation around this persona.

{% if scenario.additional_details %}
Please use the additional context to guide the level selection.
Additional context: 
<additional_context>
{{ scenario.additional_details }}
</additional_context>
{% endif %}
""",
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

Provide a brief 1 sentence phrase explaining what this dimension represents.
Example: "Represents the freelancer's preferred working arrangement and commitment level,
which affects project selection and client relationships."

Keep it concise.""",
)

# Build the jobs pipeline
jobs_object = (
    Survey([q_dimensions]).to_jobs()
    .select("scenario.persona_description", "scenario.additional_details", "scenario.num_dimensions", "answer.dimensions")
    .expand("answer.dimensions")
    .to(Survey([q_levels, q_name, q_description]))
)

# Initial survey to collect user input
initial_survey = Survey([
    QuestionFreeText(
        question_name="persona_description",
        question_text="Provide an existing persona or agent description (can be a narrative description, bullet points, or any text describing a person or agent type)",
    ),
    QuestionNumerical(
        question_name="num_dimensions",
        question_text="How many dimensions should be extracted from this persona? (Recommended: 4-8)",
        min_value=2,
        max_value=15,
    ),
    QuestionFreeText(
        question_name="additional_details",
        question_text="(Optional) Any additional guidance on which aspects to focus on when extracting dimensions?",
    ),
])

# Output formatter to create AgentBlueprint
# Note: to_agent_blueprint() internally uses AgentBlueprint.from_scenario_list()
# which performs ETL operations to convert scenario data into Dimension objects.
# For direct construction with Dimension objects, use AgentBlueprint.from_dimensions()
output_formatter = (
    OutputFormatter(
        description="Agent Blueprint",
        output_type="edsl_object"
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .to_agent_blueprint(
        dimension_name_field="dimension_name",
        dimension_values_field="levels",
        dimension_description_field="dimension_description",
    )
)

agent_blueprint_table = (output_formatter.copy()
    .set_output_type("markdown")
    .table(tablefmt = "github").to_string()
)


macro = Macro(
    application_name="agent_blueprint_from_persona",
    display_name="Agent Blueprint Creator from Persona",
    short_description="Create agent blueprints by extracting dimensions from an existing persona description.",
    long_description="This application analyzes an existing persona or agent description and extracts key dimensions to create a reusable agent blueprint. The blueprint can then be used to generate variations of similar personas with different characteristics.",
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={"agent_blueprint": output_formatter, "markdown_table": agent_blueprint_table},
    default_formatter_name="agent_blueprint",
    default_params={'num_dimensions': 6, 'additional_details': 'None'}
    )

if __name__ == "__main__":
    output = macro.output(params={
        'persona_description': '''Sarah is a 32-year-old freelance web developer based in Portland, Oregon.
She has been working on Upwork for 5 years and specializes in React and Node.js development.
She prefers long-term contracts (3+ months) with established companies and charges $85-100/hour.
Sarah values work-life balance and typically works 25-30 hours per week, allowing her to pursue
her passion for outdoor photography. She's highly responsive to clients and maintains a 99% job
success score.''',
        'num_dimensions': 6,
        'additional_details': 'Focus on professional characteristics that would be useful for creating similar but varied freelancer personas.',
    })
    print(output.agent_blueprint)

