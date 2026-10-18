"""Invigilator that runs a multi-agent group discussion inside one question task.

Mirrors ``InvigilatorInterview``: a bounded sequential loop of model calls that
accumulates a shared transcript, returning the whole transcript as the answer.
Here each turn is a different participant (persona + goal) rather than a fixed
interviewer/respondent pair.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List, TYPE_CHECKING

from ..base.data_transfer_models import EDSLResultObjectInput
from ..questions.exceptions import QuestionAnswerValidationError
from .invigilators import InvigilatorBase

if TYPE_CHECKING:
    from ..base.data_transfer_models import AgentResponseDict, ModelResponse
    from ..prompts import Prompt


@dataclass
class DiscussionTurnTrace:
    speaker: str
    round: int
    user_prompt: str
    system_prompt: str
    generated_text: str
    model_response: dict
    model_outputs: "ModelResponse"


class InvigilatorGroupDiscussion(InvigilatorBase):
    """Runs a bounded, round-robin group discussion as a single question task."""

    def get_prompts(self) -> Dict[str, "Prompt"]:
        from ..prompts import Prompt

        return {
            "user_prompt": Prompt(
                "Multi-agent group discussion managed internally by "
                "InvigilatorGroupDiscussion."
            ),
            "system_prompt": Prompt(
                "Each participant turn is executed as a separate model call."
            ),
        }

    def _replacement_dict(self) -> dict[str, Any]:
        return (
            self.scenario
            | self.prompt_constructor.prior_answers_dict()
            | {"agent": self.agent.traits}
        )

    def _rendered_question(self):
        if "{{" in (self.question.question_text or ""):
            return self.question.render(self._replacement_dict())
        return self.question

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("content", [])
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        ).strip()

    def _format_transcript(self, transcript: List[dict[str, Any]]) -> str:
        if not transcript:
            return "(No one has spoken yet.)"
        lines = []
        for message in transcript:
            speaker = message.get("speaker", "unknown")
            rnd = message.get("round", "")
            text = self._message_text(message)
            lines.append(f"[Round {rnd}] {speaker}: {text}")
        return "\n".join(lines)

    def _participant_order(
        self, participants: List[dict], round_index: int
    ) -> List[dict]:
        if getattr(self.question, "turn_order", "fixed") == "random":
            order = list(participants)
            random.Random((self.iteration or 0) * 1000 + round_index).shuffle(order)
            return order
        return participants

    def _build_system_prompt(self, participant: dict) -> str:
        pieces = [
            f"You are {participant['name']}, one participant in a group discussion.",
            "Speak only as yourself, stay in character, and do not narrate others.",
        ]
        if participant.get("persona"):
            pieces.append(f"About you: {participant['persona']}")
        if participant.get("goal"):
            pieces.append(f"Your goal: {participant['goal']}")
        return "\n\n".join(pieces)

    def _build_user_prompt(
        self,
        *,
        rendered_question,
        participant: dict,
        transcript: List[dict[str, Any]],
        round_index: int,
    ) -> str:
        names = ", ".join(p["name"] for p in rendered_question.participants)
        return (
            f"Premise:\n{rendered_question.question_text}\n\n"
            f"Participants: {names}\n\n"
            f"Transcript so far:\n{self._format_transcript(transcript)}\n\n"
            f"{rendered_question.turn_instruction}\n\n"
            f"It is round {round_index + 1}. You are {participant['name']}. "
            f"Give only your own next contribution as plain text."
        )

    async def _call_model(
        self, *, user_prompt: str, system_prompt: str
    ) -> tuple[str, "AgentResponseDict"]:
        model = copy.copy(self.model)
        if self.key_lookup:
            model.set_key_lookup(self.key_lookup)
        response = await model.async_get_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            cache=self.cache,
            iteration=self.iteration,
            invigilator=self,
            question_type="free_text",
        )
        text = response.edsl_dict.answer or ""
        return str(text).strip(), response

    @staticmethod
    def _trace_to_dict(trace: DiscussionTurnTrace) -> dict[str, Any]:
        return {
            "speaker": trace.speaker,
            "round": trace.round,
            "user_prompt": trace.user_prompt,
            "system_prompt": trace.system_prompt,
            "generated_text": trace.generated_text,
            "cache_used": trace.model_outputs.cache_used,
            "cache_key": trace.model_outputs.cache_key,
            "input_tokens": trace.model_outputs.input_tokens,
            "output_tokens": trace.model_outputs.output_tokens,
            "thinking_tokens": trace.model_outputs.thinking_tokens,
            "total_cost": trace.model_outputs.total_cost,
        }

    @staticmethod
    def _sum_numeric(values: List[Any]) -> Any:
        nums = [v for v in values if isinstance(v, (int, float))]
        return sum(nums) if nums else None

    async def async_answer_question(self) -> EDSLResultObjectInput:
        rendered_question = self._rendered_question()
        participants = rendered_question.participants
        transcript: List[dict[str, Any]] = []
        traces: List[DiscussionTurnTrace] = []
        exception_occurred = None
        validated = False

        try:
            for round_index in range(rendered_question.max_rounds):
                for participant in self._participant_order(participants, round_index):
                    system_prompt = self._build_system_prompt(participant)
                    user_prompt = self._build_user_prompt(
                        rendered_question=rendered_question,
                        participant=participant,
                        transcript=transcript,
                        round_index=round_index,
                    )
                    text, response = await self._call_model(
                        user_prompt=user_prompt, system_prompt=system_prompt
                    )
                    traces.append(
                        DiscussionTurnTrace(
                            speaker=participant["name"],
                            round=round_index + 1,
                            user_prompt=user_prompt,
                            system_prompt=system_prompt,
                            generated_text=text,
                            model_response=response.model_outputs.response,
                            model_outputs=response.model_outputs,
                        )
                    )
                    transcript.append(
                        {
                            "speaker": participant["name"],
                            "round": round_index + 1,
                            "content": [{"type": "text", "text": text}],
                        }
                    )

            generated_tokens = json.dumps(
                {
                    "transcript": transcript,
                    "turns": [self._trace_to_dict(t) for t in traces],
                }
            )
            validated_answer = rendered_question._validate_answer(
                {"answer": transcript, "generated_tokens": generated_tokens}
            )
            answer = validated_answer["answer"]
            comment = validated_answer.get("comment", "") or ""
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            comment = "The discussion transcript was not valid."
            exception_occurred = e
            generated_tokens = json.dumps({"transcript": transcript})
        except Exception as e:
            answer = None
            comment = "The discussion could not be completed."
            exception_occurred = e
            generated_tokens = json.dumps({"transcript": transcript})

        self.generated_tokens = generated_tokens
        self.raw_model_response = [t.model_response for t in traces]

        data = {
            "answer": answer,
            "comment": comment,
            "generated_tokens": generated_tokens,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": [t.model_outputs.cached_response for t in traces],
            "raw_model_response": self.raw_model_response,
            "cache_used": any(t.model_outputs.cache_used for t in traces),
            "cache_key": [t.model_outputs.cache_key for t in traces],
            "validated": validated,
            "exception_occurred": exception_occurred,
            "input_tokens": self._sum_numeric(
                [t.model_outputs.input_tokens for t in traces]
            ),
            "output_tokens": self._sum_numeric(
                [t.model_outputs.output_tokens for t in traces]
            ),
            "thinking_tokens": self._sum_numeric(
                [t.model_outputs.thinking_tokens for t in traces]
            ),
            "input_price_per_million_tokens": (
                traces[0].model_outputs.input_price_per_million_tokens
                if traces
                else None
            ),
            "output_price_per_million_tokens": (
                traces[0].model_outputs.output_price_per_million_tokens
                if traces
                else None
            ),
            "total_cost": self._sum_numeric(
                [t.model_outputs.total_cost for t in traces]
            ),
        }
        return EDSLResultObjectInput(**data)
