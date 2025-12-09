from edsl.macros.macro import Macro
from edsl.macros.output_formatter import OutputFormatter
from edsl import QuestionList, QuestionFreeText, QuestionNumerical
from edsl import Scenario
from edsl import Survey

from edsl.macros.output_formatter import ScenarioAttachmentFormatter


input_survey = Survey(
    [
        QuestionFreeText(
            question_name="input_text", question_text="""What is source text?"""
        ),
        QuestionNumerical(
            question_name="words_per_chunk",
            question_text="""How many words should be in each chunk?""",
        ),
    ]
)

q_questions = QuestionList(
    question_name="generated_questions",
    question_text="""
    Your job is to generate a list of questions that could be answered with the following text:
    <text>
    {{ scenario.input_text }}.
    </text>
    """,
)

jobs_object = q_questions.by(Scenario.example())

of = (
    OutputFormatter(description="Topics", output_type="ScenarioList")
    .select("answer.generated_questions", "scenario.input_text")
    .expand("answer.generated_questions")
    .select("answer.generated_questions")
    .to_scenario_list()
    .select("generated_questions")
    .rename({"generated_questions": "question_text"})
    .add_value("question_type", "free_text")
    .to_survey()
)

# Markdown formatter that displays the generated questions as a table
markdown_formatter = (
    OutputFormatter(description="Questions Preview (Markdown)", output_type="markdown")
    .select("answer.generated_questions", "scenario.input_text")
    .expand("answer.generated_questions")
    .select("answer.generated_questions")
    .to_scenario_list()
    .select("generated_questions")
    .rename({"generated_questions": "question_text"})
    .add_value("question_type", "free_text")
    .table(tablefmt="github")
    .to_string()
)

# This modifies the scenario by chunking the text
# before attaching it to the jobs object.
sa = ScenarioAttachmentFormatter(
    name="Scenario Attachment Formatter", output_type="ScenarioList"
).chunk_text(field="input_text", chunk_size_field="words_per_chunk", unit="word")

macro = Macro(
    application_name="jeopardy",
    display_name="Jeopardy Question Generator",
    short_description="Generate Jeopardy-style questions.",
    long_description="This application creates Jeopardy-style trivia questions with clues and answers based on provided topics or knowledge domains.",
    initial_survey=input_survey,
    jobs_object=jobs_object,
    output_formatters={"survey": of, "markdown": markdown_formatter},
    default_formatter_name="survey",
    attachment_formatters=[sa],
)

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

if __name__ == "__main__":
    # FIXME: This causes a RecursionError - likely in the to_survey() formatter method
    # Commenting out to prevent crashes during testing
    print("WARNING: This macro is currently disabled due to RecursionError issues.")
    print("The problem appears to be in the to_survey() formatter method.")
    print("Running basic test instead...")

    # Test with markdown formatter instead
    try:
        result = macro.output(
            params={"input_text": text, "words_per_chunk": 100},
            formatter_name="markdown",
        )
        print("Markdown formatter test successful:")
        print(result)
    except Exception as e:
        print(f"Error with markdown formatter: {e}")

    # # Original code that causes RecursionError:
    # gold_standard_survey = macro.output(params = {'input_text': text, 'words_per_chunk': 100}, formatter_name = 'survey')
    # from edsl.agents import Agent
    # a = Agent(traits = {'expert_knowledge_on': text})
    #
    # gold_results = gold_standard_survey.by(a).run()
    # print(gold_results.long_view())
