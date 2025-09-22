from .app import AppInteractiveSurvey

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

from edsl.app.output import OutputFormatters, FlippedTableOutput

survey = Survey([q1, q2, q3, q4, q5, q6])

from edsl.app.app import AppBase
from .output_formatter import OutputFormatters, OutputFormatter

of1 = OutputFormatter(name = "Robot VC").select('answer.*').table().flip()

of2 = OutputFormatter(name = "Robot VC").select('comment.*').table().flip()

from edsl.app.app import App

app = App(
    initial_survey=initial_survey,
    application_name="Robot VC",
    description="Score a startup for a VC investment.",
    jobs_object=survey.to_jobs(),
    output_formatters=OutputFormatters([of2, of1])
)

if __name__ == "__main__":
    #output = app.output(verbose=True)

    output = app.output(
        answers = {
            'startup_name': 'Test Startup', 
            'startup_description': """A startup that makes a new kind of dog collar.
                Both founders just graduated from high school (barely). No patents. No revenue. No customers. Pet ownership is declining. """},
        verbose=True)
    print(output)
    #output = app.run()
    #print(output)