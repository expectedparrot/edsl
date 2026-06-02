from __future__ import annotations
from typing import TYPE_CHECKING

from .cost_estimation_constants import EDSL_DEFAULT_CHARS_PER_TOKEN
from .file_store_estimator import FileStoreEstimator
from .job_cost_estimate import JobCostEstimate
from .question_estimators import QuestionEstimator
from .question_token_estimate import QuestionTokenEstimate

if TYPE_CHECKING:
    from ..jobs import Jobs
    from ...surveys import Survey
    from ...interviews.interview import Interview
    from ...invigilators.invigilators import InvigilatorBase


# ------------------------------------------------------------------
# Reach probability computation


def _compute_reach_probabilities(
    survey: "Survey",
    branch_weights: dict[tuple, float],
) -> tuple[dict[str, float], list[str]]:
    """Derive per-question reach probabilities from branch weights.

    Uses forward propagation: each question distributes its reach to successors.
    Branch destinations get their weighted share; the default next question gets
    the remainder. This correctly handles destinations reachable via multiple paths.

    Simple skip:
        {("q1", "q5"): 0.7}  →  q2/q3/q4 reach = 0.3, q5 reach = 1.0

    Weights are conditional probabilities — the user specifies the fraction of
    respondents *at that question* who take the branch, without needing to know
    the question's reach. The algorithm multiplies reach by weight internally.

        {("q1", "q4"): 0.9, ("q2", "q5"): 0.8}
        q1 receives: 1.0 (initial);       sends: 1.0*0.9=0.9 to q4,  1.0*0.1=0.1 to q2
        q2 receives: 0.1 (from q1);       sends: 0.1*0.8=0.08 to q5,  0.1*0.2=0.02 to q3
        q3 receives: 0.02 (from q2);      sends: 0.02 to q4
        q4 receives: 0.9+0.02=0.92;       sends: 0.92 to q5
        q5 receives: 0.08+0.92=1.0        [terminal — all paths converge]

    Returns:
        reach: dict mapping question_name -> reach probability in [0.0, 1.0].
        warnings: unrecognised names, destinations, or weight sums > 1.
    """
    from collections import defaultdict
    from ...surveys.base import EndOfSurvey

    question_names = survey.question_names  # cached property
    name_to_idx = survey.question_name_to_index  # cached property
    n = len(question_names)
    warnings = []

    # Parse branch_weights into outbound edges per question.
    # branch_weights is a flat dict of (from_q, to_q) -> weight edges. We regroup
    # it into an adjacency list — outbound[q_name] = [(dest_idx, weight), ...] —
    # so the propagation loop can look up all outgoing edges for a question in
    # one call rather than scanning all of branch_weights on every iteration.
    # dest_idx is the integer position of the destination in question_names,
    # or n (past the end) if the destination is EndOfSurvey.
    outbound: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for (from_q, to_q), weight in branch_weights.items():
        if from_q not in name_to_idx:
            # User referenced a question name that doesn't exist in this survey.
            warnings.append(f"branch_weights: unknown question '{from_q}' — skipping.")
            continue
        if to_q is EndOfSurvey or to_q == "EndOfSurvey":
            # EndOfSurvey has no index in question_names. We store n (one past
            # the last valid index) so the propagation loop can check dest_idx < n
            # to tell the difference between "forward to a question" and
            # "the survey ends here" — and add the probability to eos_absorbed
            # instead of forwarding it.
            dest_idx = n
        elif to_q in name_to_idx:
            dest_idx = name_to_idx[to_q]
        else:
            warnings.append(
                f"branch_weights: unknown destination '{to_q}' from '{from_q}' — skipping."
            )
            continue
        outbound[from_q].append((dest_idx, weight))

    # Warn if weights from any single question sum to > 1.
    for from_q, edges in outbound.items():
        total = sum(w for _, w in edges)
        if total > 1.0:
            warnings.append(
                f"branch_weights: weights from '{from_q}' sum to {total:.3f} > 1.0."
            )

    # Forward propagation: distribute reach from each question to its successors.
    reach: dict[str, float] = {name: 0.0 for name in question_names}
    if question_names:
        reach[question_names[0]] = 1.0  # every respondent starts at the first question

    eos_absorbed = 0.0  # probability absorbed by EndOfSurvey exits

    for i, q_name in enumerate(question_names):
        r = reach[q_name]
        if r == 0.0:
            continue  # no respondents reach this question; nothing to distribute

        edges = outbound.get(q_name, [])
        branch_total = sum(
            w for _, w in edges
        )  # total probability leaving via skip rules

        # Distribute this question's reach across each skip destination proportionally to its weight.
        for dest_idx, weight in edges:
            if dest_idx < n:
                reach[question_names[dest_idx]] += r * weight
            else:
                eos_absorbed += r * weight  # respondents who exit the survey here

        # Whatever probability didn't go to a skip destination flows to the next
        # question in sequence (the default path when no rule fires).
        if i + 1 < n:
            reach[question_names[i + 1]] += r * max(0.0, 1.0 - branch_total)

    # Total across all terminal points (last question + EndOfSurvey exits) should be 1.0.
    if question_names:
        total = reach[question_names[-1]] + eos_absorbed
        if abs(total - 1.0) > 1e-6:
            warnings.append(
                f"branch_weights: terminal probability sums to {total:.4f}, not 1.0 — "
                f"weights may be inconsistent."
            )

    return reach, warnings


