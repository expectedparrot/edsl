import textwrap

from edsl.app import App

from edsl.surveys import Survey
from edsl.questions import QuestionList, QuestionFreeText
from edsl.app import OutputFormatter
from edsl import Scenario

initial_survey = Survey([
    QuestionFreeText(
        question_name="artifact_description",
        question_text="What do you want to evaluate? (e.g., 'a technical blog post')",
    ),
])

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

        They shoudl be concise and specific, and a model should be able to score them.
        """
    ),
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
   """ 
)

s = Scenario({"artifact_description": "a technical blog post"})
jobs_object = (
    Survey([dimensions_question]).by(s)
.select('scenario.artifact_description', 'answer.dimensions')
.expand('answer.dimensions')
.to(q_scales.to_survey())
)

rubric_formatter = (OutputFormatter(description="Rubric Survey")
.select('scenario.dimensions', 'answer.scales')
.rename( 
    {'scenario.dimensions': 'question_text', 
    'answer.scales': 'option_labels'}
).to_scenario_list().string_cat("question_text", ": {{ scenario.item}}")
.to_scenario_list().add_value('question_type', 'linear_scale')
.add_value('question_options', [1,2,3,4,5])
.zip('question_options', 'option_labels', 'option_labels')
).to_survey()

app = App(
     initial_survey=initial_survey,
     description = """A rubric generator.
     A rubric generator is a tool that generates a rubric for a given `artifact`.
     For example, if the artifact is a technical blog post, the rubric generator for the blog post.
     The rubric is formatted as an EDSL survey that can then be used to score the artifact.
     For example, the survey questions if the artifact is a technical blog post might be: 
     - How clear is the post?
     - How original is the post?
     - How useful is the post?
     - How impactful is the post?

     Each question is a linear scale question with 5 options, with 5 being the highest score.
     """,
     application_name = "rubric_generator",
     jobs_object=jobs_object,
     output_formatters={"rubric": rubric_formatter},
     default_formatter_name="rubric",
)

 
if __name__ == "__main__":
    rubric_survey = app.output({'artifact_description':"A new mattress"})
    print(rubric_survey.table())

