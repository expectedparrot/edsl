"""A question that simulates a multi-agent group discussion / deliberation.

This is a *meeting-as-a-program*: a deliberation is an ordered, data-dependent
sequence of **stages**, and a vote is just one kind of stage that can appear
anywhere — to set the agenda, as a procedural motion mid-debate, to decide an
individual agenda item, or to ratify the whole package. Each decision stage
writes a **named** outcome to a shared ledger, so one conversation can produce
many decisions, and later stages can read earlier ones (path dependence).

Four axes are configured independently and run through one engine:

- **Actors**     — participants carry role, goal, ``vote_weight``, ``veto``,
                   ``can_vote`` and ``private_info`` (facts only they see).
- **Protocol**   — stages with their own participant subset, rounds and
                   turn order; anonymity; injected events; caucus side-channels.
- **Decision**   — a library of rules (plurality, majority, supermajority,
                   unanimous, weighted, ranked_choice, approval, quadratic,
                   authority) with veto, quorum and tie-break.
- **Orchestration** — the ``stages`` list, including an ``agenda`` stage whose
                   result dynamically expands into the stages that follow.

The whole thing still runs inside a single question task (the "one task,
internal loop" pattern of ``QuestionInterview``) and fans out across scenarios
and models like any other question. The answer stays a flat list of transcript
turns (each tagged with ``kind`` and ``stage``); the structured decisions ledger
and per-vote tallies are stored in ``generated_tokens``.

The simple constructor arguments (``max_rounds`` / ``decision_mode`` / ...) are
sugar: they compile into an equivalent ``stages`` list, so there is one code
path.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC

# Keep in sync with group_discussion_voting.VOTE_METHODS.
VOTE_METHODS = (
    "plurality",
    "majority",
    "supermajority",
    "unanimous",
    "weighted",
    "approval",
    "ranked_choice",
    "quadratic",
    "numeric",
    "authority",
)
STAGE_TYPES = (
    "discussion",
    "consensus",
    "vote",
    "authority",
    "moderator",
    "agenda",
    "motion",
    "deliberate",
    "negotiation",
)
DecisionMode = Literal["none", "moderator", "vote", "consensus"]


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class DiscussionTurn(BaseModel):
    """One contribution in a deliberation transcript.

    ``kind`` marks the phase (``discussion`` | ``vote`` | ``decision`` |
    ``event`` | ``caucus``) and ``stage`` names the stage it belongs to, so a
    reader (or the UI) can follow a multi-stage meeting.
    """

    speaker: str
    round: int = 1
    kind: Literal["discussion", "vote", "decision", "event", "caucus"] = "discussion"
    stage: Optional[str] = None
    # Names allowed to see this turn. ``None`` = public. Set on caucus turns so a
    # reader or UI can redact a side-conversation from non-members.
    private_to: Optional[List[str]] = None
    content: List[TextContent]


class GroupDiscussionResponse(BaseModel):
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
    invalid_examples = [({"answer": None}, {}, "Answer code must not be missing.")]

    def _preprocess(self, data: Dict[str, Any]) -> Dict[str, Any]:
        answer = data.get("answer")
        if isinstance(answer, list):
            processed = []
            for item in answer:
                if isinstance(item, dict):
                    kind = item.get("kind", "discussion")
                    if kind not in (
                        "discussion",
                        "vote",
                        "decision",
                        "event",
                        "caucus",
                    ):
                        kind = "discussion"
                    turn = {
                        "speaker": item.get("speaker", item.get("role", "unknown")),
                        "round": int(item.get("round", 1) or 1),
                        "kind": kind,
                        "stage": item.get("stage"),
                        "private_to": item.get("private_to"),
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


def _coerce_weight(value: Any) -> float:
    try:
        w = float(value)
        return w if w >= 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


def _normalize_participants(participants: Any) -> List[Dict[str, Any]]:
    """Each participant -> {name, persona, goal, role, vote_weight, veto,
    can_vote, private_info}. Accepts dicts or duck-typed EDSL Agents."""
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
                {
                    "name": name,
                    "persona": str(persona),
                    "goal": str(goal),
                    "role": str(p.get("role", "member")),
                    "vote_weight": _coerce_weight(p.get("vote_weight", 1.0)),
                    "veto": bool(p.get("veto", False)),
                    "can_vote": bool(p.get("can_vote", True)),
                    "private_info": str(p.get("private_info", "") or ""),
                }
            )
            continue
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
            {
                "name": str(name),
                "persona": str(persona),
                "goal": str(goal),
                "role": "member",
                "vote_weight": _coerce_weight(
                    traits.get("vote_weight", 1.0) if isinstance(traits, dict) else 1.0
                ),
                "veto": False,
                "can_vote": True,
                "private_info": "",
            }
        )
    return normalized


DEFAULT_MODERATOR = {
    "name": "moderator",
    "persona": "a neutral facilitator with no stake in the outcome",
}
DEFAULT_TURN_INSTRUCTION = (
    "Respond to what others have said so far, then give your own next "
    "contribution. Stay in character, pursue your goal, acknowledge points you "
    "agree or disagree with by name, and keep it to one short paragraph."
)


def _normalize_moderator(moderator: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not moderator:
        return dict(DEFAULT_MODERATOR)
    return {
        "name": str(moderator.get("name") or DEFAULT_MODERATOR["name"]),
        "persona": str(moderator.get("persona") or DEFAULT_MODERATOR["persona"]),
    }


def _normalize_stage(stage: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Fill a stage spec with defaults and validate its type/method."""
    stype = stage.get("type", "discussion")
    if stype not in STAGE_TYPES:
        raise ValueError(
            f"stage {idx}: type must be one of {STAGE_TYPES}, got {stype!r}"
        )
    method = stage.get("method", "plurality")
    if stype in ("vote", "agenda", "motion") and method not in VOTE_METHODS:
        raise ValueError(
            f"stage {idx}: method must be one of {VOTE_METHODS}, got {method!r}"
        )
    norm = {
        "type": stype,
        "name": str(stage.get("name") or f"stage_{idx + 1}"),
        "prompt": str(stage.get("prompt", "") or ""),
        "participants": stage.get("participants"),  # None = all
        "rounds": int(stage.get("rounds", 1) or 1),
        "turn_instruction": stage.get("turn_instruction"),
        "method": method,
        "options": (
            [str(o) for o in stage["options"]] if stage.get("options") else None
        ),
        "threshold": (
            float(stage["threshold"]) if stage.get("threshold") is not None else None
        ),
        "quorum": float(stage.get("quorum", 0) or 0),
        "decider": stage.get("decider"),
        "tie_breaker": stage.get("tie_breaker"),
        "anonymous": bool(stage.get("anonymous", False)),
        "outcome": stage.get("outcome", "choice"),
        "budget": stage.get("budget"),
        "event": stage.get("event"),
        "per_item": stage.get("per_item"),
        "top_k": stage.get("top_k"),
        "effect": stage.get("effect", "flow" if stype == "motion" else "substantive"),
        "early_stop": bool(stage.get("early_stop", False)),
        "private_to": stage.get("private_to"),
        # deliberate: declare deadlock after this many rounds with no position change
        "patience": int(stage.get("patience", 2) or 2),
        # negotiation: deal closes when the offer spread is within this fraction
        "tolerance": float(stage.get("tolerance", 0.05) or 0.05),
        # vote: "cast" (threshold vs ballots cast) or "electorate" (vs full
        # membership weight — abstentions/absences count against the bar).
        "basis": stage.get("basis", "cast"),
        # vote: independent/secret ballot — each voter decides from its own
        # persona + prior decisions only, NOT the running tally of other ballots.
        # Essential for large bodies (hundreds of members) to avoid an O(n^2)
        # transcript and to model a recorded vote rather than a live debate.
        "independent": bool(stage.get("independent", False)),
        # vote: max concurrent model calls for an independent ballot.
        "concurrency": int(stage.get("concurrency", 24) or 24),
    }
    return norm


