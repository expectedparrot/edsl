from ..surveys import Survey
from ..questions import QuestionList, QuestionMultipleChoice, QuestionFreeText
import textwrap

initial_survey = Survey([
    QuestionFreeText(
        question_name = "overall_question",
        question_text = "What is the overall question you want to answer?"
    ),
    QuestionFreeText(
        question_name = "population",
        question_text = "What is the population you want to survey?"
    ),
])


# First prompt: ask the LLM to propose a concrete survey question.
initial_question = QuestionList(
    question_text=textwrap.dedent("""\
    Please create survey questions that would help a researcher answer: {{ scenario.overall_question }}
    The target population is: {{ scenario.population }}
    """),
    question_name="generated_question_text",
)

from ..surveys import Survey

survey = Survey([
    QuestionMultipleChoice(
        question_text=textwrap.dedent("""\
        Consider this question:{{ scenario.generated_question_text }} being asked to {{ scenario.population }}.
        What would be the best format for this?
        Structured formats like multiple choice or checkbox are preferred, especial when the space of answers will be easy to enumerate.
        However, there should be a mix and if the question is naturally open-ended, then a free-text question is better.
        """),
        question_name="generated_question_type",
        question_options=["multiple_choice", "free_text", "checkbox"],
    ),  
    QuestionList(
        question_text=textwrap.dedent("""\
        Given this question: '{{ scenario.generated_question_text }}' (of type '{{ generated_question_type.answer }}') for a survey.
        What should the answer options be e.g., if question was 'What is your favorite color?' then options could be 'red', 'blue', 'green', 'other'?
        """),
        question_name="generated_question_options",
        ),
    QuestionFreeText(
        question_text=textwrap.dedent("""\
            Given this question: '{{ scenario.generated_question_text }}' (of type '{{ generated_question_type.answer }}') for a survey.
            What would be a good name for the question - it should be a valid python identifier. 
            Just return the name, no other text."""),
            question_name="generated_question_name",
        ),
    ])

job = (
    Survey([initial_question]).to_jobs()
    .select("generated_question_text", "population", "overall_question")
    .to_scenario_list()
    .expand("generated_question_text")
    .to(survey)
    .select(
        "generated_question_text",
        "generated_question_type",
        "generated_question_options",
  #      "generated_question_name",
    )
    .to_scenario_list()
    .then(
        "rename",
        {
            "generated_question_text": "question_text",
            "generated_question_type": "question_type",
            "generated_question_options": "question_options",
   #         "generated_question_name": "question_name",
        },
    )
    .to_survey()
)

if __name__ == "__main__":
    from .app import AppInteractiveSurvey
    from .output import PassThroughOutput
    app = AppInteractiveSurvey(
        initial_survey = initial_survey,
        jobs_object = job,
        output_formatter = PassThroughOutput(),
    )
    new_survey = app.output(answers = {"overall_question": "Why did you stop using EDSL?", "population": "Former EDSL users"}, verbose = True)
    print(new_survey)
