"""Local shared-state activity poll with heterogeneous participant preferences."""

from __future__ import annotations

from collections import Counter
import random

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    current,
    field,
    input_,
    put,
    reduce_,
    state_field,
)


ACTIVITIES = ("bike ride", "sailing", "hike", "beach day")
TRAITS_TEMPLATE = """You are a member of a group choosing a weekend activity.
Your preferred activity is {{ preferred_activity }}.
Your preference strength is {{ preference_strength }} on a 0-to-1 scale:
0 means you have no attachment to it; 1 means you feel extremely strongly.
Your conformity is {{ conformity }} on a 0-to-1 scale: 0 means you ignore what
other people chose; 1 means you strongly prefer joining the emerging consensus.
Vote as this person would, trading off personal preference against the votes you
can currently see. When there is no clear group preference, favor your own.
"""


def activity_poll() -> Machine:
    return Machine(
        name="ActivityPoll",
        constants={"activities": ACTIVITIES},
        fields={"votes": state_field(T.map(T.text(), T.choice(ACTIVITIES)), {})},
        commands={
            "vote": Command(
                inputs={
                    "voter": T.text(),
                    "activity": T.choice(ACTIVITIES),
                },
                effects=(put("votes", input_("voter"), input_("activity")),),
            )
        },
        view={
            "votes": field("votes"),
            "counts": reduce_("count_by", field("votes").values()),
        },
    )


def participants(n: int = 16, seed: int = 731) -> AgentList:
    """Create reproducible personas with clear but heterogeneous preferences."""

    rng = random.Random(seed)
    preferences = [ACTIVITIES[index % len(ACTIVITIES)] for index in range(n)]
    rng.shuffle(preferences)
    agents = []
    for index, preferred in enumerate(preferences):
        strength = rng.uniform(0.6, 0.9)
        conformity = rng.uniform(0.55, 0.9)
        agent = Agent(
            name=f"participant-{index + 1:03d}",
            traits={
                "family_id": "weekend-group",
                "turn": index,
                "preferred_activity": preferred,
                "preference_strength": round(strength, 2),
                "conformity": round(conformity, 2),
            },
        )
        agents.append(agent)
    return AgentList(agents, traits_presentation_template=TRAITS_TEMPLATE)


def build_survey(state_id: str = "weekend-activity-poll") -> Survey:
    spaces = SharedStateMap(
        SharedState(poll=activity_poll()),
        state_id=state_id,
    )
    family = spaces.by(current.agent.family_id)
    activity = QuestionMultipleChoice(
        question_name="activity",
        question_text=(
            "Current votes are {{ shared_state.poll.votes }}. "
            "Which activity should the group choose?"
        ),
        question_options=list(ACTIVITIES),
    )
    return Survey(
        [
            family.poll.read(),
            activity,
            family.poll.vote(
                voter=current.agent.name,
                activity=activity.answer,
            ),
        ]
    )


def run(
    n: int = 16,
    seed: int = 731,
    model_name: str = "gemini-2.5-flash",
    max_concurrency: int = 5,
    state_id: str = "weekend-activity-poll",
):
    people = participants(n=n, seed=seed)
    schedule = InterviewSchedule.grouped_round_robin("family_id", "turn")
    results = (
        build_survey(state_id=state_id)
        .by(people)
        .by(Model(model_name, service_name="google"))
        .run(
            cache=False,
            disable_remote_cache=True,
            disable_remote_inference=True,
            max_concurrency=max_concurrency,
            interview_schedule=schedule,
            stop_on_exceptions=True,
        )
    )
    answers = results.select("answer.activity").to_list()
    return results, Counter(answers)


if __name__ == "__main__":
    poll_results, counts = run()
    print(dict(sorted(counts.items())))
    events = poll_results.shared_state["bindings"][0]["events"]
    final_write = next(event for event in reversed(events) if event["kind"] == "write")
    print(final_write["state"]["poll"]["votes"])
