from edsl.app.app import App
from edsl.app.output_formatter import OutputFormatter, SurveyAttachmentFormatter

from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText, QuestionEDSLObject, QuestionNumerical


# Prompt the model for dimensions given each survey question
q = QuestionList(
    question_name="dimensions",
    question_text="""What dimensions of a person would you need to know to predict how they 
would answer this question: {{ scenario.question_text }}?""",
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
The associated levels were: {{ levels.answer }}.
Estimate, as best you can, the probability that a random person would have that value for this dimension.
E.g., if dimensions were 'sex' and levels were 'male' and 'female', 
the probabilities to return would be [0.5, 0.5] as males and females are equally likely.
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
    Survey([q]).to_jobs()
    .select("scenario.question_text", "answer.dimensions")
    .expand("answer.dimensions")
    .to(Survey([q_levels, q_name, q_probs, q_description]))
)

"""
Expected inputs (via initial_survey):
- A Survey to analyze (as an EDSL object)
- n: number of personas to generate
"""

initial_survey = Survey([
    QuestionEDSLObject(
        question_name="input_survey",
        question_text="Provide the Survey to analyze",
        expected_object_type="Survey",
    ),
    QuestionNumerical(
        question_name="n",
        question_text="How many personas should be generated?",
    ),
])

# Output an AgentBlueprint using the answers
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
        dimension_probs_field="probs",
        seed='1234'
    ).create_agent_list(n="{{params.n|int}}", strategy="probability", unique=True)
)

agent_list_markdown = output_formatter.copy().set_output_type("markdown").table(tablefmt="github").to_string()

# Markdown formatter that displays the persona dimensions and levels as a table
markdown_formatter = (
    OutputFormatter(
        description="Persona Dimensions Preview (Markdown)",
        output_type="markdown"
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .select("question_text", "dimension_name", "levels")
    .table(tablefmt="github")
    .to_string()
)

raw = OutputFormatter(description="Raw results")

app = App(
    description={
        "short": "A persona generator.",
        "long": "This application generates synthetic personas by analyzing survey questions, identifying relevant dimensions, and creating agent blueprints with appropriate trait levels."
    },
    application_name={
        "name": "Persona Generator",
        "alias": "create_personas"
    },
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={'agent_list': output_formatter, 'agent_list_markdown': agent_list_markdown, 'raw': raw},
    default_formatter_name="agent_list_markdown",
    attachment_formatters=[
        # Convert the passed Survey into a ScenarioList and attach as scenarios
        SurveyAttachmentFormatter(description="Survey->ScenarioList").to_scenario_list()
    ],
)

if __name__ == "__main__":
    from edsl import Survey
    survey = Survey.pull("5cde9b3b-3548-418c-9500-074103a13eef")
    
    output = app.output(params={
        'input_survey': survey,
        'n': 10,
    }, formatter_name="agent_list")
    print(output)