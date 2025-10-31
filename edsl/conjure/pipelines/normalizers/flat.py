from __future__ import annotations

from pathlib import Path
from typing import List

from ...input_data_csv import InputDataCSV
from ..models import AgentResponseRecord, NormalizedSurvey, QuestionSpec
from ..profiles import CsvProfile
from .base import SurveyNormalizer


class FlatCsvNormalizer(SurveyNormalizer):
    """Normalize simple CSV files where each column is a question."""

    def normalize(self, path: Path, profile: CsvProfile) -> NormalizedSurvey:
        config = {"skiprows": None, "delimiter": profile.delimiter}
        input_data = InputDataCSV(str(path), config=config)

        question_specs = self._build_question_specs(input_data)
        responses, respondent_order = self._build_responses(input_data)

        metadata = {
            "source": "flat_csv",
            "delimiter": profile.delimiter,
        }

        return NormalizedSurvey(
            questions=question_specs,
            responses=responses,
            respondent_order=respondent_order,
            source_metadata=metadata,
        )

    def _build_question_specs(self, input_data: InputDataCSV) -> List[QuestionSpec]:
        specs: List[QuestionSpec] = []

        for idx, question_name in enumerate(input_data.question_names):
            question_text = input_data.question_texts[idx]
            question_type = input_data.question_type.question_types[idx]
            options = input_data.question_option.question_options[idx]

            derived_hints = {
                "raw_question_name": question_text,
                "source": "flat_csv",
                "option_order": "source_column_order",
                "allows_multiple": question_type in {"checkbox", "multiple_response"},
            }

            specs.append(
                QuestionSpec(
                    question_name=question_name,
                    question_text=question_text,
                    question_type=question_type,
                    question_options=list(options) if options else None,
                    derived_hints=derived_hints,
                )
            )

        return specs

    def _build_responses(
        self,
        input_data: InputDataCSV,
    ) -> tuple[List[AgentResponseRecord], List[str]]:
        num_observations = input_data.num_observations
        respondent_order = [str(i + 1) for i in range(num_observations)]

        question_names = input_data.question_names

        records: List[AgentResponseRecord] = []

        for row_idx, respondent_id in enumerate(respondent_order):
            for q_idx, question_name in enumerate(question_names):
                value = input_data.raw_data[q_idx][row_idx]
                response_kind = _infer_response_kind(value)
                records.append(
                    AgentResponseRecord(
                        respondent_id=respondent_id,
                        question_name=question_name,
                        response=value,
                        response_kind=response_kind,
                    )
                )

        return records, respondent_order


def _infer_response_kind(value) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "scalar"
