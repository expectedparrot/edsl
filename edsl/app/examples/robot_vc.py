from edsl.app import App
from edsl.app import OutputFormatter

from edsl import (
    QuestionLinearScale,
    QuestionFreeText,
    Survey,
    QuestionCompute,
)

initial_survey = Survey([
    QuestionFreeText(
        question_name="startup_name",
        question_text="What is the name of the startup you are evaluating?",
    ),
    QuestionFreeText(
        question_name="startup_description",
        question_text="Please describe the startup you are evaluating.",
    ),
])

q1 = QuestionLinearScale(
    question_name="exceptional_achievement",
    question_text="What exceptional achievements do the founders have? : {{ scenario.startup_description}}",
    question_options=[0, 4, 8, 11, 15],
    option_labels={
        0: "No notable achievements or recognition",
        4: "Local awards, small grants, or minor recognition",
        8: "National recognition, significant academic achievements, or industry awards",
        11: "International recognition, prestigious fellowships (Thiel, Y Combinator)",
        15: "MacArthur genius grant, Nobel laureate, founded unicorn company, Olympic medalist",
    },
)

q2 = QuestionLinearScale(
    question_name="market_timing_and_tailwinds",
    question_text="How favorable is the market timing and what tailwinds exist? : {{ scenario.startup_description}}",
    question_options=[0, 3, 5, 8, 10],
    option_labels={
        0: "Market declining, regulatory headwinds, no adoption catalysts",
        3: "Stable but slow-growth market, neutral regulatory environment",
        5: "Growing market, some positive trends, early adoption signals",
        8: "Rapidly growing market, strong tailwinds, regulatory support emerging",
        10: "Perfect timing - major catalysts converging (COVID for remote work, AI moment)",
    },
)

q3 = QuestionLinearScale(
    question_name="revenue_pilots",
    question_text="What is the current revenue and pilot status? : {{ scenario.startup_description}}",
    question_options=[0, 2, 4, 6, 8],
    option_labels={
        0: "No revenue, no pilots, no customer interest",
        2: "Early conversations, LOIs but no paid pilots",
        4: "1-3 paid pilots, <$100k ARR",
        6: "$100k-$1M ARR, 5+ customers, strong pipeline",
        8: "$1M+ ARR, 20+ customers, 100%+ growth rate",
    },
)

q4 = QuestionLinearScale(
    question_name="technical_moat",
    question_text="How strong is the technical moat and defensibility? : {{ scenario.startup_description}}",
    question_options=[0, 2, 3, 5, 6],
    option_labels={
        0: "No differentiation, easily replicable",
        2: "Some proprietary technology but limited defensibility",
        3: "Strong proprietary tech OR meaningful network effects emerging",
        5: "Multiple patents, strong network effects, high switching costs",
        6: "Foundational patents, winner-take-all network effects, impossible to replicate",
    },
)

q5 = QuestionCompute(
    question_name="total_score",
    question_text="""{% set numbers = [exceptional_achievement.answer, technical_moat.answer, revenue_pilots.answer, market_timing_and_tailwinds.answer] %}
    {{ numbers | sum }}
    """,
)

q6 = QuestionCompute(
    question_name="have_meeting",
    question_text="""{% if total_score.answer > 10 %}
    Yes
    {% else %}
    No
    {% endif %}
    """,
)


survey = Survey([q1, q2, q3, q4, q5, q6])


#of1 = OutputFormatter(description="Robot VC - Answers").select('answer.*').table().flip()

of1 = OutputFormatter(description="Robot VC - Answers", output_type="markdown").select('answer.*').table(tablefmt = "github").flip().to_string()
of2 = OutputFormatter(description="Robot VC - Comments", output_type="table").select('comment.*').table().flip()

# Markdown table formatter that returns a string for web display
# Use select and table with github format to get the data as markdown
markdown_table_formatter = (
    OutputFormatter(description="Scorecard", output_type="markdown")
    .select(
        'answer.exceptional_achievement',
        'answer.market_timing_and_tailwinds',
        'answer.revenue_pilots',
        'answer.technical_moat',
        'answer.total_score',
        'answer.have_meeting'
    )
    .table(tablefmt="github")
    .flip()
    .to_string()
)

app = App(
    initial_survey=initial_survey,
    application_name="robot_vc",
    display_name="Robot VC",
    short_description="AI venture capital evaluation.",
    long_description="This application simulates venture capital evaluation by analyzing startup pitches and business plans, providing investment recommendations based on multiple criteria and market factors.",
    jobs_object=survey.to_jobs(),
    output_formatters={
        "scorecard": of1,
        #        "answers": of1,#"comments": of2
    },
    default_formatter_name="scorecard",
)

if __name__ == "__main__":
    output = app.output(
        params={
            'startup_name': 'Test Startup', 
            'startup_description': """A startup that makes a new kind of dog collar.
            Both founders just graduated from high school (barely).
            No patents. No revenue. No customers. Pet ownership is declining."""},
        verbose=True)
    print(output)