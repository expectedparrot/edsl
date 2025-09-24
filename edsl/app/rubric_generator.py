import textwrap

from .app import SingleScenarioApp

from ..surveys import Survey
from ..questions import QuestionList, QuestionFreeText
from .output_formatter import OutputFormatter


# 1) Collect what the user wants to evaluate (e.g., "a technical blog post")
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
from edsl import Scenario
s = Scenario({"artifact_description": "a technical blog post"})
jobs_object = (
    Survey([dimensions_question]).by(s)
.select('scenario.artifact_description', 'answer.dimensions')
.expand('answer.dimensions')
.to(q_scales.to_survey())
)



rubric_formatter = (OutputFormatter("Rubric Survey")
.select('scenario.dimensions', 'answer.scales')
.rename( 
    {'scenario.dimensions': 'question_text', 
    'answer.scales': 'option_labels'}
).to_scenario_list().string_cat("question_text", ": {{ scenario.item}}")
.to_scenario_list().add_value('question_type', 'linear_scale')
.add_value('question_options', [1,2,3,4,5])
.zip('question_options', 'option_labels', 'option_labels')
).to_survey()


#question_info = jobs.run()

#.to_survey()

# # 3) Build a job that expands the generated dimensions into one row per dimension
# job = (
#     Survey([dimensions_question, q_scales]).to_jobs()
#     .select("artifact_description", "dimensions")
#     .to_scenario_list()
#     .expand("dimensions")
# )


# # 4) Output formatter turns the expanded list into a Survey (skeleton: free-text questions)
# #    You can adjust this to set question_type = "linear_scale" and add options/labels.
# rubric_formatter = (
#     OutputFormatter(name="Rubric Survey")
#     .select("dimensions")
#     .to_scenario_list()
#     .rename({"dimensions": "question_text"})
#     .to_survey()
# )


app = SingleScenarioApp(
     initial_survey=initial_survey,
     jobs_object=jobs_object,
     output_formatters=[rubric_formatter],
)


#rubric_survey = app.output({'artifact_description':"Technical Blog Post"})
#print(rubric_survey.table())


#rubric_survey = app.output({'artifact_description':"A chicken dinner"})
#print(rubric_survey.table())


rubric_survey = app.output({'artifact_description':"A Python script"})
print(rubric_survey.table())

