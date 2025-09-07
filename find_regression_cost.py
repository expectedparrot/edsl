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

print("Estimated cost dict:")
print(estimated_cost_dct)

from rich import print
from rich.json import JSON

# From a dictionary
print(JSON.from_data(estimated_cost_dct))

input_tokens = estimated_cost_dct["estimated_total_input_tokens"]
try:
    assert input_tokens == 59
except AssertionError:
    print(f"Computed input_tokens: {input_tokens}")
    raise

breakpoint()


output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
assert output_tokens == 45

cost = estimated_cost_dct["estimated_total_cost_usd"]
assert cost == 104

total_credits_hold = estimated_cost_dct["total_credits_hold"]
assert total_credits_hold == 10_400

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
assert input_tokens == 118

output_tokens = estimated_cost_dct["estimated_total_output_tokens"]
assert output_tokens == 90

cost = estimated_cost_dct["estimated_total_cost_usd"]
assert cost == 208

total_credits_hold = estimated_cost_dct["total_credits_hold"]
assert total_credits_hold == 20_800


