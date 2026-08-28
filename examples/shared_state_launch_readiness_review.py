"""Evidence-backed product launch review with mitigations, vetoes, and dissent."""

from pathlib import Path
from statistics import median

from edsl import (
    Agent,
    AgentList,
    Model,
    QuestionDict,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


LAUNCH = "Enterprise Permissions launch on September 30, 2026"
REVIEW_DATE = "August 28, 2026"
COMMON_STATUS = """
- Core implementation is feature-complete; automated acceptance tests pass at 93%.
- Two medium-severity security findings remain open; no critical findings are known.
- Updated data-processing terms are drafted but not yet signed off by Legal.
- Administrator documentation is approximately 80% complete.
- Three lighthouse customers have committed to the date.
- Launch-week support coverage exists, but the escalation runbook is incomplete.
""".strip()


def reviewers() -> AgentList:
    specs = [
        (
            "Maya",
            "Product",
            "B1",
            "customer value, scope coherence, and adoption",
            False,
            "Beta users completed key workflows, but bulk role editing remains confusing.",
        ),
        (
            "Eli",
            "Engineering",
            "B2",
            "technical quality, reliability, and delivery capacity",
            False,
            "Load tests pass at expected volume; rollback automation has not had a full rehearsal.",
        ),
        (
            "Dev",
            "Security",
            "B3",
            "security exposure and control effectiveness",
            True,
            "One open finding concerns privileged-session timeout; exploitability is moderate and mitigation is designed.",
        ),
        (
            "Lena",
            "Legal",
            "B4",
            "contractual obligations, privacy, and regulatory exposure",
            True,
            "The revised DPA language is acceptable in principle but needs final outside-counsel confirmation.",
        ),
        (
            "Sofia",
            "Sales",
            "B5",
            "revenue commitments and market credibility",
            False,
            "Three enterprise buyers tie Q4 expansions to launch, but one expects a bulk-administration feature not in scope.",
        ),
        (
            "Farid",
            "Customer Success",
            "B6",
            "implementation readiness and customer outcomes",
            False,
            "Implementation teams can onboard lighthouse accounts; administrator training materials are incomplete.",
        ),
        (
            "Omar",
            "Operations",
            "B7",
            "supportability, observability, and incident response",
            False,
            "Dashboards and alerts exist; escalation ownership after US business hours is still ambiguous.",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "function": function,
                    "blocker_id": blocker_id,
                    "lens": lens,
                    "veto_authority": veto,
                    "private_evidence": evidence,
                },
            )
            for name, function, blocker_id, lens, veto, evidence in specs
        ]
    )


def initial_assessment_survey(state: SharedState) -> Survey:
    score = QuestionNumerical(
        question_name="initial_readiness",
        question_text=(
            f"Private initial review of {LAUNCH}. You represent {{{{ agent.function }}}} "
            "and focus on {{ agent.lens }}.\n\nCommon status:\n"
            f"{COMMON_STATUS}\n\nPrivate evidence available to your function:\n"
            "{{ agent.private_evidence }}\n\nScore readiness from 0 to 100 before "
            "seeing anyone else's assessment. Use these anchors: 0 means impossible "
            "or prohibited; 50 means material unresolved blockers; 75 means ready only "
            "with explicit conditions; 100 means fully verified and ready."
        ),
        min_value=0,
        max_value=100,
    )
    recommendation = QuestionMultipleChoice(
        question_name="initial_recommendation",
        question_text="Give your private initial recommendation.",
        question_options=["launch", "limited_launch", "delay"],
    )
    blocker = QuestionDict(
        question_name="primary_blocker",
        question_text=(
            "Document the single most decision-relevant blocker or concern from your "
            "function. If none is launch-blocking, document the most important residual "
            "risk. Keep each field under 40 words."
        ),
        answer_keys=["title", "severity", "evidence", "owner_function"],
        value_types=["str", "str", "str", "str"],
        value_descriptions=[
            "Short blocker title",
            "One of critical, high, medium, or low",
            "Concrete evidence rather than general concern",
            "Function accountable for mitigation",
        ],
    )
    rationale = QuestionFreeText(
        question_name="initial_rationale",
        question_text=(
            "Explain your score and recommendation in at most 60 words, citing the "
            "common status or your private evidence."
        ),
    )
    return Survey(
        [
            score,
            recommendation,
            blocker,
            rationale,
            state.assessments.append(
                reviewer="{{ agent.name }}",
                function="{{ agent.function }}",
                stage="initial",
                score=score,
                recommendation=recommendation,
                rationale=rationale,
            ),
            state.blockers.append(
                blocker_id="{{ agent.blocker_id }}",
                reporter_function="{{ agent.function }}",
                blocker=blocker,
            ),
        ]
    )


