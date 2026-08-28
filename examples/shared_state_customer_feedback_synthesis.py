"""Evidence-backed, multi-role synthesis of a customer-feedback CSV."""

import csv
from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionDict,
    QuestionList,
    QuestionMatrix,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


HERE = Path(__file__).resolve().parent
FEEDBACK_PATH = HERE / "customer_feedback_sample.csv"


def load_feedback(path: str | Path = FEEDBACK_PATH) -> list[dict[str, str]]:
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def reviewers() -> AgentList:
    specs = [
        ("Priya", "product manager", "product gaps, frequency, and roadmap impact"),
        (
            "Marcus",
            "customer support lead",
            "customer pain, urgency, and support burden",
        ),
        ("Elena", "UX researcher", "usability, accessibility, and user context"),
        (
            "Noah",
            "business analyst",
            "segment patterns, retention risk, and evidence strength",
        ),
    ]
    return AgentList(
        [
            Agent(name=name, traits={"role": role, "lens": lens})
            for name, role, lens in specs
        ]
    )


def formatted_feedback(feedback: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{row['comment_id']} [{row['segment']}]: {row['comment']}" for row in feedback
    )


def discovery_survey(state: SharedState, feedback: list[dict[str, str]]) -> Survey:
    proposal = QuestionDict(
        question_name="theme_proposal",
        question_text=(
            "Round {{ run.round }}. You are {{ agent.name }}, the {{ agent.role }}, "
            "focused on {{ agent.lens }}.\n\nCustomer comments:\n"
            f"{formatted_feedback(feedback)}\n\nThemes already proposed:\n"
            "{{ shared_state.proposals.entries }}\n\nPropose one important theme not "
            "already adequately represented. Every claim must cite exact comment IDs."
        ),
        answer_keys=["theme", "evidence_ids", "interpretation", "recommended_action"],
        value_types=["str", "list", "str", "str"],
        value_descriptions=[
            "Short, neutral theme name",
            "List of supporting comment IDs such as C03",
            "What the cited comments collectively show",
            "A concrete company action",
        ],
    )
    return Survey(
        [
            proposal,
            state.proposals.append(
                analyst="{{ agent.name }}", round="{{ run.round }}", proposal=proposal
            ),
        ]
    )


def synthesis_survey(state: SharedState, feedback: list[dict[str, str]]) -> Survey:
    synthesis = QuestionList(
        question_name="canonical_theme_names",
        question_text=(
            "You are an impartial research lead. Consolidate overlapping proposals "
            "into exactly five decision-useful themes. Preserve minority observations, "
            "do not invent prevalence, and use only valid evidence IDs.\n\nComments:\n"
            f"{formatted_feedback(feedback)}\n\nAnalyst proposals:\n"
            "{{ shared_state.proposals.entries }}\n\nReturn exactly five short, distinct "
            "canonical theme names."
        ),
        min_list_items=5,
        max_list_items=5,
    )
    return Survey([synthesis, state.synthesis.append(names=synthesis)])


def theme_editors(names: list[str]) -> AgentList:
    return AgentList(
        [
            Agent(
                name=f"Theme editor {index}",
                traits={"theme_order": index, "theme_name": name},
            )
            for index, name in enumerate(names, 1)
        ]
    )


def theme_detail_survey(state: SharedState, feedback: list[dict[str, str]]) -> Survey:
    detail = QuestionDict(
        question_name="theme_detail",
        question_text=(
            "Develop only the canonical theme '{{ agent.theme_name }}'. Use the "
            "original comments and analyst proposals. Every finding must cite exact "
            "comment IDs; do not invent frequency.\n\nComments:\n"
            f"{formatted_feedback(feedback)}\n\nProposals:\n"
            "{{ shared_state.proposals.entries }}"
        ),
        answer_keys=["evidence_ids", "finding", "action"],
        value_types=["list", "str", "str"],
        value_descriptions=[
            "Supporting comment IDs",
            "Concise evidence-grounded finding",
            "Concrete recommended company action",
        ],
    )
    return Survey(
        [
            detail,
            state.theme_details.append(
                editor_order="{{ agent.theme_order }}",
                theme_name="{{ agent.theme_name }}",
                detail=detail,
            ),
        ]
    )


