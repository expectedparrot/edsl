from edsl import Agent, QuestionBudget, Survey
from edsl.inference_services.services.test_service import TestService


def test_budget_result_uses_labelled_public_answer_contract():
    budget = QuestionBudget(
        question_name="channel_budget",
        question_text="Allocate channel spend.",
        question_options=["Channel A", "Channel B", "Channel C"],
        budget_sum=100,
    )
    model = TestService.create_model("test")(
        skip_api_key_check=True,
        func=lambda user_prompt, system_prompt, files_list: "[20,30,50]",
    )

    results = (
        Survey([budget])
        .by(Agent())
        .by(model)
        .run(
            disable_remote_inference=True,
            stop_on_exception=True,
            cache=False,
        )
    )

    assert results.select("answer.channel_budget").to_list()[0] == [
        {"Channel A": 20.0},
        {"Channel B": 30.0},
        {"Channel C": 50.0},
    ]
