"""A question that simulates a multi-agent group discussion.

Several participants take turns in a shared conversation. Each turn is one model
call that sees the premise, that participant's persona and goal, and the full
transcript so far. The whole discussion runs inside a single question task (the
same "one task, internal loop" pattern as ``QuestionInterview``), so it fans out
across scenarios and models exactly like any other question.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class DiscussionTurn(BaseModel):
    """One contribution in a group discussion transcript."""

    speaker: str
    round: int = 1
    content: List[TextContent]


class GroupDiscussionResponse(BaseModel):
    """Validates a group-discussion response: a transcript of turns."""

    answer: List[DiscussionTurn]
    generated_tokens: Optional[str] = None

    @field_validator("answer", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return list(v) if hasattr(v, "__iter__") else []


class GroupDiscussionResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [
        (
            {
                "answer": [
                    {
                        "speaker": "alice",
                        "round": 1,
                        "text": "I think we should expand.",
                    },
                    {"speaker": "bob", "round": 1, "text": "I disagree — too risky."},
                ]
            },
            {},
        )
    ]
    invalid_examples = [
        ({"answer": None}, {}, "Answer code must not be missing."),
    ]

    def _preprocess(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize each turn to {speaker, round, content:[{type,text}]}."""
        answer = data.get("answer")
        if isinstance(answer, list):
            processed = []
            for item in answer:
                if isinstance(item, dict):
                    turn = {
                        "speaker": item.get("speaker", item.get("role", "unknown")),
                        "round": int(item.get("round", 1) or 1),
                    }
                    if isinstance(item.get("content"), list):
                        turn["content"] = item["content"]
                    else:
                        turn["content"] = [
                            {"type": "text", "text": item.get("text", "") or ""}
                        ]
                    processed.append(turn)
                else:
                    processed.append(item)
            data["answer"] = processed
        return data

    def fix(self, response: dict, verbose: bool = False) -> dict:
        answer = response.get("answer")
        if answer is None:
            answer = []
        elif isinstance(answer, dict):
            answer = [answer]
        elif not isinstance(answer, list):
            answer = []
        return {"answer": answer, "generated_tokens": response.get("generated_tokens")}


def _normalize_participants(participants: Any) -> List[Dict[str, Any]]:
    """Accept a list of dicts, or EDSL Agents/AgentList, as participants.

    Each participant becomes a plain dict: {name, persona, goal}. This keeps the
    question serializable without depending on the Agent class.
    """
    normalized: List[Dict[str, Any]] = []
    items = list(participants) if participants is not None else []
    for idx, p in enumerate(items):
        if isinstance(p, dict):
            name = str(p.get("name") or f"participant_{idx + 1}")
            persona = p.get("persona") or p.get("instruction") or ""
            goal = p.get("goal") or ""
            traits = p.get("traits")
            if not persona and isinstance(traits, dict):
                persona = "; ".join(f"{k}: {v}" for k, v in traits.items())
            normalized.append(
                {"name": name, "persona": str(persona), "goal": str(goal)}
            )
            continue
        # Duck-type an EDSL Agent (has .name / .traits).
        name = getattr(p, "name", None) or f"participant_{idx + 1}"
        traits = getattr(p, "traits", {}) or {}
        goal = traits.get("goal", "") if isinstance(traits, dict) else ""
        persona = (
            "; ".join(f"{k}: {v}" for k, v in traits.items())
            if isinstance(traits, dict)
            else str(traits)
        )
        instruction = getattr(p, "instruction", "") or ""
        if instruction:
            persona = f"{instruction}\n{persona}".strip()
        normalized.append(
            {"name": str(name), "persona": str(persona), "goal": str(goal)}
        )
    return normalized


DEFAULT_TURN_INSTRUCTION = (
    "Given everything said so far, give your next contribution to the discussion. "
    "Stay in character, pursue your goal, and keep it to one short paragraph."
)


class QuestionGroupDiscussion(QuestionBase):
    """Simulate a turn-based discussion among several participants.

    Examples:
        >>> q = QuestionGroupDiscussion.example()
        >>> q.question_type
        'group_discussion'
        >>> len(q.participants)
        3
        >>> q.max_rounds
        2
    """

    question_type = "group_discussion"
    _response_model = GroupDiscussionResponse
    response_validator_class = GroupDiscussionResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        participants: List[Union[Dict[str, Any], Any]],
        max_rounds: int = 3,
        turn_instruction: Optional[str] = None,
        turn_order: Literal["fixed", "random"] = "fixed",
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """Create a group-discussion question.

        Args:
            question_name: Identifier used in results and templates.
            question_text: The shared premise/topic. May contain ``{{ scenario }}``
                placeholders.
            participants: The discussants. Each is a dict ``{name, persona, goal}``
                (persona/goal optional) or an EDSL Agent.
            max_rounds: How many times each participant speaks.
            turn_instruction: What each participant is asked on their turn.
            turn_order: ``"fixed"`` round-robin or ``"random"`` per round.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.participants = _normalize_participants(participants)
        self.max_rounds = max_rounds
        self.turn_instruction = turn_instruction or DEFAULT_TURN_INSTRUCTION
        self.turn_order = turn_order
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def _invigilator_class(self):
        from ..invigilators.invigilator_group_discussion import (
            InvigilatorGroupDiscussion,
        )

        return InvigilatorGroupDiscussion

    @property
    def data(self) -> dict:
        base_data = super().data
        base_data["participants"] = self.participants
        base_data["max_rounds"] = self.max_rounds
        base_data["turn_instruction"] = self.turn_instruction
        base_data["turn_order"] = self.turn_order
        return base_data

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        transcript = []
        for r in range(1, self.max_rounds + 1):
            for p in self.participants:
                transcript.append(
                    {
                        "speaker": p["name"],
                        "round": r,
                        "content": [
                            {"type": "text", "text": f"({p['name']}, round {r})"}
                        ],
                    }
                )
        return {"answer": transcript, "generated_tokens": None}

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        return Template(
            """
        <div class="group-discussion-question">
            <h3>Premise:</h3>
            <p>{{ question_text }}</p>
            <h3>Participants:</h3>
            <ul>{% for p in participants %}<li>{{ p.name }}</li>{% endfor %}</ul>
            <textarea id="{{ question_name }}" name="{{ question_name }}" rows="20" cols="80"></textarea>
        </div>
        """
        ).render(
            question_name=self.question_name,
            question_text=self.question_text,
            participants=self.participants,
        )

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionGroupDiscussion":
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="community_meeting",
            question_text=(
                f"You are members of a small community deciding how to share a new "
                f"public resource.{addition}"
            ),
            participants=[
                {
                    "name": "founder",
                    "persona": "You run the town's only tech company.",
                    "goal": "Grow the company and keep talent local.",
                },
                {
                    "name": "craftsman",
                    "persona": "You are a master carpenter.",
                    "goal": "Protect the value of skilled manual work.",
                },
                {
                    "name": "landowner",
                    "persona": "You own the largest parcel of land.",
                    "goal": "Protect your land holdings.",
                },
            ],
            max_rounds=2,
            turn_order="fixed",
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
