from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ...qualtrics_parser import (
    generate_question_list,
    generate_respondent_answers,
    tidy_qualtrics_three_header_csv,
)
from ..models import AgentResponseRecord, NormalizedSurvey, QuestionSpec
from ..profiles import CsvProfile
from .base import SurveyNormalizer


class QualtricsThreeRowNormalizer(SurveyNormalizer):
    """Normalizer for Qualtrics CSV exports with three or four header rows."""

    def normalize(self, path: Path, profile: CsvProfile) -> NormalizedSurvey:
        long_df, columns_meta = tidy_qualtrics_three_header_csv(
            str(path),
            header_rows=profile.header_rows,
            delimiter=profile.delimiter,
        )

        question_dicts = generate_question_list(long_df, columns_meta)
        respondent_answers = generate_respondent_answers(long_df, question_dicts)

        questions = self._build_question_specs(question_dicts)
        responses, respondent_order = self._build_responses(respondent_answers)

        metadata = {
            "source": "qualtrics_three_row",
            "header_rows": profile.header_rows,
            "delimiter": profile.delimiter,
        }

        return NormalizedSurvey(
            questions=questions,
            responses=responses,
            respondent_order=respondent_order,
            source_metadata=metadata,
        )

    def _build_question_specs(self, question_dicts: List[Dict]) -> List[QuestionSpec]:
        specs: List[QuestionSpec] = []

        for entry in question_dicts:
            derived_hints = dict(entry.get("derived_hints", {}))
            options = entry.get("question_options")
            options_list = list(options) if options else None
            specs.append(
                QuestionSpec(
                    question_name=entry["question_name"],
                    question_text=entry.get("question_text") or "",
                    question_type=entry.get("question_type", "unknown"),
                    question_options=options_list,
                    derived_hints=derived_hints,
                )
            )

        return specs

    def _build_responses(
        self, respondent_answers: List[Dict]
    ) -> tuple[List[AgentResponseRecord], List[str]]:
        records: List[AgentResponseRecord] = []
        respondent_order: List[str] = []

        for respondent in respondent_answers:
            respondent_id = respondent.get("respondent_id")
            if respondent_id is None:
                continue
            respondent_order.append(str(respondent_id))
            answers: Dict[str, object] = respondent.get("answers", {})

            for question_name, value in answers.items():
                response_kind = _infer_response_kind(value)
                response_metadata = {}
                if response_kind == "list":
                    response_metadata["selection_order_hint"] = "source"
                if response_kind == "dict":
                    response_metadata["structure"] = "subparts"

                records.append(
                    AgentResponseRecord(
                        respondent_id=str(respondent_id),
                        question_name=question_name,
                        response=value,
                        response_kind=response_kind,
                        response_metadata=response_metadata,
                    )
                )

        return records, respondent_order


def _infer_response_kind(value) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "scalar"
