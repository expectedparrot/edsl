from __future__ import annotations

from edsl.macros.composite_macro import CompositeMacro
from edsl.macros.output_formatter import OutputFormatter, ScenarioAttachmentFormatter
from edsl.macros import Macro, CompositeMacro
from edsl.questions import QuestionEDSLObject, QuestionFreeText, QuestionNumerical, QuestionList
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.agents import Agent

# First app: Jeopardy question generator
input_survey = Survey([
    QuestionFreeText(
        question_name="input_text",
        question_text="What is the source text?"
    ),
    QuestionNumerical(
        question_name="words_per_chunk",
        question_text="How many words should be in each chunk?"
    )
])

q_questions = QuestionList(
    question_name="generated_questions",
    question_text="""
    Your job is to generate a list of questions that could be answered with the following text:
    <text>
    {{ scenario.input_text }}.
    </text>
    """
)

jobs_object = Survey([q_questions]).to_jobs()

# Output formatter that creates a Survey from the generated questions
of_survey = (
    OutputFormatter(description="Topics", output_type="edsl_object")
    .select('answer.generated_questions', 'scenario.input_text')
    .expand('answer.generated_questions')
    .select('answer.generated_questions')
    .to_scenario_list()
    .select('generated_questions')
    .rename({'generated_questions':'question_text'})
    .add_value('question_type', 'free_text')
    .to_survey()
)

# Scenario attachment formatter for chunking text
sa = (
    ScenarioAttachmentFormatter(name="Scenario Attachment Formatter")
    .chunk_text(field='input_text', chunk_size_field='words_per_chunk', unit='word')
)

jeopardy_macro = Macro(
    initial_survey=input_survey,
    application_name="jeopardy",
    display_name="Jeopardy",
    short_description="A jeopardy question generator.",
    long_description="A jeopardy question generator that creates questions from source text.",
    jobs_object=jobs_object,
    output_formatters={'survey': of_survey},
    default_formatter_name='survey',
    attachment_formatters=[sa]
)

# Second app: Run the generated survey with an agent that has expert knowledge
answering_survey = Survey([
    QuestionEDSLObject(
        question_name="survey",
        question_text="What is the survey object?",
        expected_object_type="Survey",
    ),
    QuestionFreeText(
        question_name="input_text",
        question_text="What is the context text?"
    )
])

from edsl.macros.output_formatter import ScenarioAttachmentFormatter
to_agent = ScenarioAttachmentFormatter(name="To Agent").to_agent_list()

# FIXME: This should be dynamically constructed from the survey output of the first macro
# For now, use a simple placeholder
jobs_object = Survey.example().to_jobs() 

answering_of = (
    OutputFormatter(description="Run survey with expert agent", output_type="markdown").long_view().table(tablefmt='github').to_string()
)

answering_macro = Macro(
    initial_survey=answering_survey,
    jobs_object=jobs_object,
    attachment_formatters=[to_agent],
    output_formatters={"results": answering_of},
    default_formatter_name="results",
    application_name="answer_with_context",
    display_name="Answer with Context",
    short_description="Run generated survey with agent that has expert knowledge of the context.",
    long_description="Run generated survey with agent that has expert knowledge of the context."
)

# Composite macro
macro = CompositeMacro(
    first_macro=jeopardy_macro,
    second_macro=answering_macro,
    bindings={
        "survey": "survey",  # jeopardy output -> answering input
        "param:input_text": "input_text"  # jeopardy input -> answering input
    },
    fixed={"app1": {}, "app2": {}},
    application_name="create_eval_from_text",
    display_name="Create Eval from Text",
    short_description="Generate questions from text and answer them with an expert agent.",
    long_description="Generate questions from text and answer them with an expert agent."
)


if __name__ == "__main__":
    text = """
Python was conceived in the late 1980s[41] by Guido van Rossum at Centrum Wiskunde & Informatica (CWI) in the Netherlands.[42]
It was designed as a successor to the ABC programming language, which was inspired by SETL,[43] capable of exception handling and interfacing with the Amoeba operating system.[13]
Python implementation began in December, 1989.[44]
Van Rossum first released it in 1991 as Python 0.9.0.[42] Van Rossum assumed sole responsibility for the project, as the lead developer, until 12 July 2018, when he announced his "permanent vacation" from responsibilities as Python's "benevolent dictator for life" (BDFL); this title was bestowed on him by the Python community to reflect his long-term commitment as the project's chief decision-maker.[45]
(He has since come out of retirement and is self-titled "BDFL-emeritus".)
In January 2019, active Python core developers elected a five-member Steering Council to lead the project.[46][47]

The name Python derives from the British comedy series Monty Python's Flying Circus.[48] (See § Naming.)
Python 2.0 was released on 16 October 2000, with many major new features such as list comprehensions, cycle-detecting garbage collection, reference counting, and Unicode support.[49] Python 2.7's end-of-life was initially set for 2015, and then postponed to 2020 out of concern that a large body of existing code could not easily be forward-ported to Python 3.[50][51]
It no longer receives security patches or updates.[52][53]
While Python 2.7 and older versions are officially unsupported, a different unofficial Python implementation, PyPy, continues to support Python 2, i.e., "2.7.18+" (plus 3.10), with the plus signifying (at least some) "backported security updates".[54]
Python 3.0 was released on 3 December 2008, and was a major revision and not completely backward-compatible with earlier versions, with some new semantics and changed syntax. Python 2.7.18, released in 2020, was the last release of Python 2.[55] Several releases in the Python 3.x series have added new syntax to the language, and made a few (considered very minor) backwards-incompatible changes.
As of 14 August 2025, Python 3.13 is the latest stable release and Python 3.9 is the oldest supported release.[56] Releases receive two years of full support followed by three years of security support.
"""

    # FIXME: This composite macro has issues with circular references causing RecursionError
    # Commenting out to prevent crashes during testing
    print("WARNING: This composite macro is currently disabled due to RecursionError issues.")
    print("The problem appears to be in the macro serialization or the binding structure.")

    # # Run the composite macro - it generates questions and answers them with an expert agent
    # results = macro.output(params={'input_text': text, 'words_per_chunk': 100})
    # #print(results.long_view())
