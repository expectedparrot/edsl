import textwrap

from edsl.macros import Macro
from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText
from edsl.macros import OutputFormatter
from edsl.scenarios import Scenario

initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="artifact_description",
            question_text="What do you want to evaluate? (e.g., 'a technical blog post')",
        ),
    ]
)

# 2) Generate evaluation dimensions (skeleton)
dimensions_question = QuestionList(
    question_name="dimensions",
    question_text=textwrap.dedent(
        """
        You are designing an evaluation rubric for the following artifact: {{ scenario.artifact_description }}.
        Please propose concise evaluation dimensions for assessing the artifact.
        E.g., if were evaluating a technical blog post, some dimensions could be:

        - Addresses a real problem or knowledge gap in the field
        - Has clear search demand or community interest
        - Offers unique perspective or solution not readily available elsewhere
        - Matches your expertise level and can add genuine value

        They should be concise and specific but with the unambigous context, and a model should be able to score them.
        For example, if the rubric was about 'coffee' the dimensions should not just be 'Body' but rather 'Body of the coffee'.
        """
    ),
)

weight_question = QuestionList(
    question_name="weights",
    question_text="""
    We are building a scoring rubric for {{ scenario.artifact_description }}.
    An identified dimension is: {{ dimensions.answer }}
    Please propose a list of weights for each dimension to capture its relative importance to the overall quality of the artifact.
    For example, if the dimensions are 'Clarity', 'Originality', and 'Usefulness', the weights could be [0.3, 0.3, 0.4].
    """,
)

q_scales = QuestionList(
    question_name="scales",
    question_text=""" 
   We are building a scoring rubric for {{ scenario.artifact_description }}. 
   An identified dimension is: {{ scenario.dimensions }}
   We now are creating a linear scale question for this dimension.
   For this dimension, please propose scale labels for levels 1 through 5. 
   1 is the lowest score, 5 is the highest score.
   For example, if the dimension is "Clarity of the post", the scale labels could be:
   - 1: The post is unclear and difficult to understand. Major clarity and grammar issues.
   - 2: The post is somewhat clear but could be improved
   - 3: The post is clear and reasonably well-written
   - 4: The post is clear and well-written and easy to follow.
   - 5: The post is clear and well-written. It is a model of good prose.
   Just include the scale labels, no other text.
   """,
)

s = Scenario({"artifact_description": "a technical blog post"})

jobs_object = (
    Survey([dimensions_question, weight_question])
    .by(s)
    .select("scenario.artifact_description", "answer.dimensions", "answer.weights")
    .to_scenario_list()
    .expand("dimensions", "weights")
    .to(q_scales.to_survey())
)

base_formatter = (
    OutputFormatter(description="Rubric Survey", output_type="Survey")
    .select("scenario.dimensions", "answer.scales", "scenario.weights")
    .rename(
        {
            "scenario.dimensions": "question_text",
            "answer.scales": "option_labels",
            "scenario.weights": "weight",
        }
    )
    .to_scenario_list()
    .string_cat("question_text", ": {{ scenario.item}}")
    .add_value("question_type", "linear_scale")
    .add_value("question_options", [1, 2, 3, 4, 5])
    .zip("question_options", "option_labels", "option_labels")
)

rubric_survey = base_formatter.copy().set_output_type("Survey").to_survey()
survey_with_weights = rubric_survey.copy().add_weighted_linear_scale_sum()
survey_table = (
    rubric_survey.copy()
    .set_output_type("markdown")
    .table(tablefmt="github")
    .to_string()
)

macro = Macro(
    application_name="rubric_generator",
    display_name="Rubric Generator",
    short_description="A rubric generator for evaluating artifacts.",
    long_description=textwrap.dedent(
        """\
        A rubric generator is a tool that generates a rubric for a given artifact.
        For example, if the artifact is a technical blog post, the rubric generator creates evaluation criteria for the blog post.
        The rubric is formatted as an EDSL survey that can then be used to score the artifact.
        For example, the survey questions for a technical blog post might be:
        - How clear is the post?
        - How original is the post? How useful is the post?
        - How impactful is the post? Each question is a linear scale question with 5 options, with 5 being the highest score."""
    ),
    initial_survey=initial_survey,
    jobs_object=jobs_object,
    output_formatters={
        "survey": rubric_survey,
        "survey_table": survey_table,
        "survey_with_weights": survey_with_weights,
    },
    default_formatter_name="survey_table",
)


if __name__ == "__main__":
    rubric_survey = macro.output(
        {"artifact_description": "coffee beans"}, formatter_name="survey_with_weights"
    )
    print(rubric_survey)


#
# app.run(artifact_description = """Promotional offer from a wealth management platform, evaluated from perspective of a current client.""")
# output = app.output(params = {'artifact_description':"Promotional offer from a wealth management platform, evaluated from perspective of a current client."})
# output2 = app.output(params = {'artifact_description':"Promotional offer from a wealth management platform, evaluated from perspective of a current client."})

# print(len(output.survey))
# print(len(output2.survey))
