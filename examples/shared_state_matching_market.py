"""Student-proposing deferred acceptance with LLM-generated preferences."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionRank, Survey
from edsl.sharedstate import FileStateStore, SharedDeferredAcceptance, SharedState


PROGRAMS = {
    "Northstar": "Quantitative public policy; urban campus; intense mathematical core.",
    "Lakeside": "Environmental policy; small collaborative cohort; fieldwork emphasis.",
    "CivicLab": "Technology and governance; project-based curriculum; strong internships.",
}
CAPACITIES = {"Northstar": 2, "Lakeside": 2, "CivicLab": 2}
PRIORITIES = {
    "Northstar": ["Amina", "Diego", "Farah", "Ben", "Chloe", "Evan"],
    "Lakeside": ["Chloe", "Evan", "Ben", "Farah", "Amina", "Diego"],
    "CivicLab": ["Farah", "Ben", "Diego", "Amina", "Evan", "Chloe"],
}


def students() -> AgentList:
    specs = [
        ("Amina", "econometrics and housing policy", "rigorous quantitative training"),
        (
            "Ben",
            "civic technology and product design",
            "hands-on projects and internships",
        ),
        (
            "Chloe",
            "climate adaptation and conservation",
            "fieldwork and a close cohort",
        ),
        ("Diego", "data science and transportation", "technical depth and city access"),
        (
            "Evan",
            "environmental justice and community organizing",
            "collaboration and applied work",
        ),
        (
            "Farah",
            "AI governance and public institutions",
            "technology-policy integration",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={"interests": interests, "priority": priority},
            )
            for name, interests, priority in specs
        ]
    )


def preference_survey(state: SharedState) -> Survey:
    descriptions = "\n".join(
        f"{program}: {description}" for program, description in PROGRAMS.items()
    )
    ranking = QuestionRank(
        question_name="program_ranking",
        question_text=(
            "You are {{ agent.name }}. Your interests are {{ agent.interests }}, and "
            "you especially value {{ agent.priority }}. Rank every program from your "
            f"most to least preferred.\n\nPrograms:\n{descriptions}\n\n"
            "These preferences are private. Do not try to predict other applicants."
        ),
        question_options=list(PROGRAMS),
    )
    return Survey([ranking, state.market.collect(ranking, student="{{ agent.name }}")])


def run_matching_market(
    log_path: str | Path = "matching-market.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "graduate-program-match",
        FileStateStore(log_path),
        market=SharedDeferredAcceptance(CAPACITIES, PRIORITIES),
    )
    (
        preference_survey(state)
        .by(students())
        .by(Model(model_name))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    state.close()
    return state


if __name__ == "__main__":
    print(run_matching_market().render_markdown())
