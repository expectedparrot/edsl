import pytest
from edsl.language_models import Model
from edsl.jobs import Jobs
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey
from edsl.jobs.jobs_pricing_estimation import JobsPrompts

price_lookup = {
    ("test", "test"): {
        "input": {
            "service": "test",
            "model": "test",
            "mode": "regular",
            "token_type": "input",
            "service_stated_token_qty": 1,
            "service_stated_token_price": 1,
            "one_usd_buys": 1,
        },
        "output": {
            "service": "test",
            "model": "test",
            "mode": "regular",
            "token_type": "output",
            "service_stated_token_qty": 1,
            "service_stated_token_price": 1,
            "one_usd_buys": 1,
        },
    }
}


def test_prompt_cost_estimation():
    estimated_cost_dct = JobsPrompts.estimate_prompt_cost(
        system_prompt="",
        user_prompt="What is your favorite month?",
        price_lookup=price_lookup,
        inference_service="test",
        model="test",
    )

    assert estimated_cost_dct["input_tokens"] == 7
    assert estimated_cost_dct["output_tokens"] == 6
    assert estimated_cost_dct["cost_usd"] == 13  # should be 13

    estimated_cost_dct = JobsPrompts.estimate_prompt_cost(
        system_prompt="",
        user_prompt="Why is that your favorite month?",
        price_lookup=price_lookup,
        inference_service="test",
        model="test",
    )

    assert estimated_cost_dct["input_tokens"] == 8
    assert estimated_cost_dct["output_tokens"] == 6
    assert estimated_cost_dct["cost_usd"] == 14


def test_prompt_cost_estimation_with_piping():
    estimated_cost_dct = JobsPrompts.estimate_prompt_cost(
        system_prompt="",
        user_prompt="Why is {{ answer }} your favorite month?",
        price_lookup=price_lookup,
        inference_service="test",
        model="test",
    )

    assert estimated_cost_dct["input_tokens"] == 20
    assert estimated_cost_dct["output_tokens"] == 15
    assert estimated_cost_dct["cost_usd"] == 35


def test_job_cost_estimation():
    q0 = QuestionFreeText(
        question_name="q0", question_text="What is your favorite month?"
    )
    q1 = QuestionFreeText(
        question_name="q1", question_text="Why is that your favorite month?"
    )
    m = Model("test", canned_response="SPAM!")
    s = Survey(questions=[q0, q1])
    j = Jobs(survey=s, models=[m])
    estimated_cost_dct = Jobs.estimate_job_cost_from_external_prices(j, price_lookup)

    input_tokens = estimated_cost_dct["estimated_total_input_tokens"]
    assert input_tokens == 15

    output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
    assert output_tokens == 12

    cost = estimated_cost_dct["estimated_total_cost_usd"]
    assert cost == 27

    cost_credits = estimated_cost_dct["credits_hold"]
    assert cost_credits == 2_700


def test_job_cost_estimation_with_iterations():
    q0 = QuestionFreeText(
        question_name="q0", question_text="What is your favorite month?"
    )
    q1 = QuestionFreeText(
        question_name="q1", question_text="Why is that your favorite month?"
    )
    m = Model("test", canned_response="SPAM!")
    s = Survey(questions=[q0, q1])
    j = Jobs(survey=s, models=[m])
    estimated_cost_dct = Jobs.estimate_job_cost_from_external_prices(
        j, price_lookup, iterations=2
    )

    input_tokens = estimated_cost_dct["estimated_total_input_tokens"]
    assert input_tokens == 30

    output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
    assert output_tokens == 24

    cost = estimated_cost_dct["estimated_total_cost_usd"]
    assert cost == 54

    cost_credits = estimated_cost_dct["credits_hold"]
    assert cost_credits == 5_400


