"""Serializable reconstructions of the three remaining experiments in the paper."""

from __future__ import annotations

from edsl import QuestionNumerical, QuestionYesNo, Survey
from edsl.causal import (
    AgentRole,
    CausalAnalysisPlan,
    EndogenousVariable,
    Equation,
    EstimatorSpec,
    ExperimentCompiler,
    ExperimentDesign,
    ExogenousVariable,
    Measurement,
    ParticipantScope,
    PathEffect,
    StructuralCausalModel,
)
from edsl.conversations import AnyStop, CentralOrdered, Conversation, MaxUtterances, OrderedTurns, SemanticStop


def _plan(name, scenario, outcome, causes):
    scm = StructuralCausalModel(
        [*causes, outcome],
        [Equation(outcome, causes, family="linear_probability" if outcome.dtype == "binary" else "linear")],
        name=name,
        metadata={
            "scenario": scenario,
            "source": "Manning, Zhu, and Horton (2024)",
            "replication_kind": "design replication with a contemporary model",
        },
    )
    plan = CausalAnalysisPlan(
        scm,
        [PathEffect(cause, outcome) for cause in causes],
        EstimatorSpec(covariance="HC3"),
    )
    design = ExperimentDesign.factorial(causes, replications=1, seed=name)
    return scm, plan, design


def _stop(question):
    return AnyStop(SemanticStop(judge="conversation-coordinator", question=question), MaxUtterances(20))


def build_bail_hearing_experiment():
    scenario = "A judge is setting bail for a criminal defendant who committed $50,000 in tax fraud."
    bail = EndogenousVariable(
        "bail_amount", "continuous", "USD", "final bail amount set by the judge",
        Measurement("judge", Survey([QuestionNumerical(question_name="bail_amount", question_text="What was the bail amount you set for the defendant, in dollars? Respond with a number only.", min_value=0)]), "bail_amount"),
    )
    history = ExogenousVariable(
        "criminal_history", "count", "prior_convictions", "number of defendant's prior convictions",
        ParticipantScope("defendant"), [0, 1, 2, 3, 6, 9, 12], "The defendant has {{ value }} prior convictions.", visibility="public",
    )
    case_count = ExogenousVariable(
        "judge_case_count", "count", "cases", "number of cases the judge has already heard today",
        ParticipantScope("judge"), [0, 2, 5, 9, 12, 18, 23], "You have already heard {{ value }} cases today.",
    )
    remorse_levels = ["no expressed remorse", "low expressed remorse", "moderate expressed remorse", "high expressed remorse", "extreme expressed remorse"]
    remorse = ExogenousVariable(
        "defendant_remorse", "ordinal", "remorse_level", "defendant's expressed remorse",
        ParticipantScope("defendant"), remorse_levels, "The defendant's level of expressed remorse is {{ value }}.", visibility="public", levels=remorse_levels,
    )
    _, plan, design = _plan("bail-hearing-original-design", scenario, bail, [history, case_count, remorse])
    roles = [
        AgentRole("judge", "conduct the hearing and set a fair bail amount", "on your first turn open the hearing and invite the prosecutor; do not set bail until the prosecutor, defense attorney, and defendant have each spoken; then clearly announce a final bail decision"),
        AgentRole("prosecutor", "argue for bail sufficient to address flight and public-safety risks", "base your argument on the case presented"),
        AgentRole("defense_attorney", "advocate for the lowest reasonable bail", "represent the defendant professionally"),
        AgentRole("defendant", "answer the court and support the request for lower bail", "do not invent facts beyond your assigned attributes"),
    ]
    conversation = Conversation(
        "bail-hearing", ["judge", "prosecutor", "defense_attorney", "defendant"], scenario,
        CentralOrdered(center="judge", others=["prosecutor", "defense_attorney", "defendant"]),
        _stop("Stop only if the prosecutor, defense attorney, and defendant have each spoken and the judge has subsequently announced a final bail amount, or the hearing has otherwise clearly ended after all were heard."),
    )
    return ExperimentCompiler().compile(plan=plan, design=design, roles=roles), conversation, plan


