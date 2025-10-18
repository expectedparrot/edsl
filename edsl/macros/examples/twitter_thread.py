import textwrap

from edsl.agents import Agent
from edsl.questions import (
    QuestionFreeText,
    QuestionLinearScale,
    QuestionMultipleChoice,
    QuestionFileUpload,
)
from edsl.surveys import Survey
from edsl.macros import Macro
from edsl.macros import OutputFormatter

# Initial survey to gather parameters
initial_survey = Survey(
    [
        QuestionFileUpload(
            question_name="paper", question_text="Please upload your academic paper"
        ),
        QuestionMultipleChoice(
            question_name="target_audience",
            question_text="Who is your target audience?",
            question_options=[
                "Academic researchers",
                "Industry professionals",
                "General public",
                "Policy makers",
            ],
        ),
        QuestionLinearScale(
            question_name="thread_length",
            question_text="How many tweets would you like in your thread? (approximately)",
            question_options=[5, 7, 10, 12, 15],
            option_labels={
                5: "5 tweets",
                7: "7 tweets",
                10: "10 tweets",
                12: "12 tweets",
                15: "15 tweets",
            },
        ),
        QuestionMultipleChoice(
            question_name="tone",
            question_text="What tone should the thread have?",
            question_options=[
                "Professional/Academic",
                "Conversational/Accessible",
                "Enthusiastic/Promotional",
            ],
        ),
    ]
)

# Create an agent specialized in science communication
thread_writer = Agent(
    name="Thread Writer",
    traits={
        "persona": """You are an expert science communicator who specializes in
        translating complex academic research into engaging Twitter threads. You understand
        how to hook readers, break down complex ideas, and maintain engagement across a thread.
        You know Twitter best practices and how to craft tweets that are informative yet accessible."""
    },
)

# Question to generate the thread
q_thread = QuestionFreeText(
    question_name="twitter_thread",
    question_text=textwrap.dedent(
        """\
    Please create an engaging Twitter thread about this academic paper: {{ scenario.paper }}

    Target audience: {{ scenario.target_audience }}
    Desired thread length: Approximately {{ scenario.thread_length }} tweets
    Tone: {{ scenario.tone }}

    Guidelines:
    - Start with a hook tweet that grabs attention and explains why this research matters
    - Break down the key findings into digestible tweets
    - Use clear, accessible language appropriate for the target audience
    - Include the main methodology and results
    - End with implications/takeaways and a call to action
    - Keep each tweet under 280 characters
    - Number each tweet (e.g., "1/10", "2/10", etc.)
    - Use line breaks between tweets for clarity
    - Consider using emojis sparingly if appropriate for the tone

    Format each tweet clearly, starting each one on a new line with its number.
    """
    ),
)

# Question to generate key hashtags
q_hashtags = QuestionFreeText(
    question_name="hashtags",
    question_text=textwrap.dedent(
        """\
    Based on the paper: {{ scenario.paper }}

    Suggest 5-8 relevant hashtags that would help this thread reach the right audience.
    Consider hashtags related to:
    - The research field/discipline
    - Key concepts or methods
    - Relevant academic or professional communities

    List them separated by spaces, e.g., #MachineLearning #AI #Research
    """
    ),
)

# Question to generate a visual suggestion
q_visual_suggestion = QuestionFreeText(
    question_name="visual_suggestion",
    question_text=textwrap.dedent(
        """\
    Based on the paper: {{ scenario.paper }}

    Suggest 2-3 types of visuals or graphics that would enhance this Twitter thread.
    For each suggestion, briefly describe:
    - What type of visual (chart, diagram, infographic, etc.)
    - What it should show
    - Where in the thread it would go (which tweet number)

    Be specific and practical about what would be most impactful for Twitter.
    """
    ),
)

# Create the survey
survey = Survey([q_thread, q_hashtags, q_visual_suggestion])

# Output formatter
thread_template = """
# Twitter Thread

## Target Audience
{{ target_audience }}

## Tone
{{ tone }}

## Thread Length
{{ thread_length }} tweets

## Thread

{{ twitter_thread }}

## Suggested Hashtags

{{ hashtags }}

## Visual Suggestions

{{ visual_suggestion }}

---

*Generated with EDSL*
"""

docx_formatter = OutputFormatter(description="DOCX Report").to_docx(
    "twitter_thread.docx"
)

# Markdown formatter - just select and convert to markdown
# This will return the selected fields as inline markdown text
markdown_formatter = (
    OutputFormatter(description="Markdown", output_type="markdown")
    .select("answer.twitter_thread", "answer.hashtags", "answer.visual_suggestion")
    .table(tablefmt="github")
    .flip()
    .to_string()
)

# Create the macro
macro = Macro(
    application_name="twitter_thread",
    display_name="Twitter Thread Generator",
    short_description="Generate Twitter threads from text.",
    long_description="This application converts long-form text into engaging Twitter threads by breaking content into tweet-sized chunks while maintaining narrative flow and engagement.",
    initial_survey=initial_survey,
    jobs_object=survey.by(thread_writer),
    output_formatters={"markdown": markdown_formatter, "docx": docx_formatter},
    default_formatter_name="markdown",
)

if __name__ == "__main__":
    # Example usage
    macro.output(
        {
            "paper": "../optimize.pdf",
            "target_audience": "General public",
            "thread_length": 10,
            "tone": "Conversational/Accessible",
        }
    )