def canonical_themes(state: SharedState) -> list[dict]:
    entries = state.read().state["theme_details"]["entries"]
    if len(entries) < 5:
        raise ValueError("synthesis requires five persisted theme details")
    latest = {int(entry["editor_order"]): entry for entry in entries}
    return [
        {
            "id": f"T{order}",
            "name": latest[order]["theme_name"],
            **latest[order]["detail"],
        }
        for order in range(1, 6)
    ]


def prioritization_survey(state: SharedState, themes: list[dict]) -> Survey:
    theme_ids = [theme["id"] for theme in themes]
    slate = "\n".join(
        f"{theme['id']}: {theme['name']} — {theme['finding']} Evidence: {theme['evidence_ids']}"
        for theme in themes
    )
    vote = QuestionMatrix(
        question_name="priority_votes",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}, focused on "
            f"{{{{ agent.lens }}}}. Rate every consolidated theme.\n\n{slate}\n\n"
            "Use high for an urgent next-quarter priority, medium for planned work, "
            "and low for monitoring or later action."
        ),
        question_items=theme_ids,
        question_options=["high", "medium", "low"],
        randomize_items=True,
    )
    return Survey([vote, state.priorities.append(voter="{{ agent.name }}", votes=vote)])


def score_priorities(state: SharedState, themes: list[dict]) -> list[dict]:
    scores = {theme["id"]: 0 for theme in themes}
    weights = {"high": 2, "medium": 1, "low": 0}
    for entry in state.read().state["priorities"]["entries"]:
        for theme_id, vote in entry["votes"].items():
            scores[theme_id] += weights[vote]
    return sorted(
        (dict(theme) | {"priority_score": scores[theme["id"]]} for theme in themes),
        key=lambda theme: (-theme["priority_score"], theme["id"]),
    )


def run_customer_feedback_synthesis(
    log_path: str | Path = "customer-feedback-synthesis-live.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, list[dict]]:
    feedback = load_feedback()
    state = SharedState(
        "customer-feedback-synthesis",
        FileStateStore(log_path),
        proposals=SharedLog(),
        synthesis=SharedLog(),
        theme_details=SharedLog(),
        priorities=SharedLog(),
    )
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    proposal_count = state.read().state["proposals"]["count"]
    if proposal_count < 4:
        discovery_survey(state, feedback).by(reviewers()).by(model).run(
            interview_schedule=InterviewSchedule.rounds(
                count=2,
                within_round="concurrent",
                state_visibility="snapshot",
                round_order="rotate",
            ),
            **options,
        )
    proposal_count = state.read().state["proposals"]["count"]
    if proposal_count < 4:
        raise RuntimeError(
            f"discovery incomplete: expected at least 4 persisted proposals, got {proposal_count}"
        )
    facilitator = Agent(
        name="Ruth",
        traits={"role": "research synthesis lead"},
    )
    if state.read().state["synthesis"]["count"] == 0:
        synthesis_survey(state, feedback).by(facilitator).by(model).run(**options)
    if state.read().state["synthesis"]["count"] == 0:
        raise RuntimeError("consolidation incomplete: no synthesis was persisted")
    names = state.read().state["synthesis"]["entries"][-1]["names"]
    if state.read().state["theme_details"]["count"] < 5:
        theme_detail_survey(state, feedback).by(theme_editors(names)).by(model).run(
            **options
        )
    detail_count = state.read().state["theme_details"]["count"]
    if detail_count < 5:
        raise RuntimeError(
            f"theme detailing incomplete: expected 5 persisted details, got {detail_count}"
        )
    themes = canonical_themes(state)
    if state.read().state["priorities"]["count"] < len(reviewers()):
        prioritization_survey(state, themes).by(reviewers()).by(model).run(**options)
    ballot_count = state.read().state["priorities"]["count"]
    if ballot_count < len(reviewers()):
        raise RuntimeError(
            f"prioritization incomplete: expected 4 persisted ballots, got {ballot_count}"
        )
    ranked = score_priorities(state, themes)
    state.close()
    return state, ranked


if __name__ == "__main__":
    shared_state, ranked_themes = run_customer_feedback_synthesis()
    print(shared_state.render_markdown())
    print("\nPrioritized themes:")
    for theme in ranked_themes:
        print(
            f"- {theme['name']} ({theme['priority_score']}/8): "
            f"{theme['finding']} → {theme['action']}"
        )