def build_job_interview_experiment():
    scenario = "A person is interviewing for a job as a lawyer."
    hired = EndogenousVariable(
        "hired", "binary", "indicator", "whether the interviewer decides to hire the applicant",
        Measurement("interviewer", Survey([QuestionYesNo(question_name="hired", question_text="Have you decided to hire the job applicant?")]), "hired"), levels=[0, 1],
    )
    bar = ExogenousVariable(
        "passed_bar", "binary", "status", "whether the applicant passed the bar exam",
        ParticipantScope("applicant"), ["Passed", "Not"], "Your bar exam status is: {{ value }}.", levels=["Not", "Passed"],
    )
    friendliness = ExogenousVariable(
        "interviewer_friendliness", "count", "positive_phrases", "number of positive phrases used by interviewer",
        ParticipantScope("interviewer"), [2, 7, 12, 17, 22], "Use approximately {{ value }} positive or friendly phrases during the interview.",
    )
    height = ExogenousVariable(
        "applicant_height", "continuous", "centimeters", "job applicant's height",
        ParticipantScope("applicant"), [160, 165, 170, 175, 180, 185, 190, 195], "Your height is {{ value }} centimeters.",
    )
    _, plan, design = _plan("job-interview-original-design", scenario, hired, [bar, friendliness, height])
    roles = [
        AgentRole("interviewer", "conduct the interview and decide whether to hire", "ask relevant questions and clearly conclude the interview"),
        AgentRole("applicant", "present yourself as a strong candidate for the lawyer position", "answer truthfully according to your assigned attributes"),
    ]
    conversation = Conversation(
        "lawyer-job-interview", ["interviewer", "applicant"], scenario,
        OrderedTurns(["interviewer", "applicant"]),
        _stop("Has the interview reached a natural conclusion or has the interviewer made a hiring decision?"),
    )
    return ExperimentCompiler().compile(plan=plan, design=design, roles=roles), conversation, plan


def build_art_auction_experiment():
    scenario = "Three bidders participate in an open ascending-price auction for a piece of art starting at $50."
    final_price = EndogenousVariable(
        "final_price", "continuous", "USD", "final bid for the piece of art",
        Measurement("auctioneer", Survey([QuestionNumerical(question_name="final_price", question_text="What was the final bid for the piece of art at the end of the auction, in dollars? Respond with a number only.", min_value=0)]), "final_price"),
    )
    budgets = [
        ExogenousVariable(
            f"bidder_{index}_budget", "continuous", "USD", f"bidder {index}'s maximum budget",
            ParticipantScope(f"bidder_{index}"), [50, 100, 150, 200, 250, 300, 350],
            "Your maximum budget for the piece of art is {{ value }} USD.",
        )
        for index in (1, 2, 3)
    ]
    _, plan, design = _plan("art-auction-original-design", scenario, final_price, budgets)
    roles = [
        AgentRole("auctioneer", "run a clear open ascending-price auction and sell to the highest bidder", "start at $50 and invite bidders 1, 2, and 3 in that fixed order; never close before all three have responded; continue repeated rounds while an active bidder might raise; track bids and clearly announce the winner and final price"),
        *[
            AgentRole(f"bidder_{index}", "win the artwork if it is worthwhile", "when invited, state one concrete higher bid not exceeding your private maximum budget, or clearly pass; never bid more than your maximum")
            for index in (1, 2, 3)
        ],
    ]
    conversation = Conversation(
        "art-auction", ["auctioneer", "bidder_1", "bidder_2", "bidder_3"], scenario,
        CentralOrdered(center="auctioneer", others=["bidder_1", "bidder_2", "bidder_3"]),
        _stop("Stop only after bidders 1, 2, and 3 have each spoken at least once and the auctioneer has subsequently closed the auction with a winner and final price, or all bidders have clearly passed."),
        turn_instructions={
            "*": "Use one terse line of at most 12 words. Never add ceremony or explanation.",
            "auctioneer": "State the standing bid and invite the named next eligible bidder. If only one bidder remains active, close immediately at the standing bid instead of inviting another bid.",
            "bidder_1": "Raise by exactly $100; if that exceeds your maximum, bid your maximum only if above the standing bid, otherwise reply 'pass'.",
            "bidder_2": "Raise by exactly $100; if that exceeds your maximum, bid your maximum only if above the standing bid, otherwise reply 'pass'.",
            "bidder_3": "Raise by exactly $100; if that exceeds your maximum, bid your maximum only if above the standing bid, otherwise reply 'pass'.",
        },
        retire_on={"bidder_1": ["pass"], "bidder_2": ["pass"], "bidder_3": ["pass"]},
        turn_contracts={
            f"bidder_{index}": {
                "kind": "numeric_offer_or_pass",
                "maximum_context": f"bidder_{index}_budget",
                "opening": 50,
                "increment": 50,
                "max_jump": 100,
                "currency": "$",
                "pass_token": "pass",
            }
            for index in (1, 2, 3)
        },
    )
    return ExperimentCompiler().compile(plan=plan, design=design, roles=roles), conversation, plan


STUDIES = {
    "bail": build_bail_hearing_experiment,
    "interview": build_job_interview_experiment,
    "auction": build_art_auction_experiment,
}
