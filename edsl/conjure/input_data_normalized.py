from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .input_data import InputDataABC
from .pipelines.models import NormalizedSurvey


class InputDataNormalized(InputDataABC):
    """InputData adapter backed by an in-memory NormalizedSurvey."""

    def __init__(
        self,
        normalized_survey: NormalizedSurvey,
        datafile_name: str,
        config: Optional[dict] = None,
        question_names_to_question_text: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        self.normalized_survey = normalized_survey
        self.source_path = Path(datafile_name)

        question_specs = normalized_survey.questions
        respondent_order = normalized_survey.respondent_order

        question_names = [spec.question_name for spec in question_specs]
        question_texts = [spec.question_text for spec in question_specs]
        question_types = [spec.question_type for spec in question_specs]
        question_options = [spec.question_options for spec in question_specs]

        derived_hints = {
            spec.question_name: spec.derived_hints for spec in question_specs
        }
        self.derived_hints_by_question = derived_hints
        self.respondent_ids = respondent_order

        mapping = question_names_to_question_text or {
            spec.question_name.lower(): spec.question_text
            for spec in question_specs
            if spec.question_text
        }

        raw_data = self._build_raw_data(
            question_names, respondent_order, normalized_survey.responses
        )

        super().__init__(
            datafile_name=datafile_name,
            config=config or {},
            raw_data=raw_data,
            question_names=question_names,
            question_texts=question_texts,
            question_types=question_types,
            question_options=question_options,
            question_names_to_question_text=mapping,
            **kwargs,
        )

    @staticmethod
    def _build_raw_data(
        question_names: List[str],
        respondent_order: List[str],
        responses,
    ) -> List[List]:
        by_question: Dict[str, Dict[str, object]] = {qn: {} for qn in question_names}

        for record in responses:
            by_question.setdefault(record.question_name, {})[
                record.respondent_id
            ] = record.response

        raw_data: List[List] = []
        for question_name in question_names:
            respondent_to_response = by_question.get(question_name, {})
            question_responses: List[object] = []
            for respondent_id in respondent_order:
                question_responses.append(
                    respondent_to_response.get(respondent_id, "missing")
                )
            raw_data.append(question_responses)
        return raw_data

    def get_question_texts(self) -> List[str]:
        return [spec.question_text for spec in self.normalized_survey.questions]

    def get_question_names(self) -> List[str]:
        return [spec.question_name for spec in self.normalized_survey.questions]

    def get_raw_data(self) -> List[List]:
        return self.raw_data
