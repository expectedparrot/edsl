from __future__ import annotations
from typing import TYPE_CHECKING

from .token_estimate import TokenEstimate
from .cost_estimate import CostEstimate
from .question_estimators import QuestionEstimator
from .file_store_estimator import FileStoreEstimator

if TYPE_CHECKING:
    from ..jobs import Jobs
    from ...surveys.base import EndOfSurveyParent
    from ...surveys import Survey
    from ...interviews.interview import Interview


# ------------------------------------------------------------------
# Reach probability computation


def _compute_reach_probabilities(
    survey: "Survey",
    branch_weights: dict[tuple, float],
) -> tuple[dict[str, float], list[str]]:
    """Derive per-question reach probabilities from branch weights.

    branch_weights keys are (from_question_name, to_question_name_or_EndOfSurvey).
    Processes in survey order so that compounding is correct.
    """
    from ...surveys.base import EndOfSurvey

    question_names = [q.question_name for q in survey.questions]
    n = len(question_names)
    name_to_idx = {name: i for i, name in enumerate(question_names)}
    reach = {name: 1.0 for name in question_names}

    warnings = []

    # Sort by from_q position so probabilities compound correctly
    def sort_key(item):
        (from_q, _), _ = item
        return name_to_idx.get(from_q, -1)

    for (from_q, to_q), weight in sorted(branch_weights.items(), key=sort_key):
        if from_q not in name_to_idx:
            warnings.append(f"branch_weights: unknown question '{from_q}' — skipping.")
            continue

        from_idx = name_to_idx[from_q]

        if to_q is EndOfSurvey or to_q == "EndOfSurvey":
            end_idx = n
        elif to_q in name_to_idx:
            end_idx = name_to_idx[to_q]
        else:
            warnings.append(
                f"branch_weights: unknown destination '{to_q}' from '{from_q}' — skipping."
            )
            continue

        for i in range(from_idx + 1, end_idx):
            reach[question_names[i]] *= 1.0 - weight

    return reach, warnings


def _validate_branch_weights(
    branch_weights: dict[tuple, float],
    survey: "Survey",
    warnings: list[str],
) -> None:
    """Warn if weights from the same question sum to > 1."""
    from collections import defaultdict

    question_names = set(q.question_name for q in survey.questions)
    totals = defaultdict(float)
    for (from_q, _), weight in branch_weights.items():
        if from_q in question_names:
            totals[from_q] += weight

    for q_name, total in totals.items():
        if total > 1.0:
            warnings.append(
                f"branch_weights: weights from '{q_name}' sum to {total:.3f} > 1.0."
            )


# ------------------------------------------------------------------
# Cost conversion


def _compute_cost_usd(
    estimate: TokenEstimate,
    inference_service: str,
    model_name: str,
    price_lookup: dict,
) -> float:
    from ...language_models.price_manager import PriceRetriever

    retriever = PriceRetriever(price_lookup)
    prices = retriever.get_price(inference_service, model_name)

    input_price = retriever.get_price_per_million_tokens(prices, "input") / 1_000_000
    output_price = retriever.get_price_per_million_tokens(prices, "output") / 1_000_000

    return (
        estimate.total_input_tokens * input_price
        + estimate.total_output_tokens * output_price
    )


# ------------------------------------------------------------------
# JobCostEstimator


