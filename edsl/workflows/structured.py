"""Serializable structured-response contracts for workflow steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from edsl import QuestionBudget, QuestionMatrix, Survey


@dataclass(frozen=True)
class ChoiceTable:
    question_name: str
    question_text: str
    rows: tuple[str, ...]
    options: tuple[Any, ...]
    require_monotone: bool = False

    def __init__(self, question_name: str, question_text: str, rows: Sequence[str], options: Sequence[Any], *, require_monotone: bool = False):
        object.__setattr__(self, "question_name", question_name)
        object.__setattr__(self, "question_text", question_text)
        object.__setattr__(self, "rows", tuple(rows))
        object.__setattr__(self, "options", tuple(options))
        object.__setattr__(self, "require_monotone", require_monotone)
        if not question_name or not self.rows or not self.options:
            raise ValueError("choice table requires a name, rows, and options")
        if len(set(self.rows)) != len(self.rows) or len(set(self.options)) != len(self.options):
            raise ValueError("choice-table rows and options must be unique")

    def survey(self) -> Survey:
        return Survey([QuestionMatrix(question_name=self.question_name, question_text=self.question_text, question_items=list(self.rows), question_options=list(self.options), include_comment=False)])

    def to_dict(self) -> dict[str, Any]:
        return {"type": "choice_table", "question_name": self.question_name, "question_text": self.question_text, "rows": list(self.rows), "options": list(self.options), "require_monotone": self.require_monotone}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ChoiceTable":
        return cls(data["question_name"], data["question_text"], data["rows"], data["options"], require_monotone=bool(data.get("require_monotone", False)))

    def validate(self, answers: Mapping[str, Any]) -> None:
        response = answers.get(self.question_name)
        if not isinstance(response, Mapping) or set(response) != set(self.rows):
            raise ValueError(f"choice table {self.question_name!r} requires exactly rows {list(self.rows)!r}")
        if any(value not in self.options for value in response.values()):
            raise ValueError(f"choice table {self.question_name!r} contains an invalid option")
        if self.require_monotone:
            indices = [self.options.index(response[row]) for row in self.rows]
            if indices != sorted(indices):
                raise ValueError(f"choice table {self.question_name!r} violates monotone option order")


@dataclass(frozen=True)
class StrategyTable(ChoiceTable):
    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "type": "strategy_table"}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StrategyTable":
        return cls(data["question_name"], data["question_text"], data["rows"], data["options"], require_monotone=bool(data.get("require_monotone", False)))


@dataclass(frozen=True)
class AllocationVector:
    question_name: str
    question_text: str
    targets: tuple[str, ...]
    budget: int
    exact: bool = True

    def __init__(self, question_name: str, question_text: str, targets: Sequence[str], budget: int, *, exact: bool = True):
        object.__setattr__(self, "question_name", question_name)
        object.__setattr__(self, "question_text", question_text)
        object.__setattr__(self, "targets", tuple(targets))
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "exact", exact)
        if not question_name or not self.targets or len(set(self.targets)) != len(self.targets):
            raise ValueError("allocation vector requires a name and unique targets")
        if not isinstance(budget, int) or budget < 0:
            raise ValueError("allocation-vector budget must be a nonnegative integer")

    def survey(self) -> Survey:
        return Survey([QuestionBudget(question_name=self.question_name, question_text=self.question_text, question_options=list(self.targets), budget_sum=self.budget, permissive=not self.exact, include_comment=False)])

    def to_dict(self) -> dict[str, Any]:
        return {"type": "allocation_vector", "question_name": self.question_name, "question_text": self.question_text, "targets": list(self.targets), "budget": self.budget, "exact": self.exact}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AllocationVector":
        return cls(data["question_name"], data["question_text"], data["targets"], int(data["budget"]), exact=bool(data.get("exact", True)))

    def validate(self, answers: Mapping[str, Any]) -> None:
        response = answers.get(self.question_name)
        if not isinstance(response, Mapping) or set(response) != set(self.targets):
            raise ValueError(f"allocation vector {self.question_name!r} requires exactly targets {list(self.targets)!r}")
        values = list(response.values())
        if any(not isinstance(value, (int, float)) or value < 0 for value in values):
            raise ValueError(f"allocation vector {self.question_name!r} requires nonnegative numeric values")
        total = sum(values)
        if (self.exact and total != self.budget) or (not self.exact and total > self.budget):
            relation = "equal" if self.exact else "not exceed"
            raise ValueError(f"allocation vector {self.question_name!r} total must {relation} {self.budget}")


def structured_contract_from_dict(data: Mapping[str, Any]) -> ChoiceTable | StrategyTable | AllocationVector:
    classes = {"choice_table": ChoiceTable, "strategy_table": StrategyTable, "allocation_vector": AllocationVector}
    try:
        return classes[data["type"]].from_dict(data)
    except KeyError as exc:
        raise ValueError(f"unsupported structured response contract {data.get('type')!r}") from exc
