"""Choose a team with space for your role: python -m examples.team_formation."""

import json
from collections import Counter
from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionCompute,
    QuestionFreeText,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.team_formation import (
    DEFAULT_TEAMS,
    DEFAULT_ROLES,
    build_machine,
)


def build_survey(*, state_id=None, teams=DEFAULT_TEAMS, role_seats=None):
    spec = build_machine(teams, role_seats)
    states = SharedStateMap(SharedState(teams=spec), state_id=state_id)
    teams = states.by(current.agent.study_id).teams
    enrollment = QuestionCompute(
        question_name="team_enrollment",
        question_text="{{ 'open' if not shared_state.teams.complete or shared_state.teams.team else 'closed' }}",
    )
    role = QuestionMultipleChoice(
        question_name="role",
        question_text="Which role would you fill?",
        question_options=list(spec.constants["role_seats"]),
    )
    available = QuestionCompute(
        question_name="team_availability",
        question_text="{{ 'open' if shared_state.teams.options and shared_state.teams.role == role.answer else 'closed' }}",
    )
    team = QuestionMultipleChoice(
        question_name="team",
        question_text="Which eligible team would you like to join?",
        question_options="{{ shared_state.teams.options }}",
    )
    joined = QuestionCompute(
        question_name="joined_team",
        question_text="{{ shared_state.teams.team or 'unassigned' }}",
    )
    introduction = QuestionFreeText(
        question_name="introduction",
        question_text="Introduce yourself to team {{ joined_team.answer }}.",
    )
    survey = Survey(
        [
            teams.read(),
            enrollment,
            role,
            teams.register(respondent_id=current.agent.respondent_id, role=role.answer),
            teams.read(),
            available,
            team,
            teams.join(respondent_id=current.agent.respondent_id, team=team.answer),
            teams.read(),
            joined,
            introduction,
        ]
    )
    survey.add_stop_rule(enrollment, "{{ team_enrollment.answer }} != 'open'")
    survey.add_stop_rule(available, "{{ team_availability.answer }} != 'open'")
    survey.add_stop_rule(joined, "{{ joined_team.answer }} == 'unassigned'")
    return survey, states, InterviewSchedule.grouped_round_robin("study_id", "turn")


def demo_answer(self, question, scenario):
    if question.question_name == "role":
        return self.traits["role"]
    if question.question_name == "team":
        return question.question_options[0]
    return "Happy to join."


def demo_agents():
    agents = AgentList()
    for i, role in enumerate(["Designer"] * 3 + ["Builder"] * 5):
        agent = Agent(
            traits={
                "respondent_id": f"R{i}",
                "study_id": "study",
                "turn": i,
                "role": role,
            }
        )
        agent.add_direct_question_answering_method(demo_answer)
        agents.append(agent)
    return agents


def run_demo():
    from edsl.runner import Runner

    survey, _, schedule = build_survey()
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(demo_agents()).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    counts = {team: Counter() for team in DEFAULT_TEAMS}
    for row in results:
        if row.answer.get("introduction") is not None:
            counts[row.answer["joined_team"]][row.answer["role"]] += 1
        else:
            assert row.answer.get("team") is None
    assert all(dict(count) == DEFAULT_ROLES for count in counts.values())
    return {
        "teams": {team: dict(count) for team, count in counts.items()},
        "not_assigned": len(results) - sum(sum(c.values()) for c in counts.values()),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
