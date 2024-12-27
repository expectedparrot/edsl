from edsl import Model
from edsl import Question, Survey
from typing import List


def test_question_types(include=None, exclude=None, permissive=True) -> Survey:
    all = Question.available()
    if include is not None:
        all = [q for q in all if q in include]
    if exclude is not None:
        all = [q for q in all if q not in exclude]
    questions = [Question.example(question_type) for question_type in all]
    if permissive:
        for q in questions:
            q.permissive = True
    return Survey(questions)


def test_models(services=None) -> List[Model]:
    if services is None:
        services = Model.services()
    models = []
    for service in services:
        models.extend(Model.available(service=service))
    return [Model(model) for model, _, _ in models]


types_to_test = [
    "likert_five",
    "linear_scale",
    "rank",
    "top_k",
    "list",
    "multiple_choice",
    "numerical",
    "yes_no",
    "checkbox",
    "extract",
    "free_text",
]
# types_to_test = ["rank"]
# types_to_test = ["likert_five"]
services_to_test = Model.services()
breakpoint()
if "ollama" in services_to_test:
    services_to_test.remove("ollama")
# services_to_test.remove("test")
# services_to_test = ["azure"]  # , "groq", "bedrock"]
# types_to_test = ["numerical"]
for question_type in types_to_test:
    print("Now testing question type: ", question_type)
    for service in services_to_test:
        print("Now testing service: ", service)
        question_name = Question.example(question_type).question_name
        # print("Now testing question type: ", question_type)
        survey = test_question_types(include=[question_type], permissive=False)
        models = test_models(services=[service])
        results = survey.by(models).run(cache=True, skip_retry=True)

        all_answers = (
            results.select("answer.*")
            .to_scenario_list()
            .unpivot()
            .select("value")
            .to_list()
        )
        results.select(
            "model.model",
            "answer.*",
            "generated_tokens.*",
            f"{question_name}_cost",
            f"{question_name}_one_usd_buys",
        ).print()

        frac_fail = sum([1 for answer in all_answers if answer is None]) / len(
            all_answers
        )
        print(f"Fraction of failed answers: {frac_fail}")

        if frac_fail > 0:
            print("Failing models")
            question_name = survey.questions[0].question_name
            results.filter(f"answer.{question_name} is None").select(
                "model.model"
            ).print()


# print("Now running against {} models".format(len(models)))
# results = s.by(models).run(print_exceptions=True, skip_retry=True, cache=False)
# info = results.push()
# outcome = results.to_scenario_list()
# info = outcome.push()
# print(info)

# combined_responses = None
# for service in Model.services():
#     if service in ["bedrock", "deep_infra"]:
#         print(f"Testing {service}")
#         models = [Model(model) for model, _, _ in Model.available(service=service)]
#         # from edsl import QuestionNumerical as Q

#         q = Q.example()
#         q.min_selections = 1
#         results = q.by(models).run()
#         results.select("model", "answer.*").print()
#         sl = (
#             results.select("model", "answer.*")
#             .to_scenario_list()
#             .add_value("service", service)
#         )
#         if combined_responses is None:
#             combined_responses = sl
#         else:
#             combined_responses += sl


# combined_responses.print()
# info = combined_responses.push()
# print(info)