def test_job_cost_estimation_with_piping():
    q0 = QuestionFreeText(
        question_name="q0", question_text="What is your favorite month?"
    )
    q1 = QuestionFreeText(
        question_name="q1", question_text="Why is {{ q0.answer }} your favorite month?"
    )
    m = Model("test", canned_response="SPAM!")
    s = Survey(questions=[q0, q1])
    j = Jobs(survey=s, models=[m])
    estimated_cost_dct = Jobs.estimate_job_cost_from_external_prices(j, price_lookup)

    # Test to make sure that the piping multiplier has taken effect
    input_tokens = estimated_cost_dct["estimated_total_input_tokens"]
    assert input_tokens > 20  # 7 from q0 + 20 from q1

    output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
    assert output_tokens > 15  # 21  # 6 from q0 + 15 from q1

    cost = estimated_cost_dct["estimated_total_cost_usd"]
    assert cost > 30  #  # 7 + 20 + 6 + 15

    cost_credits = estimated_cost_dct["credits_hold"]
    assert cost_credits > 3_000


def test_job_cost_estimation_with_piping_and_iterations():
    q0 = QuestionFreeText(
        question_name="q0", question_text="What is your favorite month?"
    )
    q1 = QuestionFreeText(
        question_name="q1", question_text="Why is {{ q0.answer }} your favorite month?"
    )
    m = Model("test", canned_response="SPAM!")
    s = Survey(questions=[q0, q1])
    j = Jobs(survey=s, models=[m])
    estimated_cost_dct = Jobs.estimate_job_cost_from_external_prices(
        j, price_lookup, iterations=2
    )

    # Test to make sure that the piping multiplier has taken effect
    input_tokens = estimated_cost_dct["estimated_total_input_tokens"]
    assert input_tokens > 30  # 54

    output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
    assert output_tokens > 25  # 42

    cost = estimated_cost_dct["estimated_total_cost_usd"]
    assert cost > 60  # 96

    cost_credits = estimated_cost_dct["credits_hold"]
    assert cost_credits > 6_000


def test_prompt_cost_estimation_with_fallback_to_highest_service_price():
    price_lookup_with_multiple = {
        ("service1", "model1"): {
            "input": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 1,
                "one_usd_buys": 1,
            },
            "output": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 2,
                "one_usd_buys": 0.5,
            },
        },
        ("service1", "model2"): {
            "input": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 3,
                "one_usd_buys": 0.33,
            },
            "output": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 4,
                "one_usd_buys": 0.25,
            },
        },
        ("service2", "model1"): {
            "input": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 5,
                "one_usd_buys": 0.2,
            },
            "output": {
                "service_stated_token_qty": 1,
                "service_stated_token_price": 6,
                "one_usd_buys": 0.1667,
            },
        },
    }

    # Test fallback to highest prices for service1 when model not found
    estimated_cost_dct = JobsPrompts.estimate_prompt_cost(
        system_prompt="",
        user_prompt="Test prompt",  # 3 tokens
        price_lookup=price_lookup_with_multiple,
        inference_service="service1",
        model="unknown",
    )

    # Should use highest prices for service (service1): 3 USD per input token and 4 USD per output token
    assert estimated_cost_dct["input_tokens"] == 2
    assert estimated_cost_dct["output_tokens"] == 2
    assert estimated_cost_dct["cost_usd"] == 14  # (2 * 3) + (2 * 4) = 14


def test_prompt_cost_estimation_with_fallback_to_default_price():
    # Empty price lookup to trigger default price fallback
    empty_price_lookup = {}

    estimated_cost_dct = JobsPrompts.estimate_prompt_cost(
        system_prompt="",
        user_prompt="Test prompt",  # 2 tokens
        price_lookup=empty_price_lookup,
        inference_service="unknown_service",
        model="unknown_model",
    )

    # Should use default prices: 0.000001 USD per token for both input and output
    assert estimated_cost_dct["input_tokens"] == 2
    assert estimated_cost_dct["output_tokens"] == 2
    # Cost should be (2 * 0.000001) + (2 * 0.000001) = 0.000004
    assert estimated_cost_dct["cost_usd"] == pytest.approx(0.000004)
