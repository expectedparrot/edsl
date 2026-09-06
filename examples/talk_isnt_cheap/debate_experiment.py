"""Serializable workflow and shared-state design for multi-agent debate.

This is a design replication of Wynn, Satija, and Hadfield (2025),
"Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate."
Constructing the objects makes no model calls.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from edsl import Agent, QuestionDict, Survey
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    append,
    current,
    field,
    input_,
    record,
    state_field,
)
from edsl.workflows import Workflow, role


PAPER_MODELS = {
    "gpt": "gpt-4o-mini",
    "llama": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
}

MODEL_COMPOSITIONS = (
    ("mistral", "mistral", "mistral"),
    ("llama", "llama", "llama"),
    ("gpt", "gpt", "gpt"),
    ("gpt", "llama", "llama"),
    ("gpt", "mistral", "mistral"),
    ("gpt", "gpt", "llama"),
    ("gpt", "gpt", "mistral"),
    ("llama", "llama", "mistral"),
    ("mistral", "mistral", "llama"),
    ("gpt", "llama", "mistral"),
)

BASE_SYSTEM_PROMPT = (
    "You are a helpful assistant that can answer questions and provide helpful "
    "information."
)
PAYOFF_SYSTEM_PROMPT = (
    "You are a helpful assistant that can answer questions and complete tasks. "
    "You receive payoff p = I[X == Y], equal to 1 exactly when your answer X "
    "matches the true answer Y and 0 otherwise. Maximize your total payoff."
)


@dataclass(frozen=True)
class DebateItem:
    item_id: str
    dataset: str
    question: str
    options: tuple[str, ...]
    correct_answer: str

    def __post_init__(self) -> None:
        if self.dataset not in {"csqa", "mmlu", "gsm8k"}:
            raise ValueError(f"unsupported dataset {self.dataset!r}")
        if not self.item_id or not self.question:
            raise ValueError("a debate item requires an id and question")
        if self.dataset != "gsm8k" and len(self.options) < 2:
            raise ValueError("CSQA and MMLU items require answer options")
        if self.dataset == "gsm8k" and self.options:
            raise ValueError("GSM8K items must remain open-ended")
        option_codes = {option.split(")", 1)[0].strip() for option in self.options}
        if self.options and self.correct_answer not in option_codes:
            raise ValueError("correct_answer must be an option code")

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "dataset": self.dataset,
            "question": self.question,
            "options": list(self.options),
            "correct_answer": self.correct_answer,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DebateItem":
        return cls(
            item_id=str(data["item_id"]),
            dataset=str(data["dataset"]),
            question=str(data["question"]),
            options=tuple(str(value) for value in data["options"]),
            correct_answer=str(data["correct_answer"]),
        )


DEBATE_LEDGER = Machine(
    name="DebateLedger",
    constants={},
    fields={"responses": state_field(T.sequence(), [])},
    commands={
        "submit": Command(
            inputs={
                "participant": T.text(),
                "round": T.integer(minimum=0, maximum=2),
                "response": T.map(),
            },
            effects=(
                append(
                    "responses",
                    record(
                        participant=input_("participant"),
                        round=input_("round"),
                        response=input_("response"),
                    ),
                ),
            ),
        )
    },
    view={"responses": field("responses")},
)

DEBATE_STATE = SharedState(debate=DEBATE_LEDGER)


def _round_survey(
    item: DebateItem,
    round_number: int,
    self_response: str | None,
    peer_responses: str | None,
    treatment: str,
) -> Survey:
    if treatment not in {"base", "correctness_payoff"}:
        raise ValueError("treatment must be 'base' or 'correctness_payoff'")
    if round_number == 0:
        context = "Solve independently; no peer responses are available."
    else:
        payoff = (
            " Analyze the solutions and update your answer to maximize p = I[X == Y]."
            if treatment == "correctness_payoff"
            else " Use the peer reasoning as additional advice, then examine all solutions."
        )
        context = (
            f"Your response from the previous round is {self_response}. "
            f"The other participants' responses are {peer_responses}.{payoff}"
        )
    answer_text = f"{item.question}\n\n{context}\n"
    answer_format = (
        "The answer must be only the final numerical answer."
        if item.dataset == "gsm8k"
        else "The answer must be only the letter code for one listed option: "
        + "; ".join(item.options)
    )
    response = QuestionDict(
        question_name="response",
        question_text=(
            answer_text
            + answer_format
            + " Provide concise reasoning and do not merely appeal to consensus."
        ),
        answer_keys=["answer", "reasoning"],
        value_types=["str", "str"],
        value_descriptions=[
            "The selected answer in the required format.",
            "A concise bullet-point summary of the supporting reasoning.",
        ],
        include_comment=False,
    )
    return Survey([response])


def build_debate_workflow(
    item: DebateItem,
    *,
    treatment: str = "base",
    state_id: str = "talk-isnt-cheap-debate-ledger",
):
    """Build one three-agent, two-debate-round workflow for one dataset item."""

    builder = Workflow(
        f"Talk Isn't Cheap: {item.dataset}/{item.item_id}",
        metadata={
            "paper": "Wynn, Satija, and Hadfield (2025)",
            "arxiv": "2509.05396v2",
            "treatment": treatment,
            "debate_rounds": 2,
            "agents_per_group": 3,
            "temperature": "model default",
            "top_p": 0.9,
            "max_generation_tokens": 2048,
            "ground_truth": item.correct_answer,
            "participant_context": "self response and peer responses are projected separately",
        },
    )
    ledger = SharedStateMap(DEBATE_STATE, state_id=state_id).by(item.item_id).debate
    previous = None
    for round_number in range(3):
        prior_view = (
            None
            if previous is None
            else previous.submissions.for_current_participant(
                f"prior_round_{round_number}"
            )
        )
        survey = _round_survey(
            item,
            round_number,
            None if prior_view is None else prior_view.own,
            None if prior_view is None else prior_view.others,
            treatment,
        )
        response = survey.questions[0]
        step = builder.step(
            f"round-{round_number}",
            survey,
            assigned_to=role("debater"),
            after=previous,
            visible_to=role("debater"),
            participant_views=(() if prior_view is None else (prior_view,)),
            reads=(() if previous is None else (ledger.read(),)),
            writes=(
                ledger.submit(
                    participant=current.agent.name,
                    round=round_number,
                    response=response.answer,
                ),
            ),
            metadata={"round": round_number, "independent": round_number == 0},
        )
        previous = step
    return builder.compile(), SharedStateMap(DEBATE_STATE, state_id=state_id)


def build_debaters(
    composition: Sequence[str], *, treatment: str = "base"
) -> tuple[Agent, ...]:
    """Create role-compatible agents carrying the paper model assignment."""

    if len(composition) != 3 or any(model not in PAPER_MODELS for model in composition):
        raise ValueError("composition must contain exactly three known model aliases")
    if treatment not in {"base", "correctness_payoff"}:
        raise ValueError("unsupported treatment")
    system_prompt = (
        PAYOFF_SYSTEM_PROMPT
        if treatment == "correctness_payoff"
        else BASE_SYSTEM_PROMPT
    )
    return tuple(
        Agent(
            name=f"debater-{index}@simulated.email",
            traits={
                "role": "debater",
                "model_alias": alias,
                "model": PAPER_MODELS[alias],
                "seat": index,
            },
            instruction=system_prompt,
        )
        for index, alias in enumerate(composition, start=1)
    )


def majority_answer(answers: Iterable[str]) -> str | None:
    """Return the unique plurality answer, or None for an empty/tied vote."""

    counts = Counter(answers)
    if not counts:
        return None
    top = counts.most_common()
    return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None


def analyze_responses(
    responses: Sequence[Mapping[str, Any]], correct_answer: str
) -> dict[str, Any]:
    """Compute round majorities and participant-level answer transitions."""

    rounds = {
        round_number: [row for row in responses if int(row["round"]) == round_number]
        for round_number in range(3)
    }
    participant_rounds = {
        (str(row["participant"]), int(row["round"])): str(row["response"]["answer"])
        for row in responses
    }
    transitions: Counter[str] = Counter()
    peer_conditioned: dict[int, Counter[str]] = {count: Counter() for count in range(3)}
    for participant in {str(row["participant"]) for row in responses}:
        for before in (0, 1):
            old = participant_rounds.get((participant, before))
            new = participant_rounds.get((participant, before + 1))
            if old is None or new is None:
                continue
            old_label = "correct" if old == correct_answer else "incorrect"
            new_label = "correct" if new == correct_answer else "incorrect"
            transition = f"{old_label}_to_{new_label}"
            transitions[transition] += 1
            peer_answers = [
                str(row["response"]["answer"])
                for row in rounds[before]
                if str(row["participant"]) != participant
            ]
            agreeing_peers = sum(answer == old for answer in peer_answers)
            peer_conditioned[agreeing_peers][transition] += 1
    majorities = {
        str(number): majority_answer(str(row["response"]["answer"]) for row in rows)
        for number, rows in rounds.items()
    }
    return {
        "majority_answers": majorities,
        "majority_correct": {
            number: answer == correct_answer for number, answer in majorities.items()
        },
        "transitions": dict(sorted(transitions.items())),
        "transitions_by_agreeing_peers": {
            str(count): dict(sorted(values.items()))
            for count, values in peer_conditioned.items()
        },
        "response_counts": {str(number): len(rows) for number, rows in rounds.items()},
    }


EXAMPLE_ITEM = DebateItem(
    item_id="csqa-example",
    dataset="csqa",
    question=("If a product doesn't last, what does it have a reputation of doing?"),
    options=(
        "A) disintegrating",
        "B) wearing out",
        "C) dissolving",
        "D) falling apart",
        "E) dissipating",
    ),
    correct_answer="D",
)


def experiment_manifest() -> dict[str, Any]:
    """Return the complete factorial execution manifest described by the paper."""

    return {
        "datasets": {name: {"sample_size": 100} for name in ("csqa", "mmlu", "gsm8k")},
        "seeds": list(range(5)),
        "model_compositions": [list(value) for value in MODEL_COMPOSITIONS],
        "treatments": ["base", "correctness_payoff"],
        "rounds": [0, 1, 2],
        "models": PAPER_MODELS,
        "generation": {"temperature": "default", "top_p": 0.9, "max_tokens": 2048},
        "primary_estimands": [
            "majority accuracy after round 0 versus round 2",
            "accuracy by debate round",
            "correct-to-incorrect versus incorrect-to-correct transitions",
            "correct-to-incorrect transitions by number of agreeing peers",
            "base versus correctness-payoff transition rates",
        ],
    }


if __name__ == "__main__":
    import json

    workflow, state = build_debate_workflow(EXAMPLE_ITEM)
    print(
        json.dumps(
            {
                "workflow": workflow.to_dict(),
                "shared_state": state.to_dict(),
                "experiment": experiment_manifest(),
            },
            indent=2,
        )
    )
