import textwrap

from edsl.agents import Agent, AgentList
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey
from edsl.language_models import Model

models = [
    Model("claude-opus-4-20250514", service_name="anthropic"),
    Model("gemini-2.0-flash-exp", service_name="google"),
]

a1 = Agent(
    name = "Econometrics Ed",
    traits = {
        'persona': """You are a PhD economist and assistant professor at a
        top US Econ Department. You are particularly focused on econometrics and statistical issues in the work you review and do."""
    }
)
a2 = Agent(
    name = "Policy Pam",
    traits = {
        'persona': """You are a PhD economist and assistant professor at a
        top US Econ Department. When reviewing, you are primarily foused on big-picture / what's at stake.
        You always want to know what are the practical and policy implications of the work.
        """
    }
)
a3 = Agent(
    name = "Litrary Lenore",
    traits = {
        'persona': """You are a PhD economist and assistant professor at a
        top US Econ Department. When reviewing, while you are an expert economist, you are primarily foused on the clarity and quality of the writing.
        You are nitpicky about style and grammar errors. You appreciate a well-crafted argument and note areas of the text that lack panache.
        """
    }
)
referees = AgentList([a1,a2,a3])


q_review = QuestionFreeText(
    question_text="""Please provide a critical referee report on this paper: {{scenario.paper}}""",
    question_name='full_review'
)

q_response_to_review = QuestionFreeText(
    question_name='response_to_review',
    question_text=textwrap.dedent("""\
    You submitted this paper: {{ scenario.paper}}.
    You received this review {{ full_review.answer }}.
    Please write a detailed response to the review.
    Push back on critiques that you don't agree with or that you think are wrong and explain why.
    Support your arguments with evidence from the paper.""")
)

q_round_two = QuestionFreeText(
    question_name='reviewer_round_2',
    question_text=textwrap.dedent("""\
    You reviwed this paper: {{ scenario.paper}}.
    Your review of the paper was: {{ full_review.answer }}.
    The author has now responded with this:
    <author response>
    {{ response_to_review.answer }}.
    </author response>
    Please tell us whether your critiques were adquetely adressed, point by point.
    """)
)

from edsl.questions import QuestionFileUpload
initial_survey = Survey([QuestionFileUpload(question_name = "paper", question_text = "Please upload your paper")])

survey = Survey([q_review, q_response_to_review, q_round_two])

from edsl.app import App
from edsl.app import OutputFormatter

report_template = """
# Review by {{ model }} playing role of '{{ agent_name }}'

## Paper

{{full_review}}

## Response to Review

{{response_to_review}}

## Referee's Response

{{ reviewer_round_2 }}
"""

output_formatter = (OutputFormatter(description = "Report From Template", output_type="docx")
.report_from_template(template=report_template, format='docx', filestore=True)
)

app = App(
    description = "A referee report generator.",
    application_name = "referee_report",
    initial_survey = initial_survey,
    jobs_object = survey.by(referees).by(models),
    output_formatters = {"report": output_formatter},
    default_formatter_name = "report",
)

if __name__ == "__main__":
    # Pass initial_survey-derived params directly (no legacy 'scenario' wrapper)
    app.output({'paper': "optimize.pdf"})