def mitigation_survey(state: SharedState) -> Survey:
    context = (
        "You represent {{ agent.function }}. All independently submitted blockers "
        "are now revealed simultaneously:\n{{ shared_state.blockers.entries }}\n\n"
    )
    addressed = QuestionFreeText(
        question_name="addressed_blockers",
        question_text=(
            context
            + "List the comma-separated blocker IDs your function can materially address. "
            f"The review date is {REVIEW_DATE} and launch is September 30, 2026."
        ),
    )
    mitigation = QuestionFreeText(
        question_name="mitigation_plan",
        question_text="State the concrete mitigation or scope restriction in at most 55 words.",
    )
    evidence = QuestionFreeText(
        question_name="verification_evidence",
        question_text=(
            "State the evidence already available or required to verify the mitigation. "
            "Do not claim closure without evidence. At most 55 words."
        ),
    )
    residual = QuestionFreeText(
        question_name="residual_risk",
        question_text="State the risk remaining after mitigation in at most 45 words.",
    )
    deadline = QuestionFreeText(
        question_name="mitigation_deadline",
        question_text=(
            f"Give a specific deadline between {REVIEW_DATE} and September 30, 2026."
        ),
    )
    return Survey(
        [
            addressed,
            mitigation,
            evidence,
            residual,
            deadline,
            state.mitigations.append(
                owner="{{ agent.name }}",
                owner_function="{{ agent.function }}",
                addressed_blocker_ids=addressed,
                mitigation=mitigation,
                verification_evidence=evidence,
                residual_risk=residual,
                deadline=deadline,
            ),
        ]
    )


def final_assessment_survey(state: SharedState) -> Survey:
    score = QuestionNumerical(
        question_name="final_readiness",
        question_text=(
            "Reassess launch readiness independently after reviewing all blockers and "
            "mitigations.\n\nBlockers:\n{{ shared_state.blockers.entries }}\n\n"
            "Mitigations:\n{{ shared_state.mitigations.entries }}\n\nScore 0 to 100. "
            "Use these anchors: 0 means impossible or prohibited; 50 means material "
            "unresolved blockers; 75 means ready only with explicit conditions; 100 "
            "means fully verified and ready."
        ),
        min_value=0,
        max_value=100,
    )
    recommendation = QuestionMultipleChoice(
        question_name="final_recommendation",
        question_text=(
            "Give your final recommendation. A limited launch means only the three "
            "lighthouse customers with explicit controls."
        ),
        question_options=["launch", "limited_launch", "delay"],
    )
    approval = QuestionMultipleChoice(
        question_name="approval_status",
        question_text=(
            "State whether your function approves unconditionally, approves subject "
            "to a stated condition, or does not approve."
        ),
        question_options=["approved", "conditional", "not_approved"],
    )
    condition = QuestionFreeText(
        question_name="approval_condition",
        question_text=(
            "State the exact approval condition, or 'none' if unconditional. Include "
            "what evidence closes it and a deadline no later than September 30, 2026. "
            "At most 55 words."
        ),
    )
    rationale = QuestionFreeText(
        question_name="final_rationale",
        question_text=(
            "Briefly explain what changed or did not change your assessment. Preserve "
            "any dissent from the apparent group direction. At most 60 words."
        ),
    )
    return Survey(
        [
            score,
            recommendation,
            approval,
            condition,
            rationale,
            state.final_reviews.append(
                reviewer="{{ agent.name }}",
                function="{{ agent.function }}",
                veto_authority="{{ agent.veto_authority }}",
                score=score,
                recommendation=recommendation,
                approval=approval,
                condition=condition,
                rationale=rationale,
            ),
        ]
    )


