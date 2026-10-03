"""Bounded batch execution with validated caching and ordinary EDSL Results."""

from __future__ import annotations

import asyncio
import copy
import math

import httpx

from .evaluation import canonical


class EvaluationRunError(RuntimeError):
    """Execution failed; completed rows and successful cached batches are retained."""

    def __init__(self, errors, partial_results):
        self.errors = errors
        self.partial_results = partial_results
        super().__init__("Evaluation failed: " + "; ".join(errors))


def _number(value, name, *, probability=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")
    if probability and not 0 <= value <= 1:
        raise ValueError(f"{name} must be between zero and one")
    return value


def validate_response(batch, response, row):
    from edsl.questions.probabilistic_response import ProbabilisticResponse

    if not isinstance(response, dict) or not isinstance(response.get("model"), str):
        raise ValueError("Response must identify the model that answered")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(batch.questions):
        raise ValueError("Response question IDs must match the batch exactly")
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        raise ValueError("Response usage must be an object")
    for name in ("input_tokens", "output_tokens"):
        count = usage.get(name)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"usage.{name} must be a nonnegative integer")
    distributions = {}
    for name, definition in batch.questions.items():
        answer = answers[name]
        primitive = definition["type"]
        if not isinstance(answer, dict) or answer.get("type") != primitive:
            raise ValueError(f"{name}: response primitive does not match the question")
        options = row.questions[name].question_options
        if primitive == "binary":
            p = _number(answer.get("probability"), name, probability=True)
            probabilities = [p if str(o).lower() == "yes" else 1 - p for o in options]
        else:
            values = answer.get("probabilities")
            if not isinstance(values, dict) or set(values) != {
                str(i) for i in range(len(options))
            }:
                raise ValueError(f"{name}: probability keys must match the option IDs")
            probabilities = [values[str(i)] for i in range(len(options))]
            _number(answer.get("confidence"), f"{name}.confidence", probability=True)
            if primitive == "choice":
                choice = answer.get("choice")
                if not isinstance(choice, str) or choice not in values:
                    raise ValueError(f"{name}: choice is not a supplied option")
            if primitive == "score":
                score = _number(answer.get("score"), f"{name}.score")
                if not 0 <= score <= len(options) - 1:
                    raise ValueError(f"{name}: score is outside its levels")
        contract = getattr(row.questions[name], "probabilistic_response", None)
        contract = contract or ProbabilisticResponse(resolution="mode")
        probabilities = contract.validate(probabilities, len(options))
        if primitive == "choice" and probabilities[int(answer["choice"])] != max(
            probabilities
        ):
            raise ValueError(f"{name}: choice is not a highest-probability option")
        # Providers may quantize scores and probabilities independently. Validate
        # each field's domain, but do not require algebraic equality between
        # independently rounded outputs. EDSL resolves answers from probabilities.
        distributions[name] = probabilities
    return distributions


async def execute(plan, *, cache=None, max_concurrency=8):
    from edsl import Cache, Results
    from edsl.results import Result
    from edsl.prompts import Prompt
    from edsl.questions.probabilistic_response import ProbabilisticResponse

    if (
        isinstance(max_concurrency, bool)
        or not isinstance(max_concurrency, int)
        or max_concurrency < 1
    ):
        raise ValueError("max_concurrency must be a positive integer")
    if cache is None or cache is False:
        cache = Cache()
    if not isinstance(cache, Cache):
        raise TypeError("cache must be an EDSL Cache, False, or None")
    results = [
        Result(
            agent=row.agent,
            scenario=row.scenario,
            model=row.model,
            iteration=row.iteration,
            answer={},
            survey=plan.survey,
            question_to_attributes={
                name: {
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "question_options": q.question_options,
                }
                for name, q in row.questions.items()
            },
            indices=row.indices,
        )
        for row in plan.rows
    ]
    errors = []
    pending = iter(enumerate(plan.batches))

    async with httpx.AsyncClient(timeout=120) as client:

        async def worker():
            for batch_index, batch in pending:
                row = plan.rows[batch.row]
                result = results[batch.row]
                try:
                    call = {
                        "model": batch.model.model,
                        "parameters": {
                            "evaluation_format": 1,
                            "service": batch.model.service_name,
                        },
                        "system_prompt": canonical(batch.state),
                        "user_prompt": canonical(batch.questions),
                        "iteration": row.iteration,
                    }
                    cached, cache_key = cache.fetch(**call)
                    if cached is not None:
                        import json

                        response = json.loads(cached)
                    else:
                        response = await batch.model.async_evaluate(
                            copy.deepcopy(batch.state),
                            copy.deepcopy(batch.questions),
                            client=client,
                        )
                    distributions = validate_response(batch, response, row)
                    if cached is None:
                        cache_key = cache.store(
                            **call,
                            response=response,
                            service=batch.model.service_name,
                            validated=True,
                        )
                    for name, definition in batch.questions.items():
                        question = row.questions[name]
                        contract = (
                            question.probabilistic_response
                            or ProbabilisticResponse(resolution="mode")
                        )
                        resolution = contract.resolve(
                            distributions[name],
                            context=contract.seed_context(
                                agent=row.agent,
                                scenario=row.scenario,
                                question_name=name,
                                iteration=row.iteration,
                            ),
                        )[0]
                        index = resolution["index"]
                        result["answer"][name] = (
                            question.question_options[index]
                            if index is not None
                            else None
                        )
                        result["distribution"][name] = distributions[name]
                        for field in ("draw", "seed", "method"):
                            result[f"resolution_{field}"][name] = resolution[field]
                        result["validated_dict"][f"{name}_validated"] = True
                        result["cache_used_dict"][name] = cached is not None
                        result["cache_keys"][name] = cache_key
                        result["prompt"][f"{name}_user_prompt"] = Prompt(
                            canonical(definition)
                        )
                        result["prompt"][f"{name}_system_prompt"] = Prompt(
                            canonical(batch.state)
                        )
                        # Preserve normalized typed output, actual version, and batch
                        # membership. Charge shared usage on just one answer.
                        raw = {
                            "answer": response["answers"][name],
                            "model": response["model"],
                            "batch_key": cache_key,
                            "batch_questions": list(batch.questions),
                        }
                        if definition["type"] == "score":
                            raw["score_from_distribution"] = sum(
                                i * p for i, p in enumerate(distributions[name])
                            )
                            raw["score_difference"] = (
                                response["answers"][name]["score"]
                                - raw["score_from_distribution"]
                            )
                        if name == next(iter(batch.questions)):
                            raw["usage"] = response["usage"]
                            raw["response"] = response
                            for token_name, count in response["usage"].items():
                                result["raw_model_response"][
                                    f"{name}_{token_name}"
                                ] = count
                        result["raw_model_response"][f"{name}_raw_model_response"] = raw
                except Exception as exc:
                    errors.append(f"batch {batch_index}: {exc}")

        workers = [
            asyncio.create_task(worker())
            for _ in range(min(max_concurrency, len(plan.batches)))
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
    complete = [
        result
        for result, row in zip(results, plan.rows)
        if set(result["answer"]) == set(row.questions)
    ]
    output = Results(survey=plan.survey, data=complete, cache=cache)
    if errors:
        raise EvaluationRunError(errors, output)
    return output
