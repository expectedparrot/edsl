import textwrap

from edsl.app import App
from edsl.app.output_formatter import OutputFormatter
from edsl.questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    QuestionCheckBox,
    QuestionMarkdown,
)
from edsl import Agent, Survey

initial_survey = Survey(
    [
        QuestionNumerical(
            question_name="number_of_people",
            question_text="What is the number of people being fed?",
        ),
        QuestionFreeText(
            question_name="dietary_preferences_or_restrictions",
            question_text="What are the dietary preferences or restrictions?",
        ),
        QuestionMultipleChoice(
            question_name="time_for_cooking",
            question_text="How much time do you have for cooking?",
            question_options=[
                "Very little - ideally meals are almost no preparation",
                "Some - I'm find with cooking for 15 minutes or so for a hot meal",
                "Lots - I love cooking and can spend a lot of time in the kitchen",
            ],
        ),
        QuestionCheckBox(
            question_name="days_of_the_week",
            question_text="What are the days of the week you need a meal plan for?",
            question_options=[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
        ),
        QuestionFreeText(
            question_name="any_specific_health_goals",
            question_text="What are the any specific health goals?",
        ),
        QuestionFreeText(
            question_name="food_allergies_or_intolerances",
            question_text="What are the food allergies or intolerances?",
        ),
        QuestionFreeText(
            question_name="other", question_text="Any other instructions?"
        ),
    ]
)

a = Agent(
    name="nutritionist",
    traits={
        "persona": textwrap.dedent(
            """\
Adopt the role of an expert nutritionist tasked with creating personalized meal plans. 
"""
        ),
    },
)

q_meal_plan = QuestionFreeText(
    question_name="meal_plan_scratch",
    question_text=textwrap.dedent(
        """\
Your primary objective is to design a comprehensive weekly meal plan that caters to specific dietary needs and preferences. 
Take a deep breath and work on this problem step-by-step. 
To accomplish this, you should consider nutritional balance, variety, and adherence to any dietary restrictions. 
Create a detailed narrative meal plan that promotes health and satisfies taste preferences while accommodating the specified number of people.

<planning context>
Number of people: {{ scenario.number_of_people }}
Dietary preferences or restrictions: {{ scenario.dietary_preferences_or_restrictions }}
Days of the week: {{ scenario.days_of_the_week }}
Any specific health goals: {{ scenario.any_specific_health_goals }}
Food allergies or intolerances:  {{ scenario.food_allergies_or_intolerances }}
Time for cooking: {{ scenario.time_for_cooking }}
Other instructions: {{ scenario.other }}
</planning context>

Write your meal plan with columns for each day of the week, including breakfast, lunch, dinner, and snacks for each day.
"""
    ),
)

q_meal_plan_table = QuestionMarkdown(
    question_name="meal_plan_table",
    question_text="""You were asked {{ meal_plan_scratch.question_text }}.
    You received as an answer: {{ meal_plan_scratch.answer }}.
    Please extract and return a markdown table with columns for each day of the week, including breakfast, lunch, dinner, and snacks for each day.
    Only return the markdown table, no other text.""",
)

q_shopping_list = QuestionFreeText(
    question_name="shopping_list",
    question_text="""You have a weekly meal plan: 
    {{ meal_plan_table.answer }}
    Please extract and return a markdown list of the ingredients you need to buy for the meal plan.     
    Number of people: {{ scenario.number_of_people }}
    Return a table with columns for the ingredient, quantity, and unit.
    Only return the markdown table, no other text.""",
)

q_recipes = QuestionFreeText(
    question_name="recipes",
    question_text="""You have a weekly meal plan: 
    {{ meal_plan_table.answer }}
    For any of these meals that requiring some cooking or skill, please provide a very short recipe
    Only do it for the meals that require some cooking or skill.
    Return markdown text with the meal name as the heading and then a paragraph of the recipe.
    """,
)

s = Survey([q_meal_plan, q_meal_plan_table, q_shopping_list, q_recipes])
jobs = s.by(a)

from edsl.app.app import App

markdown_viewer = (
    OutputFormatter(name = "Markdown Viewer")
    .select('answer.meal_plan_table', 'answer.shopping_list', 'answer.recipes')
    .to_markdown()
    .view()
)

docx_writer = (
    OutputFormatter(name = "Docx Writer")
    .select('answer.meal_plan_table', 'answer.shopping_list', 'answer.recipes')
    .to_markdown()
    .to_docx()
)


app = App(
    initial_survey=initial_survey,
    application_name="Meal Planner",
    description="Create a meal plan for a given number of people.",
    jobs_object=jobs,
    output_formatters=[markdown_viewer, docx_writer]
)

if __name__ == "__main__":
    plan = app.output({
            "number_of_people": 1,
            "dietary_preferences_or_restrictions": "None",
            "days_of_the_week": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
            ],
            "time_for_cooking": "Very little - ideally meals are almost no preparation",
            "any_specific_health_goals": "Build muscle and lose body fat",
            "other": "I'm fine with very simple meals. Almost zero preparation please.",
            "food_allergies_or_intolerances": None,
        },
        verbose=True,
    )
    print(plan)
