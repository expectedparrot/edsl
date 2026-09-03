"""EDSL model-backed callbacks for causal conversation experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from edsl import Agent, Model, QuestionFreeText, QuestionMultipleChoice, QuestionYesNo, Survey
import re

from .runner import ConversationTurnRequest, MeasurementRequest


@dataclass(frozen=True)
class AdapterCall:
    kind: str
    instance_id: str | None
    role: str
    input: Mapping[str, Any]
    answers: Mapping[str, Any]
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "instance_id": self.instance_id, "role": self.role, "input": dict(self.input), "answers": dict(self.answers), "model": self.model}


class EDSLCausalAdapter:
    """Adapt ordinary EDSL agents, surveys, and models to causal runner callbacks."""

    def __init__(self, model: Model, *, coordinator_model: Model | None = None, measurement_model: Model | None = None, run_options: Mapping[str, Any] | None = None):
        self.model = model
        self.coordinator_model = coordinator_model or model
        self.measurement_model = measurement_model or model
        self.run_options = {"disable_remote_inference": True, "disable_remote_cache": True, "cache": False, "stop_on_exceptions": True, **dict(run_options or {})}
        self.calls: list[AdapterCall] = []

    @staticmethod
    def _model_name(model: Model) -> str:
        return str(getattr(model, "model", getattr(model, "model_name", type(model).__name__)))

    @staticmethod
    def _transcript_text(transcript: Sequence[Mapping[str, Any]]) -> str:
        return "\n".join(f"{item['role']}: {item['text']}" for item in transcript) or "(No one has spoken yet.)"

    def _run(self, survey: Survey, agent: Agent, model: Model, *, kind: str, instance_id: str | None, role: str, input_data: Mapping[str, Any]) -> Mapping[str, Any]:
        results = survey.by(agent).by(model).run(**self.run_options)
        answers = dict(results[0].answer)
        self.calls.append(AdapterCall(kind, instance_id, role, dict(input_data), answers, self._model_name(model)))
        return answers

    def speak(self, request: ConversationTurnRequest) -> str:
        public = "\n".join(str(value) for key, value in request.public_context.items() if key.endswith("_instruction")) or "No additional public treatment information."
        private = "\n".join(str(value) for value in request.private_context.values()) or "No additional private treatment information."
        prompt = f"""You are the {request.role} in this social interaction.

Scenario: {request.scenario}
Goal: {request.participant.traits['goal']}
Constraint: {request.participant.traits['constraint']}

Public information:
{public}

Private information known only to you:
{private}

Conversation so far:
{self._transcript_text(request.transcript)}

Turn instructions:
{request.turn_instruction or "No additional turn instructions."}

Provide only your next public utterance. Do not describe your reasoning or another participant's response."""
        if request.turn_contract and request.turn_contract.get("kind") == "numeric_offer_or_pass":
            contract = request.turn_contract
            currency = str(contract.get("currency", "$"))
            amounts = [float(value) for item in request.transcript for value in re.findall(rf"{re.escape(currency)}\s*([0-9]+(?:\.[0-9]+)?)", str(item["text"]))]
            standing = max(amounts, default=float(contract.get("opening", 0)))
            maximum = float((request.private_values or {})[contract["maximum_context"]])
            increment = float(contract["increment"])
            max_jump = float(contract.get("max_jump", increment))
            legal = []
            candidate = standing + increment
            while candidate <= maximum and candidate <= standing + max_jump:
                legal.append(f"{currency}{candidate:g}")
                candidate += increment
            choices = legal + [str(contract.get("pass_token", "pass"))]
            survey = Survey([QuestionMultipleChoice(question_name="utterance", question_text=prompt, question_options=choices)])
        else:
            survey = Survey([QuestionFreeText(question_name="utterance", question_text=prompt)])
        answers = self._run(survey, request.participant.to_agent(), self.model, kind="speaker", instance_id=request.instance_id, role=request.role, input_data={"prompt": prompt, "transcript_version": len(request.transcript)})
        return str(answers["utterance"]).strip()

    def judge(self, definition, transcript: Sequence[Mapping[str, Any]], question: str) -> bool:
        prompt = f"""You are a hidden conversation coordinator.
Scenario: {definition.scenario}
Conversation:
{self._transcript_text(transcript)}

Decision criterion: {question}
Should the conversation stop now?"""
        survey = Survey([QuestionYesNo(question_name="stop", question_text=prompt)])
        agent = Agent(name="conversation-coordinator", traits={"role": "conversation-coordinator"}, instruction="Judge conversation termination conservatively and consistently.")
        answers = self._run(survey, agent, self.coordinator_model, kind="semantic_stop", instance_id=transcript[0]["instance_id"] if transcript else None, role="conversation-coordinator", input_data={"prompt": prompt, "transcript_version": len(transcript)})
        return str(answers["stop"]).strip().lower() in {"yes", "true", "1"}

    def measure(self, request: MeasurementRequest) -> Any:
        survey = Survey.from_dict(dict(request.manifest.survey))
        transcript = self._transcript_text(request.transcript)
        agent = request.participant.to_agent()
        agent.instruction = f"{agent.instruction}\nThe completed interaction transcript is:\n{transcript}"
        answers = self._run(survey, agent, self.measurement_model, kind="measurement", instance_id=request.instance_id, role=request.participant.role, input_data={"survey": request.manifest.survey, "transcript_version": len(request.transcript)})
        if request.manifest.field not in answers:
            raise ValueError(f"measurement response has no field {request.manifest.field!r}")
        return self._coerce(answers[request.manifest.field], request.manifest.dtype, request.manifest.levels)

    @staticmethod
    def _coerce(value: Any, dtype: str, levels: Sequence[Any]) -> Any:
        if dtype == "binary":
            if value in levels:
                return levels.index(value)
            normalized = str(value).strip().lower()
            if normalized in {"yes", "true", "1"}:
                return 1
            if normalized in {"no", "false", "0"}:
                return 0
            raise ValueError(f"cannot coerce {value!r} to binary")
        if dtype == "continuous":
            return float(value)
        if dtype == "count":
            number = int(value)
            if number < 0:
                raise ValueError("count measurements cannot be negative")
            return number
        if dtype in {"ordinal", "nominal"}:
            if value not in levels:
                raise ValueError(f"measurement value {value!r} is not a declared level")
            return levels.index(value) if dtype == "ordinal" else value
        raise ValueError(f"unsupported measurement type {dtype!r}")

    def provenance(self) -> list[dict[str, Any]]:
        return [call.to_dict() for call in self.calls]
