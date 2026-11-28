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

        if getattr(self.model, "_inference_service_", None) == "persimmon":
            return {
                "user_prompt": Prompt(
                    "Persimmon conversation with simulated interviewer and respondent."
                ),
                "system_prompt": Prompt(
                    "Interviewer and respondent personas are configured as Persimmon participants."
                ),
            }

        return {
            "user_prompt": Prompt(
                "Turn-based interview simulation managed internally by InvigilatorInterview."
            ),
            "system_prompt": Prompt(
                "The interviewer and respondent are executed as separate model calls."
            ),
        }

    def _replacement_dict(self) -> dict[str, Any]:
        return (
            self.scenario
            | self.prompt_constructor.prior_answers_dict()
            | {"agent": self.agent.traits}
        )

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
                        "acknowledgment": str(
                            parsed.get("acknowledgment", "") or ""
                        ).strip(),
                        "question": str(parsed.get("question", "") or "").strip(),
                    }

            lowered = stripped.lower()
            if lowered in {"done", "stop", "complete"}:
                return {"done": True, "acknowledgment": "", "question": ""}
            return {"done": False, "acknowledgment": "", "question": stripped}

        if not isinstance(parsed, dict):
            return {
                "done": False,
                "acknowledgment": "",
                "question": str(parsed).strip(),
            }

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
            "leave question empty. Otherwise set done to false and provide one natural next "
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

    async def _async_answer_question_persimmon(self) -> EDSLResultObjectInput:
        """Run the interviewer and respondent as participants in Persimmon."""
        import httpx

        rendered_question = self._rendered_question()
        interviewer_name = "Interviewer"
        respondent_name = "Respondent"
        respondent_description = "\n\n".join(
            part
            for part in (
                self.prompt_constructor.agent_instructions_prompt.text,
                self.prompt_constructor.agent_persona_prompt.text,
            )
            if part
        )
        memory_prompt = self.prompt_constructor.prior_question_memory_prompt.text
        if memory_prompt:
            respondent_description = "\n\n".join(
                part
                for part in (
                    respondent_description,
                    f"Prior survey context:\n{memory_prompt}",
                )
                if part
            )
        interviewer_description = (
            "You are a skilled qualitative interviewer. Conduct a natural, "
            "neutral interview. Follow the goal and guide in the conversation "
            "setting, ask one focused open-ended question per turn, and do not "
            "answer for the respondent.\n\n"
            f"Interview goal: {rendered_question.question_text}\n\n"
            f"Interview guide: {rendered_question.interview_guide}"
        )
        setting_parts = [
            f"Qualitative interview.\n\nGoal: {rendered_question.question_text}"
            f"\n\nGuide: {rendered_question.interview_guide}"
        ]
        if memory_prompt:
            setting_parts.append(f"Prior survey context:\n{memory_prompt}")
        setting = "\n\n".join(setting_parts)
        headers = {
            "Authorization": f"Bearer {self.model.api_token}",
            "Content-Type": "application/json",
        }
        base_url = "https://api.persimmon.humansand.ai/v1"
        cache_parameters = self.model.parameters.copy()
        cache_user_prompt = json.dumps(
            {
                "question_name": rendered_question.question_name,
                "goal": rendered_question.question_text,
                "guide": rendered_question.interview_guide,
                "max_turns": rendered_question.max_turns,
                "interviewer": interviewer_description,
                "respondent": respondent_description,
                "prior_survey_context": memory_prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_system_prompt = setting
        cached_response = None
        cache_key = None
        if self.cache is not None:
            cached_response, cache_key = self.cache.fetch(
                model=str(self.model.model),
                parameters=cache_parameters,
                system_prompt=cache_system_prompt,
                user_prompt=cache_user_prompt,
                iteration=self.iteration,
                remote_fetch=False,
            )
            if cached_response:
                try:
                    cached_payload = json.loads(cached_response)
                except (TypeError, json.JSONDecodeError):
                    cached_payload = None
                if isinstance(cached_payload, dict) and cached_payload.get("validated"):
                    self.generated_tokens = cached_payload["generated_tokens"]
                    self.raw_model_response = cached_payload["raw_model_response"]
                    return EDSLResultObjectInput(
                        answer=cached_payload["answer"],
                        comment=cached_payload["comment"],
                        generated_tokens=cached_payload["generated_tokens"],
                        question_name=self.question.question_name,
                        prompts=self.get_prompts(),
                        cached_response=cached_response,
                        raw_model_response=cached_payload["raw_model_response"],
                        cache_used=True,
                        cache_key=cache_key,
                        validated=True,
                        exception_occurred=None,
                        input_tokens=cached_payload["input_tokens"],
                        output_tokens=cached_payload["output_tokens"],
                        thinking_tokens=None,
                        total_cost=None,
                    )
        transcript: List[dict[str, Any]] = []
        raw_responses: List[dict[str, Any]] = []
        input_tokens: List[int] = []
        output_tokens: List[int] = []
        exception_occurred = None
        validated = False

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    f"{base_url}/conversations",
                    headers=headers,
                    json={
                        "model": self.model.model,
                        "setting": setting,
                        "participants": [
                            {
                                "name": interviewer_name,
                                "description": interviewer_description[:32000],
                            },
                            {
                                "name": respondent_name,
                                "description": respondent_description[:32000],
                            },
                        ],
                    },
                )
                response.raise_for_status()
                conversation_id = response.json()["id"]
                history: List[dict[str, str]] = []
                turns = []
                tier = self.model.parameters.get("tier", "standard")
                max_tokens = self.model.parameters.get("max_tokens", 256)

                for _ in range(rendered_question.max_turns):
                    for speaker in (interviewer_name, respondent_name):
                        response = await client.post(
                            f"{base_url}/conversations/{conversation_id}/turns",
                            headers=headers,
                            json={
                                "turns": history,
                                "speaker": speaker,
                                "tier": tier,
                                "max_tokens": max_tokens,
                            },
                        )
                        response.raise_for_status()
                        turn = response.json()
                        raw_responses.append(turn)
                        usage = turn.get("usage", {})
                        if isinstance(usage.get("prompt_tokens"), int):
                            input_tokens.append(usage["prompt_tokens"])
                        if isinstance(usage.get("completion_tokens"), int):
                            output_tokens.append(usage["completion_tokens"])

                        text = turn.get("content")
                        if not isinstance(text, str) or not text.strip():
                            raise ValueError(
                                f"Persimmon returned no content for {speaker}."
                            )
                        text = text.strip()
                        history.append({"name": turn["name"], "content": text})
                        transcript.append(
                            {
                                "role": (
                                    "interviewer"
                                    if speaker == interviewer_name
                                    else "respondent"
                                ),
                                "content": [{"type": "text", "text": text}],
                            }
                        )
                        turns.append(
                            {
                                "role": speaker.lower(),
                                "generated_text": text,
                                "model_response": turn,
                            }
                        )

            generated_tokens = json.dumps(
                {
                    "conversation_id": conversation_id,
                    "transcript": transcript,
                    "turns": turns,
                }
            )
            validated_answer = rendered_question._validate_answer(
                {"answer": transcript, "generated_tokens": generated_tokens}
            )
            answer = validated_answer["answer"]
            comment = validated_answer.get("comment", "") or ""
            validated = True
        except Exception as e:
            exception_occurred = e
            answer = None
            comment = "The Persimmon interview could not be completed."
            generated_tokens = json.dumps(
                {
                    "transcript": transcript,
                    "turns": raw_responses,
                }
            )

        self.generated_tokens = generated_tokens
        self.raw_model_response = raw_responses
        if self.cache is not None and validated:
            cached_payload = {
                "answer": answer,
                "comment": comment,
                "generated_tokens": generated_tokens,
                "raw_model_response": raw_responses,
                "input_tokens": sum(input_tokens) if input_tokens else None,
                "output_tokens": sum(output_tokens) if output_tokens else None,
                "validated": True,
            }
            cache_key = self.cache.store(
                model=str(self.model.model),
                parameters=cache_parameters,
                system_prompt=cache_system_prompt,
                user_prompt=cache_user_prompt,
                response=cached_payload,
                iteration=self.iteration,
                service=self.model._inference_service_,
            )
        return EDSLResultObjectInput(
            answer=answer,
            comment=comment,
            generated_tokens=generated_tokens,
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
            cached_response=None,
            raw_model_response=raw_responses,
            cache_used=False,
            cache_key=cache_key,
            validated=validated,
            exception_occurred=exception_occurred,
            input_tokens=sum(input_tokens) if input_tokens else None,
            output_tokens=sum(output_tokens) if output_tokens else None,
            thinking_tokens=None,
            total_cost=None,
        )

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
        if getattr(self.model, "_inference_service_", None) == "persimmon":
            return await self._async_answer_question_persimmon()

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
                [trace.model_outputs.total_cost for trace in traces]
            ),
        }
        return EDSLResultObjectInput(**data)