class JobCostEstimator:
    """Estimates the cost of a Jobs run.

    Args:
        question_estimator: QuestionEstimator instance. If None, uses defaults.
        file_estimator: FileStoreEstimator instance. If None, uses defaults.
    """

    def __init__(
        self,
        question_estimator: QuestionEstimator | None = None,
        file_estimator: FileStoreEstimator | None = None,
    ):
        self.question_estimator = question_estimator or QuestionEstimator()
        self.file_estimator = file_estimator or FileStoreEstimator()

    def estimate_cost(
        self,
        job: "Jobs",
        token_overrides: dict[str, TokenEstimate] | None = None,
        branch_weights: dict[tuple, float] | None = None,
        price_lookup: dict | None = None,
    ) -> CostEstimate:
        """Estimate the cost of running a job.

        Args:
            job: The Jobs instance to estimate.
            token_overrides: Per-question-name TokenEstimate overrides. Only non-None
                fields are applied; others use the estimated value.
            branch_weights: dict keyed by (from_question_name, to_question_name) with
                probability of taking that branch. Used to compute expected cost when
                the survey has skip logic.
            price_lookup: Price dict (keyed by (inference_service, model)). If None,
                fetched from Coop.

        Returns:
            CostEstimate with .detail, .assumptions, and .warnings.
        """
        warnings: list[str] = []

        # Fetch prices
        if price_lookup is None:
            from ...language_models.price_manager import PriceManager

            price_lookup = PriceManager().get_all_prices()

        # Ensure job has agents/models/scenarios populated
        job.replace_missing_objects()

        # Build interview list
        interviews = list(job.generate_interviews())
        if not interviews:
            return CostEstimate(
                rows=[], assumptions=self._build_assumptions(), warnings=warnings
            )

        survey = interviews[0].survey

        # Validate and compute reach probabilities
        reach_probs = {q.question_name: 1.0 for q in survey.questions}
        if branch_weights:
            _validate_branch_weights(branch_weights, survey, warnings)
            reach_probs, bw_warnings = _compute_reach_probabilities(
                survey, branch_weights
            )
            warnings.extend(bw_warnings)
            if branch_weights:
                warnings.append(
                    "branch_weights provided: estimates are expected costs weighted by reach probability. "
                    "Questions not covered by branch_weights default to reach probability 1.0."
                )
        else:
            warnings.append(
                "No branch_weights provided: all questions assumed to be asked (upper bound). "
                "Pass branch_weights to estimate_cost() for surveys with skip logic."
            )

        # Build agent/scenario lookup for detail rows
        agent_lookup = {id(a): i for i, a in enumerate(job.agents)}
        scenario_lookup = {id(s): i for i, s in enumerate(job.scenarios)}

        rows: list[dict] = []

        for interview_idx, interview in enumerate(interviews):
            interview_rows, interview_warnings = self._estimate_interview(
                interview=interview,
                interview_idx=interview_idx,
                survey=survey,
                reach_probs=reach_probs,
                token_overrides=token_overrides or {},
                price_lookup=price_lookup,
                agent_lookup=agent_lookup,
                scenario_lookup=scenario_lookup,
            )
            rows.extend(interview_rows)
            warnings.extend(interview_warnings)

        assumptions = self._build_assumptions(token_overrides, branch_weights)
        return CostEstimate(rows=rows, assumptions=assumptions, warnings=warnings)

    # ------------------------------------------------------------------

    def _estimate_interview(
        self,
        interview: "Interview",
        interview_idx: int,
        survey: "Survey",
        reach_probs: dict[str, float],
        token_overrides: dict[str, TokenEstimate],
        price_lookup: dict,
        agent_lookup: dict,
        scenario_lookup: dict,
    ) -> tuple[list[dict], list[str]]:
        from ..fetch_invigilator import FetchInvigilator
        from ...scenarios import FileStore

        rows: list[dict] = []
        warnings: list[str] = []
        output_estimates: dict[str, int] = (
            {}
        )  # question_name -> estimated output tokens

        fetcher = FetchInvigilator(interview)

        for question in survey.questions:
            q_name = question.question_name
            invigilator = fetcher(question)
            prompts = invigilator.get_prompts()
            model = invigilator.model
            inference_service = model._inference_service_
            model_name = model.model

            # Base estimate from question estimator
            base_estimate, q_warnings = self.question_estimator.estimate(
                question, prompts, model
            )
            warnings.extend(q_warnings)
            estimator_name = self.question_estimator.estimator_name_for(
                question.question_type
            )

            # File tokens
            file_tokens = 0
            for fs in prompts.get("files_list", []):
                if isinstance(fs, FileStore):
                    ft, fw = self.file_estimator.estimate(fs, inference_service)
                    file_tokens += ft
                    warnings.extend(fw)

            # Memory tokens (weighted by reach probability of prior questions)
            memory_entry = survey.memory_plan.get(q_name)
            memory_qs = memory_entry.prior_questions if memory_entry else []
            memory_tokens = sum(
                reach_probs.get(pq, 1.0) * output_estimates.get(pq, 0)
                for pq in memory_qs
            )

            # Assemble full estimate
            full_estimate = TokenEstimate(
                input_tokens=base_estimate.input_tokens,
                file_tokens=file_tokens,
                memory_tokens=int(memory_tokens),
                answer_tokens=base_estimate.answer_tokens,
                comment_tokens=base_estimate.comment_tokens,
                thinking_tokens=base_estimate.thinking_tokens,
            )

            # Apply token_overrides (partial — only non-None fields)
            if q_name in token_overrides:
                full_estimate = full_estimate.merge(token_overrides[q_name])
                estimator_name = f"manual override (base: {estimator_name})"

            # Store weighted output for downstream memory
            reach = reach_probs.get(q_name, 1.0)
            output_estimates[q_name] = int(reach * full_estimate.total_output_tokens)

            # Cost
            cost_usd = _compute_cost_usd(
                full_estimate, inference_service, model_name, price_lookup
            )

            row = {
                "interview_index": interview_idx,
                "question_name": q_name,
                "agent_index": agent_lookup.get(id(interview.agent), 0),
                "scenario_index": scenario_lookup.get(id(interview.scenario), 0),
                "model": model_name,
                "inference_service": inference_service,
                "estimator_used": estimator_name,
                "reach_probability": reach,
                **full_estimate.to_detail_row(),
                "cost_usd": cost_usd,
            }
            rows.append(row)

        return rows, warnings

    def _build_assumptions(
        self,
        token_overrides: dict | None = None,
        branch_weights: dict | None = None,
    ) -> dict:
        return {
            "chars_per_token": 4,
            "question_estimator": repr(self.question_estimator.__class__.__name__),
            "file_estimator": repr(self.file_estimator.__class__.__name__),
            "token_overrides_applied": (
                list(token_overrides.keys()) if token_overrides else []
            ),
            "branch_weights_applied": bool(branch_weights),
        }
