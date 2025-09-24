from edsl.app.app import SurveyInputApp
from edsl.app.output_formatter import OutputFormatter, OutputFormatters

from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText


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
    .to(Survey([q_levels, q_name]))
)

# Output an AgentBlueprint using the answers
output_formatter = (
    OutputFormatter(
        name="Agent Blueprint",
        allowed_commands=["select", "to_scenario_list", "to_agent_blueprint"],
    )
    .select("scenario.*", "answer.*")
    .to_scenario_list()
    .to_agent_blueprint(
        dimension_name_field="dimension_name",
        dimension_values_field="levels",
        dimension_description_field="dimension_description",
    )
)

initial_survey = None

a = SurveyInputApp(
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters=OutputFormatters([output_formatter]),
)

if __name__ == "__main__":
    output = a.output(params=Survey.example())
    print(output)