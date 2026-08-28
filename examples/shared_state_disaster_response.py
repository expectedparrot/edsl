"""Two-wave disaster response with atomic, capability-constrained resources."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionMultipleChoice, Survey
from edsl.sharedstate import FileStateStore, SharedResourceBoard, SharedState


INCIDENTS = [
    {
        "id": "I1",
        "round": 1,
        "severity": 5,
        "capability": "fire",
        "description": "warehouse fire",
    },
    {
        "id": "I2",
        "round": 1,
        "severity": 4,
        "capability": "medical",
        "description": "multi-vehicle bus crash",
    },
    {
        "id": "I3",
        "round": 1,
        "severity": 3,
        "capability": "utility",
        "description": "downed distribution line",
    },
    {
        "id": "I4",
        "round": 2,
        "severity": 5,
        "capability": "utility",
        "description": "hospital backup-generator failure",
    },
    {
        "id": "I5",
        "round": 2,
        "severity": 4,
        "capability": "security",
        "description": "urgent neighborhood evacuation",
    },
    {
        "id": "I6",
        "round": 2,
        "severity": 3,
        "capability": "fire",
        "description": "brush fire near homes",
    },
]
RESOURCES = {
    "Engine-7": "fire",
    "Ambulance-3": "medical",
    "Grid-Crew-2": "utility",
    "Patrol-5": "security",
}


def responders() -> AgentList:
    specs = [
        ("Chief Rivera", "fire incident commander", "Engine-7", "fire"),
        ("Dr. Chen", "EMS medical director", "Ambulance-3", "medical"),
        ("Sam Okafor", "utility dispatcher", "Grid-Crew-2", "utility"),
        ("Captain Lewis", "police watch commander", "Patrol-5", "security"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "role": role,
                    "resource": resource,
                    "capability": capability,
                },
            )
            for name, role, resource, capability in specs
        ]
    )


def wave_survey(state: SharedState, wave: int) -> Survey:
    wave_incidents = [item for item in INCIDENTS if item["round"] == wave]
    incident_text = "\n".join(
        f"{item['id']}: severity {item['severity']}, requires {item['capability']} — {item['description']}"
        for item in wave_incidents
    )
    incident = QuestionMultipleChoice(
        question_name=f"wave_{wave}_incident",
        question_text=(
            f"Disaster-response wave {wave}. You are {{ agent.name }}, the "
            "{{ agent.role }}, controlling {{ agent.resource }} with capability "
            "{{ agent.capability }}.\n\nNew incidents:\n"
            f"{incident_text}\n\nCurrent shared resource board:\n"
            "{{ shared_state.board }}\n\nSelect the highest-severity unassigned new "
            "incident your available resource can serve, or none."
        ),
        question_options=[item["id"] for item in wave_incidents] + ["none"],
    )
    resource = QuestionMultipleChoice(
        question_name=f"wave_{wave}_resource",
        question_text=(
            "You selected {{ "
            f"wave_{wave}_incident.answer"
            " }}. Select your resource {{ agent.resource }} if deploying it; otherwise "
            "select none. Never select another agency's resource."
        ),
        question_options=list(RESOURCES) + ["none"],
    )
    return Survey(
        [
            incident,
            resource,
            state.board.allocate(
                incident,
                resource,
                responder="{{ agent.name }}",
                round_number=wave,
            ),
        ]
    )


def run_disaster_response(
    log_path: str | Path = "disaster-response.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "coastal-storm-response",
        FileStateStore(log_path),
        board=SharedResourceBoard(INCIDENTS, RESOURCES),
    )
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    for wave in (1, 2):
        wave_survey(state, wave).by(responders()).by(model).run(**options)
    state.close()
    return state


if __name__ == "__main__":
    print(run_disaster_response().render_markdown())
