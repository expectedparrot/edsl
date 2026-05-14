"""Interview-specific invigilator that runs a turn-based interviewer/respondent loop."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, List, TYPE_CHECKING

from ..base.data_transfer_models import EDSLResultObjectInput
from ..questions.exceptions import QuestionAnswerValidationError
from .invigilators import InvigilatorBase

if TYPE_CHECKING:
    from ..base.data_transfer_models import AgentResponseDict, ModelResponse
    from ..prompts import Prompt


@dataclass
class InterviewTurnTrace:
    role: str
    user_prompt: str
    system_prompt: str
    generated_text: str
    model_response: dict
    model_outputs: "ModelResponse"


class InvigilatorInterview(InvigilatorBase):
    """Runs a bounded, sequential interview conversation inside one question task."""

    interviewer_system_prompt = (
        "You are an expert qualitative interviewer. "
        "Review the interview goal, guide, and transcript so far, then decide whether "
        "the interview is complete or provide the single best next interviewer utterance."
    )

    def get_prompts(self) -> Dict[str, "Prompt"]:
        from ..prompts import Prompt

        return {
            "user_prompt": Prompt(
                "Turn-based interview simulation managed internally by InvigilatorInterview."
            ),
            "system_prompt": Prompt(
                "The interviewer and respondent are executed as separate model calls."
            ),
        }

    def _replacement_dict(self) -> dict[str, Any]:
        return self.scenario | self.prompt_constructor.prior_answers_dict() | {
            "agent": self.agent.traits
        }

    def _rendered_question(self):
        replacement_dict = self._replacement_dict()
        if getattr(self.question, "parameters", None):
            return self.question.render(replacement_dict)
        if "{{" in self.question.question_text or "{{" in self.question.interview_guide:
            return self.question.render(replacement_dict)
        return self.question

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("content", [])
        if not content:
            return ""
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        ).strip()

    def _format_transcript(self, transcript: List[dict[str, Any]]) -> str:
        if not transcript:
            return "(No conversation yet.)"
        lines = []
        for message in transcript:
            role = message.get("role", "unknown").capitalize()
            text = self._message_text(message)
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _combine_interviewer_utterance(acknowledgment: str, question: str) -> str:
        acknowledgment = acknowledgment.strip()
        question = question.strip()
        if acknowledgment and question:
            return f"{acknowledgment}\n\n{question}"
        return acknowledgment or question

    @staticmethod
    def _parse_interviewer_decision(text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(stripped[start : end + 1])
                except json.JSONDecodeError:
                    parsed = None
                else:
                    return {
                        "done": bool(parsed.get("done", False)),
                        "acknowledgment": str(parsed.get("acknowledgment", "") or "").strip(),
                        "question": str(parsed.get("question", "") or "").strip(),
                    }

            lowered = stripped.lower()
            if lowered in {"done", "stop", "complete"}:
                return {"done": True, "acknowledgment": "", "question": ""}
            return {"done": False, "acknowledgment": "", "question": stripped}

        if not isinstance(parsed, dict):
            return {"done": False, "acknowledgment": "", "question": str(parsed).strip()}

        return {
            "done": bool(parsed.get("done", False)),
            "acknowledgment": str(parsed.get("acknowledgment", "") or "").strip(),
            "question": str(parsed.get("question", "") or "").strip(),
        }

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

    def _build_interviewer_user_prompt(
        self, *, rendered_question, transcript: List[dict[str, Any]], turn_index: int
    ) -> str:
        return (
            f"Interview goal:\n{rendered_question.question_text}\n\n"
            f"Interview guide:\n{rendered_question.interview_guide}\n\n"
            f"Transcript so far:\n{self._format_transcript(transcript)}\n\n"
            f"You are deciding interviewer turn {turn_index + 1}.\n"
            "Return a JSON object with exactly these keys:\n"
            '- "done": boolean\n'
            '- "acknowledgment": string\n'
            '- "question": string\n\n'
            "If the interview has covered the guide sufficiently, set done to true and "
            'leave question empty. Otherwise set done to false and provide one natural next '
            "interviewer utterance. Keep acknowledgment brief and professional."
        )

    def _build_respondent_system_prompt(self) -> str:
        agent_instructions = self.prompt_constructor.agent_instructions_prompt.text
        agent_persona = self.prompt_constructor.agent_persona_prompt.text
        pieces = [
            "You are the respondent in a qualitative interview.",
            "Answer naturally and stay in character.",
        ]
        if agent_instructions:
            pieces.append(agent_instructions)
        if agent_persona:
            pieces.append(agent_persona)
        return "\n\n".join(pieces)

    def _build_respondent_user_prompt(
        self,
        *,
        rendered_question,
        transcript: List[dict[str, Any]],
        interviewer_utterance: str,
    ) -> str:
        memory_prompt = self.prompt_constructor.prior_question_memory_prompt.text
        pieces = [
            f"Interview goal:\n{rendered_question.question_text}",
            f"Interview guide:\n{rendered_question.interview_guide}",
        ]
        if memory_prompt:
            pieces.append(f"Prior survey context:\n{memory_prompt}")
        pieces.extend(
            [
                f"Transcript so far:\n{self._format_transcript(transcript)}",
                f"Latest interviewer utterance:\n{interviewer_utterance}",
                "Respond as the interview subject only. Output only the respondent's reply text.",
            ]
        )
        return "\n\n".join(pieces)

    @staticmethod
    def _trace_to_dict(trace: InterviewTurnTrace) -> dict[str, Any]:
        return {
            "role": trace.role,
            "user_prompt": trace.user_prompt,
            "system_prompt": trace.system_prompt,
            "generated_text": trace.generated_text,
            "model_response": trace.model_response,
            "cache_used": trace.model_outputs.cache_used,
            "cache_key": trace.model_outputs.cache_key,
            "input_tokens": trace.model_outputs.input_tokens,
            "output_tokens": trace.model_outputs.output_tokens,
            "thinking_tokens": trace.model_outputs.thinking_tokens,
            "total_cost": trace.model_outputs.total_cost,
        }

    @staticmethod
    def _sum_numeric(values: List[Any]) -> Any:
        numeric_values = [value for value in values if isinstance(value, (int, float))]
        return sum(numeric_values) if numeric_values else None

    async def async_answer_question(self) -> EDSLResultObjectInput:
        rendered_question = self._rendered_question()
        transcript: List[dict[str, Any]] = []
        traces: List[InterviewTurnTrace] = []
        exception_occurred = None
        validated = False

        try:
            for turn_index in range(rendered_question.max_turns):
                interviewer_user_prompt = self._build_interviewer_user_prompt(
                    rendered_question=rendered_question,
                    transcript=transcript,
                    turn_index=turn_index,
                )
                interviewer_text, interviewer_response = await self._call_model(
                    user_prompt=interviewer_user_prompt,
                    system_prompt=self.interviewer_system_prompt,
                )
                traces.append(
                    InterviewTurnTrace(
                        role="interviewer",
                        user_prompt=interviewer_user_prompt,
                        system_prompt=self.interviewer_system_prompt,
                        generated_text=interviewer_text,
                        model_response=interviewer_response.model_outputs.response,
                        model_outputs=interviewer_response.model_outputs,
                    )
                )

                decision = self._parse_interviewer_decision(interviewer_text)
                if decision["done"]:
                    break

                interviewer_utterance = self._combine_interviewer_utterance(
                    decision["acknowledgment"], decision["question"]
                ).strip()
                if not interviewer_utterance:
                    break

                transcript.append(
                    {
                        "role": "interviewer",
                        "content": [{"type": "text", "text": interviewer_utterance}],
                    }
                )

                respondent_system_prompt = self._build_respondent_system_prompt()
                respondent_user_prompt = self._build_respondent_user_prompt(
                    rendered_question=rendered_question,
                    transcript=transcript,
                    interviewer_utterance=interviewer_utterance,
                )
                respondent_text, respondent_response = await self._call_model(
                    user_prompt=respondent_user_prompt,
                    system_prompt=respondent_system_prompt,
                )
                traces.append(
                    InterviewTurnTrace(
                        role="respondent",
                        user_prompt=respondent_user_prompt,
                        system_prompt=respondent_system_prompt,
                        generated_text=respondent_text,
                        model_response=respondent_response.model_outputs.response,
                        model_outputs=respondent_response.model_outputs,
                    )
                )
                transcript.append(
                    {
                        "role": "respondent",
                        "content": [{"type": "text", "text": respondent_text}],
                    }
                )

            trace_payload = {
                "transcript": transcript,
                "turns": [self._trace_to_dict(trace) for trace in traces],
            }
            generated_tokens = json.dumps(trace_payload)
            validated_answer = rendered_question._validate_answer(
                {"answer": transcript, "generated_tokens": generated_tokens}
            )
            answer = validated_answer["answer"]
            comment = validated_answer.get("comment", "") or ""
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            comment = "The interview transcript was not valid."
            exception_occurred = e
            generated_tokens = json.dumps(
                {
                    "transcript": transcript,
                    "turns": [self._trace_to_dict(trace) for trace in traces],
                }
            )
        except Exception as e:
            answer = None
            comment = "The interview could not be completed."
            exception_occurred = e
            generated_tokens = json.dumps(
                {
                    "transcript": transcript,
                    "turns": [self._trace_to_dict(trace) for trace in traces],
                }
            )

        self.generated_tokens = generated_tokens
        self.raw_model_response = [trace.model_response for trace in traces]
        cache_keys = [trace.model_outputs.cache_key for trace in traces]
        cached_responses = [trace.model_outputs.cached_response for trace in traces]
        cache_used = any(trace.model_outputs.cache_used for trace in traces)

        data = {
            "answer": answer,
            "comment": comment,
            "generated_tokens": generated_tokens,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": cached_responses,
            "raw_model_response": self.raw_model_response,
            "cache_used": cache_used,
            "cache_key": cache_keys,
            "validated": validated,
            "exception_occurred": exception_occurred,
            "input_tokens": self._sum_numeric(
                [trace.model_outputs.input_tokens for trace in traces]
            ),
            "output_tokens": self._sum_numeric(
                [trace.model_outputs.output_tokens for trace in traces]
            ),
            "thinking_tokens": self._sum_numeric(
                [trace.model_outputs.thinking_tokens for trace in traces]
            ),
            "input_price_per_million_tokens": None,
            "output_price_per_million_tokens": None,
            "total_cost": self._sum_numeric(
                [trace.model_outputs.total_cost for trace in traces]
            ),
        }
        return EDSLResultObjectInput(**data)
