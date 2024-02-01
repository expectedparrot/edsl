# import pytest
# from edsl.agents import Agent
# from edsl.jobs.Jobs import Jobs
# from edsl.questions import QuestionMultipleChoice
# from edsl.scenarios import Scenario
# from edsl.surveys import Survey
# from edsl.language_models import (
#     LanguageModelOpenAIThreeFiveTurbo,
#     LanguageModelOpenAIFour,
# )


# @pytest.fixture(scope="function")
# def huge_job():
#     q = QuestionMultipleChoice(
#         question_text="How are you?",
#         question_options=["Good", "Great", "OK", "Bad"],
#         question_name="how_feeling",
#     )
#     survey = Survey(name="Test Survey", questions=[q])
#     agents = [Agent(traits={"trait1": f"value{x}"}) for x in range(0, 100)]
#     models = [
#         LanguageModelOpenAIThreeFiveTurbo(use_cache=True),
#         LanguageModelOpenAIFour(use_cache=True),
#     ]
#     scenarios = [Scenario({"price": x, "quantity": 2}) for x in range(0, 100)]
#     huge_job = Jobs(
#         survey=survey,
#         agents=agents,
#         models=models,
#         scenarios=scenarios,
#     )
#     yield huge_job


# def test_jobs_run(huge_job):
#     results = huge_job.run(debug=True)
