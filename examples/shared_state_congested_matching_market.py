"""A congested matching market that exercises deferred-acceptance rejection chains."""

import json

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionRank, Survey
from edsl.sharedstate import FileStateStore, SharedDeferredAcceptance, SharedState


PROGRAMS = {
    "Northstar": "Traditional quantitative public policy with a theoretical core.",
    "Lakeside": "Environmental policy with fieldwork and a small rural cohort.",
    "CivicLab": "Technology governance with applied AI projects and city internships.",
}
CAPACITIES = {"Northstar": 2, "Lakeside": 2, "CivicLab": 2}
PRIORITIES = {
    "Northstar": ["Diego", "Amina", "Evan", "Chloe", "Ben", "Farah"],
    "Lakeside": ["Chloe", "Evan", "Amina", "Farah", "Diego", "Ben"],
    "CivicLab": ["Farah", "Ben", "Amina", "Diego", "Chloe", "Evan"],
}


def applicants() -> AgentList:
    specs = [
        ("Amina", "AI regulation", "CivicLab", "Northstar", "Lakeside"),
        ("Ben", "civic technology", "CivicLab", "Northstar", "Lakeside"),
        (
            "Chloe",
            "digital environmental governance",
            "CivicLab",
            "Lakeside",
            "Northstar",
        ),
        ("Diego", "public-sector data science", "CivicLab", "Northstar", "Lakeside"),
        ("Evan", "environmental justice", "Lakeside", "Northstar", "CivicLab"),
        ("Farah", "algorithmic accountability", "CivicLab", "Northstar", "Lakeside"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "interest": interest,
                    "ideal": first,
                    "fallback": second,
                    "last_choice": third,
                },
            )
            for name, interest, first, second, third in specs
        ]
    )


def preference_survey(state: SharedState) -> Survey:
    descriptions = "\n".join(
        f"{program}: {description}" for program, description in PROGRAMS.items()
    )
    ranking = QuestionRank(
        question_name="program_ranking",
        question_text=(
            "You are {{ agent.name }}, focused on {{ agent.interest }}. After careful "
            "research, your genuine preference is {{ agent.ideal }} first, "
            "{{ agent.fallback }} second, and {{ agent.last_choice }} third. Submit "
            "that complete private ranking; do not strategize about admissions.\n\n"
            f"Program descriptions:\n{descriptions}"
        ),
        question_options=list(PROGRAMS),
    )
    return Survey([ranking, state.market.collect(ranking)])


def blocking_pairs(state: SharedState, log_path: str | Path) -> list[tuple[str, str]]:
    requests = {}
    for line in Path(log_path).read_text().splitlines():
        event = json.loads(line)
        if event.get("op") == "collect":
            requests[event["args"]["student"]] = event["args"]["ranking"]
    market = state.read().state["market"]
    matches = market["matches"]
    institution_matches = market["institution_matches"]
    priority_rank = {
        institution: {student: rank for rank, student in enumerate(order)}
        for institution, order in PRIORITIES.items()
    }
    blocks = []
    for student, ranking in requests.items():
        assigned = matches.get(student)
        for institution in ranking[: ranking.index(assigned)]:
            incumbents = institution_matches[institution]
            if len(incumbents) < CAPACITIES[institution] or any(
                priority_rank[institution][student]
                < priority_rank[institution][incumbent]
                for incumbent in incumbents
            ):
                blocks.append((student, institution))
    return blocks


def run_congested_market(
    log_path: str | Path = "matching-market-congested.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, list[tuple[str, str]]]:
    state = SharedState(
        "congested-program-match",
        FileStateStore(log_path),
        market=SharedDeferredAcceptance(CAPACITIES, PRIORITIES),
    )
    (
        preference_survey(state)
        .by(applicants())
        .by(Model(model_name))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    state.close()
    return state, blocking_pairs(state, log_path)


if __name__ == "__main__":
    shared_state, blocks = run_congested_market()
    print(shared_state.render_markdown())
    print(f"\nBlocking pairs: {blocks}")