# ------------------------------------------------------------------
# Cost conversion


def _compute_cost_usd(
    estimate: QuestionTokenEstimate,
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
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
        question_estimator: QuestionEstimator | None = None,
        file_estimator: FileStoreEstimator | None = None,
    ):
        self.chars_per_token = chars_per_token
        self.question_estimator = question_estimator or QuestionEstimator(
            chars_per_token=chars_per_token
        )
        self.file_estimator = file_estimator or FileStoreEstimator(
            chars_per_token=chars_per_token
        )

    def estimate_cost(
        self,
        job: "Jobs",
        token_overrides: dict[str, QuestionTokenEstimate] | None = None,
        branch_weights: dict[tuple, float] | None = None,
        price_lookup: dict | None = None,
    ) -> JobCostEstimate:
        """Estimate the cost of running a job.

        Args:
            job: The Jobs instance to estimate.
            token_overrides: Per-question-name QuestionTokenEstimate overrides. Only non-None
                fields are applied; others use the estimated value.
            branch_weights: dict keyed by (from_question_name, to_question_name) with
                probability of taking that branch. Used to compute expected cost when
                the survey has skip logic.
            price_lookup: Price dict (keyed by (inference_service, model)). If None,
                fetched from Coop.

        Returns:
            JobCostEstimate with .detail, .assumptions, and .warnings.
        """
        warnings: list[str] = []

        # Fetch prices
        if price_lookup is None:
            from ...language_models.price_manager import PriceManager

            price_lookup = PriceManager().get_all_prices()

        # Ensure job has agents/models/scenarios populated
        job.replace_missing_objects()

        # Build interview list
        interviews: list["Interview"] = list(job.generate_interviews())
        if not interviews:
            return JobCostEstimate(
                rows=[], assumptions=self._build_assumptions(), warnings=warnings
            )

        survey = interviews[0].survey

        # Validate and compute reach probabilities
        reach_probs = {q.question_name: 1.0 for q in survey.questions}
        if branch_weights:
            reach_probs, bw_warnings = _compute_reach_probabilities(
                survey, branch_weights
            )
            warnings.extend(bw_warnings)
            warnings.append(
                "branch_weights provided: estimates are expected costs weighted by reach probability. "
                "Questions not covered by branch_weights default to reach probability 0.0."
            )
        else:
            warnings.append(
                "No branch_weights provided: skip logic in the survey is ignored and the survey "
                "is assumed to proceed linearly with every question asked by every respondent. "
                "This is a worst-case upper bound. Pass branch_weights to estimate_cost() "
                "to account for skip logic."
            )

        # Map object identity -> position index so each detail row can record
        # which agent/scenario it came from as a simple integer (0, 1, 2, ...)
        # without an O(n) list scan per interview.
        agent_index_lookup = {id(a): i for i, a in enumerate(job.agents)}
        scenario_index_lookup = {id(s): i for i, s in enumerate(job.scenarios)}

        rows: list[dict] = []

        for interview_idx, interview in enumerate(interviews):
            interview_rows, interview_warnings = self._estimate_interview_cost(
                interview=interview,
                interview_idx=interview_idx,
                survey=survey,
                reach_probs=reach_probs,
                token_overrides=token_overrides or {},
                price_lookup=price_lookup,
                agent_index_lookup=agent_index_lookup,
                scenario_index_lookup=scenario_index_lookup,
            )
            rows.extend(interview_rows)
            warnings.extend(interview_warnings)

        assumptions = self._build_assumptions(token_overrides, branch_weights)
        return JobCostEstimate(rows=rows, assumptions=assumptions, warnings=warnings)

    # ------------------------------------------------------------------

    def _estimate_interview_cost(
        self,
        interview: "Interview",
        interview_idx: int,
        survey: "Survey",
        reach_probs: dict[str, float],
        token_overrides: dict[str, QuestionTokenEstimate],
        price_lookup: dict,
        agent_index_lookup: dict,
        scenario_index_lookup: dict,
    ) -> tuple[list[dict], list[str]]:
        from ..fetch_invigilator import FetchInvigilator
        from ...surveys.memory.memory import Memory

        rows: list[dict] = []
        warnings: list[str] = []
        output_estimates: dict[str, int] = (
            {}
        )  # question_name -> estimated output tokens

        fetcher = FetchInvigilator(interview)

        for question in survey.questions:
            q_name = question.question_name
            invigilator: "InvigilatorBase" = fetcher(question)
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
                ft, fw = self.file_estimator.estimate(fs, inference_service)
                file_tokens += ft
                warnings.extend(fw)

            # Memory tokens (weighted by reach probability of prior questions)
            memory_entry = survey.memory_plan.get(q_name)
            # Memory is a UserList of question name strings — iterate directly.
            memory_qs = list(memory_entry) if isinstance(memory_entry, Memory) else []
            # Each prior question contributes its estimated output tokens weighted
            # by its reach probability — if a prior question was likely skipped,
            # its memory contribution is proportionally smaller. Defaults to
            # reach=1.0 (always asked) for questions not covered by branch_weights.
            memory_tokens = sum(
                reach_probs.get(pq, 1.0) * output_estimates.get(pq, 0)
                for pq in memory_qs
            )

            # Assemble full estimate
            full_estimate = QuestionTokenEstimate(
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

            # Store expected output tokens for use by downstream memory calculations.
            # Scaled by reach probability so that a question only reached 30% of the
            # time contributes proportionally less to later questions' memory overhead.
            reach = reach_probs.get(q_name, 1.0)
            output_estimates[q_name] = int(reach * full_estimate.total_output_tokens)

            # Cost — zero for non-billable questions (compute, functional)
            if full_estimate.billable:
                cost_usd = _compute_cost_usd(
                    full_estimate, inference_service, model_name, price_lookup
                )
            else:
                cost_usd = 0.0

            row = {
                "interview_index": interview_idx,
                "question_name": q_name,
                "agent_index": agent_index_lookup.get(id(interview.agent), 0),
                "scenario_index": scenario_index_lookup.get(id(interview.scenario), 0),
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
        assumptions: dict = {
            "chars_per_token": self.chars_per_token,
            "question_estimator": repr(self.question_estimator.__class__.__name__),
            "file_estimator": repr(self.file_estimator.__class__.__name__),
            "token_overrides_applied": (
                list(token_overrides.keys()) if token_overrides else []
            ),
            "branch_weights_applied": bool(branch_weights),
        }

        # Only report per-type/MIME deviations when a custom estimator was passed
        # with a different chars_per_token than the top-level default.
        q_cpt: int | None = getattr(self.question_estimator, "chars_per_token", None)
        if q_cpt is not None and q_cpt != self.chars_per_token:
            assumptions["chars_per_token_questions"] = q_cpt

        per_type_overrides: dict[str, int] = getattr(
            self.question_estimator, "chars_per_token_overrides", {}
        )
        if per_type_overrides:
            assumptions["chars_per_token_question_type_overrides"] = per_type_overrides

        f_cpt: int | None = getattr(self.file_estimator, "chars_per_token", None)
        if f_cpt is not None and f_cpt != self.chars_per_token:
            assumptions["chars_per_token_files"] = f_cpt

        per_mime_overrides: dict[str, int] = getattr(
            self.file_estimator, "chars_per_token_overrides", {}
        )
        if per_mime_overrides:
            assumptions["chars_per_token_mime_overrides"] = per_mime_overrides

        return assumptions