class QuestionGroupDiscussion(QuestionBase):
    """Simulate a staged, multi-agent deliberation that produces real decisions.

    Examples:
        >>> q = QuestionGroupDiscussion.example()
        >>> q.question_type
        'group_discussion'
        >>> len(q.participants)
        3
        >>> [s['type'] for s in q.resolved_stages()]
        ['discussion', 'moderator']

        >>> v = QuestionGroupDiscussion.example_vote()
        >>> [s['type'] for s in v.resolved_stages()]
        ['discussion', 'vote']
        >>> v.resolved_stages()[1]['method']
        'weighted'
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
        decision_mode: DecisionMode = "none",
        decision_prompt: Optional[str] = None,
        decision_options: Optional[List[str]] = None,
        deciders: Optional[List[str]] = None,
        vote_method: str = "plurality",
        moderator: Optional[Dict[str, Any]] = None,
        stages: Optional[List[Dict[str, Any]]] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """Create a group-discussion / deliberation question.

        Provide either the simple arguments (``max_rounds`` + ``decision_mode``)
        or an explicit ``stages`` list for full orchestration. ``stages`` wins
        when both are given.

        See the module docstring for the stage schema and actor fields.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.participants = _normalize_participants(participants)
        self.max_rounds = max_rounds
        self.turn_instruction = turn_instruction or DEFAULT_TURN_INSTRUCTION
        self.turn_order = turn_order

        if decision_mode not in ("none", "moderator", "vote", "consensus"):
            raise ValueError(
                f"decision_mode must be none/moderator/vote/consensus, got {decision_mode!r}"
            )
        self.decision_mode = decision_mode
        self.decision_prompt = decision_prompt
        self.decision_options = (
            [str(o) for o in decision_options] if decision_options else None
        )
        self.deciders = [str(d) for d in deciders] if deciders else None
        if vote_method not in VOTE_METHODS:
            raise ValueError(
                f"vote_method must be one of {VOTE_METHODS}, got {vote_method!r}"
            )
        self.vote_method = vote_method
        self.moderator = _normalize_moderator(moderator)
        self.stages = (
            [_normalize_stage(s, i) for i, s in enumerate(stages)] if stages else None
        )

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
        base_data["decision_mode"] = self.decision_mode
        base_data["decision_prompt"] = self.decision_prompt
        base_data["decision_options"] = self.decision_options
        base_data["deciders"] = self.deciders
        base_data["vote_method"] = self.vote_method
        base_data["moderator"] = self.moderator
        base_data["stages"] = self.stages
        return base_data

    # ---- orchestration ------------------------------------------------------

    def resolved_stages(self) -> List[Dict[str, Any]]:
        """Return the explicit ``stages`` or compile the simple sugar into one.

        Simple mode = one ``discussion`` stage of ``max_rounds`` rounds, plus one
        decision stage derived from ``decision_mode``.
        """
        if self.stages:
            return self.stages

        stages: List[Dict[str, Any]] = [
            _normalize_stage(
                {
                    "type": "discussion",
                    "name": "discussion",
                    "rounds": self.max_rounds,
                    "turn_instruction": self.turn_instruction,
                },
                0,
            )
        ]
        if self.decision_mode == "moderator":
            stages.append(
                _normalize_stage(
                    {
                        "type": "moderator",
                        "name": "decision",
                        "prompt": self.decision_prompt or self.question_text,
                    },
                    1,
                )
            )
        elif self.decision_mode == "consensus":
            stages.append(
                _normalize_stage(
                    {
                        "type": "consensus",
                        "name": "decision",
                        "prompt": self.decision_prompt or self.question_text,
                    },
                    1,
                )
            )
        elif self.decision_mode == "vote":
            stages.append(
                _normalize_stage(
                    {
                        "type": "vote",
                        "name": "decision",
                        "prompt": self.decision_prompt or self.question_text,
                        "method": self.vote_method,
                        "options": self.decision_options,
                        "participants": self.deciders,
                    },
                    1,
                )
            )
        return stages

    def participant_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for p in self.participants:
            if p["name"] == name:
                return p
        return None

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        transcript = []
        rnd = 1
        for stage in self.resolved_stages():
            names = stage["participants"] or [p["name"] for p in self.participants]
            if stage["type"] in ("discussion", "consensus"):
                for _r in range(stage["rounds"]):
                    for n in names:
                        transcript.append(
                            {
                                "speaker": n,
                                "round": rnd,
                                "kind": "discussion",
                                "stage": stage["name"],
                                "content": [{"type": "text", "text": f"({n})"}],
                            }
                        )
                    rnd += 1
            else:
                transcript.append(
                    {
                        "speaker": self.moderator["name"],
                        "round": rnd,
                        "kind": "decision",
                        "stage": stage["name"],
                        "content": [{"type": "text", "text": "(decision)"}],
                    }
                )
                rnd += 1
        return {"answer": transcript, "generated_tokens": None}

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        return Template(
            """
        <div class="group-discussion-question">
            <h3>Premise:</h3><p>{{ question_text }}</p>
            <h3>Participants:</h3>
            <ul>{% for p in participants %}<li>{{ p.name }} ({{ p.role }})</li>{% endfor %}</ul>
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
            decision_mode="moderator",
        )

    @classmethod
    @inject_exception
    def example_vote(cls, randomize: bool = False) -> "QuestionGroupDiscussion":
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="budget_vote",
            question_text=(
                f"The town has $10,000 left this year. Decide how to spend it.{addition}"
            ),
            participants=[
                {
                    "name": "mayor",
                    "persona": "You chair the council.",
                    "goal": "A balanced outcome.",
                    "vote_weight": 2.0,
                    "role": "chair",
                },
                {
                    "name": "treasurer",
                    "persona": "You manage finances.",
                    "goal": "Spend prudently.",
                },
                {
                    "name": "teacher",
                    "persona": "You run the school.",
                    "goal": "Books and laptops.",
                },
            ],
            max_rounds=2,
            decision_mode="vote",
            decision_options=["schools", "clinic", "roads", "split evenly"],
            deciders=["mayor", "treasurer"],
            vote_method="weighted",
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
