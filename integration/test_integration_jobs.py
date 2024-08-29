from edsl import Model, Agent, Scenario, Survey
from edsl.questions import QuestionMultipleChoice

Model.available()


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
    agents = [Agent(traits={"state": value}) for value in {"sad", "happy"}]
    scenarios = [Scenario({"greeting": key}) for key in ["mate", "friendo"]]

    models_to_check = [
        "gpt-4",
        "gemini-pro",
        "claude-3-opus-20240229",
        "meta-llama/Meta-Llama-3-70B-Instruct",
    ]
    models = [Model(model_name) for model_name in models_to_check]
    print("-------------------------")
    print("Running job without cache?")
    job_no_cache = survey.by(agents).by(scenarios).by(models)
    results_no_cache = job_no_cache.run(cache=False, stop_on_exception=True)
    results_no_cache

    # TODO: ADD OPTION THAT SPECIFIES CACHE
