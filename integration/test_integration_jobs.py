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

    models = [Model(model) for model in Model.available()]

    print("-------------------------")
    print("Running job without cache?")
    job_no_cache = survey.by(agents).by(scenarios).by(models)
    results_no_cache = job_no_cache.run(batch_mode = True)
    results_no_cache

    # TODO: ADD OPTION THAT SPECIFIES CACHE