def require_count(state: SharedState, primitive: str, expected: int) -> None:
    count = state.read().state[primitive]["count"]
    if count < expected:
        raise RuntimeError(
            f"{primitive} incomplete: expected {expected} persisted records, got {count}"
        )


def missing_reviewers(
    state: SharedState,
    agents: AgentList,
    primitive: str,
    identity_field: str,
) -> AgentList:
    completed = {
        entry[identity_field] for entry in state.read().state[primitive]["entries"]
    }
    return AgentList([agent for agent in agents if agent.name not in completed])


def decide(state: SharedState) -> dict:
    initial = state.read().state["assessments"]["entries"]
    final = state.read().state["final_reviews"]["entries"]
    mitigations = state.read().state["mitigations"]["entries"]
    vetoes = [
        review
        for review in final
        if review["veto_authority"]
        and (
            review["recommendation"] == "delay" or review["approval"] == "not_approved"
        )
    ]
    final_scores = [review["score"] for review in final]
    recommendations = [review["recommendation"] for review in final]
    if vetoes:
        decision = "delay"
    elif median(final_scores) >= 75 and recommendations.count("launch") >= 4:
        decision = "launch"
    elif median(final_scores) >= 60 and recommendations.count("delay") <= 2:
        decision = "limited_launch"
    else:
        decision = "delay"
    conditions = [
        {
            "function": review["function"],
            "condition": review["condition"],
        }
        for review in final
        if review["approval"] != "approved"
        or review["condition"].strip().lower() != "none"
    ]
    dissent = [
        {
            "function": review["function"],
            "recommendation": review["recommendation"],
            "rationale": review["rationale"],
        }
        for review in final
        if review["recommendation"] != decision
    ]
    initial_by_function = {item["function"]: item for item in initial}
    movement = {
        review["function"]: review["score"]
        - initial_by_function[review["function"]]["score"]
        for review in final
    }
    return {
        "decision": decision,
        "initial_median": median(item["score"] for item in initial),
        "final_median": median(final_scores),
        "score_movement": movement,
        "vetoes": vetoes,
        "conditions": conditions,
        "dissent": dissent,
        "owners_and_deadlines": [
            {
                "owner": item["owner"],
                "function": item["owner_function"],
                "blockers": item.get("response", item)["addressed_blocker_ids"],
                "deadline": item.get("response", item)["deadline"],
            }
            for item in mitigations
        ],
    }


def run_launch_review(
    log_path: str | Path = "launch-readiness-review-live.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, dict]:
    state = SharedState(
        "enterprise-permissions-launch",
        FileStateStore(log_path),
        assessments=SharedLog(),
        blockers=SharedLog(),
        mitigations=SharedLog(),
        final_reviews=SharedLog(),
    )
    agents = reviewers()
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    initial_missing = AgentList(
        [
            agent
            for agent in agents
            if agent.name
            not in {
                entry["reviewer"]
                for entry in state.read().state["assessments"]["entries"]
            }
            or agent.traits["blocker_id"]
            not in {
                entry["blocker_id"]
                for entry in state.read().state["blockers"]["entries"]
            }
        ]
    )
    if initial_missing:
        initial_assessment_survey(state).by(initial_missing).by(model).run(**options)
    require_count(state, "assessments", 7)
    require_count(state, "blockers", 7)
    mitigation_missing = missing_reviewers(state, agents, "mitigations", "owner")
    if mitigation_missing:
        mitigation_survey(state).by(mitigation_missing).by(model).run(**options)
    require_count(state, "mitigations", 7)
    final_missing = missing_reviewers(state, agents, "final_reviews", "reviewer")
    if final_missing:
        final_assessment_survey(state).by(final_missing).by(model).run(**options)
    require_count(state, "final_reviews", 7)
    decision = decide(state)
    state.close()
    return state, decision


if __name__ == "__main__":
    shared_state, launch_decision = run_launch_review()
    print(shared_state.render_markdown())
    print(f"\nDecision record: {launch_decision}")
