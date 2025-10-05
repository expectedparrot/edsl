import textwrap

from edsl.questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionCheckBox,
    QuestionMarkdown,
)
from edsl import Agent, Survey

initial_survey = Survey(
    [
        QuestionFreeText(
            question_name="trip_duration",
            question_text="What is the duration of your trip?",
        ),
        QuestionFreeText(
            question_name="destination",
            question_text="What is your destination?",
        ),
        QuestionFreeText(
            question_name="weather_conditions",
            question_text="What are the expected weather conditions?",
        ),
        QuestionCheckBox(
            question_name="planned_activities",
            question_text="What are your planned activities?",
            question_options=[
                "Hiking/Outdoor adventures",
                "Beach/Swimming",
                "Business meetings",
                "Formal dining",
                "Sightseeing/Tourism",
                "Sports/Fitness",
                "Photography",
                "Shopping",
                "Cultural events",
                "Nightlife/Entertainment",
            ],
        ),
        QuestionMultipleChoice(
            question_name="travel_style",
            question_text="What is your travel style?",
            question_options=[
                "Backpacking/Budget travel",
                "Business travel",
                "Luxury travel",
                "Family vacation",
                "Adventure travel",
            ],
        ),
        QuestionFreeText(
            question_name="special_considerations",
            question_text="Any special considerations or requirements?",
        ),
    ]
)

a = Agent(
    name="travel_planner",
    traits={
        "persona": textwrap.dedent(
            """\
Adopt the role of an expert travel planner tasked with creating comprehensive packing lists.
Your primary objective is to generate a detailed, well-organized packing list tailored to specific trip parameters.
To accomplish this, consider the destination's climate, planned activities, and trip duration.
Categorize items into essentials, clothing, toiletries, electronics, and travel documents.
Ensure the list is thorough yet concise, accounting for potential weather variations and activity-specific needs.
Prioritize versatile items to maximize space efficiency and minimize overpacking.
"""
        ),
    },
)

q_packing_list = QuestionFreeText(
    question_name="packing_list_detailed",
    question_text=textwrap.dedent(
        """\
Create a comprehensive packing list for the trip based on the following information.
Take a deep breath and work on this problem step-by-step.

<trip context>
Trip duration: {{ scenario.trip_duration }}
Destination: {{ scenario.destination }}
Expected weather conditions: {{ scenario.weather_conditions }}
Planned activities: {{ scenario.planned_activities }}
Travel style: {{ scenario.travel_style }}
Special considerations: {{ scenario.special_considerations }}
</trip context>

Present your output in a categorized list format, using headings for each category (Essentials, Clothing, Toiletries, Electronics, and Travel Documents) followed by bullet points for individual items. Consider the destination's climate, planned activities, and trip duration. Ensure the list accounts for potential weather variations and activity-specific needs while prioritizing versatile items to maximize space efficiency.
"""
    ),
)

q_packing_checklist = QuestionMarkdown(
    question_name="packing_checklist",
    question_text="""You were asked {{ packing_list_detailed.question_text }}.
    You received as an answer: {{ packing_list_detailed.answer }}.
    Please extract and return a markdown checklist format with checkboxes for each item, organized by category.
    Use the format: - [ ] Item name
    Only return the markdown checklist, no other text.""",
)

q_packing_tips = QuestionFreeText(
    question_name="packing_tips",
    question_text="""Based on this packing list:
    {{ packing_checklist.answer }}
    And the trip details:
    Destination: {{ scenario.destination }}
    Duration: {{ scenario.trip_duration }}
    Activities: {{ scenario.planned_activities }}

    Please provide 5-7 practical packing tips specific to this trip. Consider space-saving techniques, versatile items, and destination-specific advice.
    Format as a numbered list with brief explanations.""",
)

q_weight_estimates = QuestionFreeText(
    question_name="weight_estimates",
    question_text="""Based on this packing list:
    {{ packing_list_detailed.answer }}

    Please provide estimated weight ranges for each category and total estimated luggage weight.
    Consider the travel style: {{ scenario.travel_style }}
    Format as a simple table with categories and weight estimates.""",
)

s = Survey([q_packing_list, q_packing_checklist, q_packing_tips, q_weight_estimates])
jobs = s.by(a)


from edsl.app import App
from edsl.app import OutputFormatter

markdown_viewer = (
    OutputFormatter(description = "Markdown Viewer", output_type="markdown")
    .select('answer.packing_checklist', 'answer.packing_tips', 'answer.weight_estimates')
    .table(tablefmt="github")
    .flip()
    .to_string()
)

app = App(
    description={
        "short": "Generate packing lists for trips.",
        "long": "This application creates customized packing lists for trips based on destination, duration, activities, weather conditions, and traveler preferences."
    },
    application_name={
        "name": "Packing List Generator",
        "alias": "packing_list"
    },
    initial_survey=initial_survey,
    jobs_object=jobs,
    output_formatters={"markdown": markdown_viewer},
    default_formatter_name="markdown",
)

if __name__ == "__main__":
    plan = app.output(
        params = {
            'trip_duration': '1 week',
            'destination': 'Paris',
            'weather_conditions': 'sunny',
            'planned_activities': 'sightseeing',
            'travel_style': 'luxury',
            'special_considerations': 'none',
        },
        verbose=True)