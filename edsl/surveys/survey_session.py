"""Stateful, locally testable navigation for human survey respondents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import EndOfSurvey


class SurveySession:
    """Apply human navigation policy on top of a survey's forward flow."""

    def __init__(self, survey, humanize_schema: Optional[Dict[str, Any]] = None):
        self.survey = survey
        self.humanize_schema = deepcopy(humanize_schema or {})
        self.active_path = []
        self.current_index = 0
        self.active_rule_answers: Dict[str, Any] = {}
        self.answer_records: Dict[str, list[Dict[str, Any]]] = {}
        self._navigation_events: list[Dict[str, Any]] = []
        self._inactive_answers: Dict[str, Dict[str, Any]] = {}

        first = self.survey.next_question_with_instructions()
        if first is not EndOfSurvey:
            self.active_path.append(first)

    @property
    def current_name(self) -> Optional[str]:
        item = self.current()
        if item is EndOfSurvey:
            return None
        return getattr(item, "question_name", getattr(item, "name", None))

    def current(self):
        if self.current_index >= len(self.active_path):
            return EndOfSurvey
        return self.active_path[self.current_index]

    def answer(self, question_name: str, value: Any) -> None:
        item = self.current()
        if item is EndOfSurvey or getattr(item, "question_name", None) != question_name:
            raise ValueError(f"{question_name!r} is not the current question")

        key = f"{question_name}.answer"
        prior_exists = key in self.active_rule_answers
        prior_value = self.active_rule_answers.get(key)
        if prior_exists and prior_value != value:
            self._truncate_after_current()

        revision = len(self.answer_records.get(question_name, [])) + 1
        record = {"answer": deepcopy(value), "revision": revision}
        self.answer_records.setdefault(question_name, []).append(record)
        self.active_rule_answers[key] = value
        self._inactive_answers.pop(question_name, None)
        self._navigation_events.append(
            {
                "event": "answer",
                "question": question_name,
                "answer": deepcopy(value),
                "revision": revision,
            }
        )

    def forward(self):
        current = self.current()
        if current is EndOfSurvey:
            return EndOfSurvey

        # Revisiting without changing an answer follows the already visited path.
        if self.current_index + 1 < len(self.active_path):
            next_item = self.active_path[self.current_index + 1]
        else:
            next_item = self.survey.next_question_with_instructions(
                current, self.active_rule_answers
            )
            if next_item is not EndOfSurvey:
                self.active_path.append(next_item)

        self._navigation_events.append(
            {
                "event": "forward",
                "from": self._item_name(current),
                "to": None if next_item is EndOfSurvey else self._item_name(next_item),
            }
        )
        self.current_index += 1
        return next_item

    def can_back(self) -> bool:
        if not self._back_enabled() or self.current_index == 0:
            return False
        # A boundary question may be revisited, but cannot itself be crossed.
        if self.current_index < len(self.active_path):
            current = self.active_path[self.current_index]
            qname = getattr(current, "question_name", None)
            if qname and not self._allow_back_past(qname):
                return False
        return True

    def back(self):
        if not self.can_back():
            raise RuntimeError("Back navigation is not available")
        old = self.current()
        self.current_index -= 1
        new = self.current()
        self._navigation_events.append(
            {
                "event": "back",
                "from": None if old is EndOfSurvey else self._item_name(old),
                "to": self._item_name(new),
            }
        )
        return new

    def final_answers(self) -> Dict[str, Any]:
        return {
            key.removesuffix(".answer"): deepcopy(value)
            for key, value in self.active_rule_answers.items()
        }

    def navigation_history(self) -> list[Dict[str, Any]]:
        return deepcopy(self._navigation_events)

    def inactive_answers(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self._inactive_answers)

    def final_result_metadata(self) -> Dict[str, Any]:
        return {
            "humanize_navigation": {
                "events": self.navigation_history(),
                "inactive_answers": self.inactive_answers(),
            }
        }

    def _truncate_after_current(self) -> None:
        downstream = self.active_path[self.current_index + 1 :]
        for item in downstream:
            qname = getattr(item, "question_name", None)
            key = f"{qname}.answer" if qname else None
            if key and key in self.active_rule_answers:
                record = deepcopy(self.answer_records[qname][-1])
                record["reason"] = "path_truncated"
                self._inactive_answers[qname] = record
                del self.active_rule_answers[key]
                self._navigation_events.append(
                    {
                        "event": "invalidate",
                        "question": qname,
                        "reason": "path_truncated",
                    }
                )
        del self.active_path[self.current_index + 1 :]

    def _back_enabled(self) -> bool:
        return bool(
            self.humanize_schema.get("survey", {})
            .get("navigation", {})
            .get("back_button", False)
        )

    def _allow_back_past(self, question_name: str) -> bool:
        return bool(
            self.humanize_schema.get("questions", {})
            .get(question_name, {})
            .get("navigation", {})
            .get("allow_back_past", True)
        )

    @staticmethod
    def _item_name(item) -> Optional[str]:
        return getattr(item, "question_name", getattr(item, "name", None))
