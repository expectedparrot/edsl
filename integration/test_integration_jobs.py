from edsl.language_models import (
    LanguageModelOpenAIThreeFiveTurbo,
    LanguageModelOpenAIFour,
    GeminiPro,
)
from edsl.agents import Agent
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios import Scenario
from edsl.surveys import Survey


def test_simple_job_integration():
    q1 = QuestionMultipleChoice(
        question_text="How are you {{greeting}}??",
        question_options=["Terrible", "OK", "Great"],
        question_name="how_feeling_today",
    )
    q2 = QuestionMultipleChoice(
        question_text="How were you yesterday?",
        question_options=["Terrible", "OK", "Great"],
        question_name="how_feeling_yesterday",
    )
    survey = Survey(questions=[q1, q2])
    agents = [Agent({"state": value}) for value in {"sad", "happy"}]
    scenarios = [Scenario({"greeting": key}) for key in ["mate", "friendo"]]
    models_no_cache = [
        LanguageModelOpenAIThreeFiveTurbo(use_cache=False),
        LanguageModelOpenAIFour(use_cache=False),
        GeminiPro(use_cache=False),
    ]
    models_cache = [
        LanguageModelOpenAIThreeFiveTurbo(use_cache=True),
        LanguageModelOpenAIFour(use_cache=True),
        GeminiPro(use_cache=True),
    ]

    # print("-------------------------")
    # print("Uncomment to test streaming")
    # job_no_cache = survey.by(agents).by(scenarios).by(models_no_cache)
    # results_streaming = job_no_cache.run(method="streaming")
    # results_streaming

    print("-------------------------")
    print("Running job without cache")
    job_no_cache = survey.by(agents).by(scenarios).by(models_no_cache)
    results_no_cache = job_no_cache.run()
    results_no_cache

    print("-------------------------")
    print("Running job with cache")
    job_cache = survey.by(agents).by(scenarios).by(models_cache)
    results_cache = job_cache.run()
    results_cache
