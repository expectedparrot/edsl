from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .input_data import InputDataABC
from .pipelines.loaders import load_agent_responses, load_questions_yaml


class InputDataYAML(InputDataABC):
    """
    InputData adapter that reads normalized YAML questions plus agent responses.
    """

    def __init__(
        self,
        datafile_name: str,
        responses_file: str,
        config: Optional[dict] = None,
        **kwargs,
    ):
        self.questions_yaml_path = Path(datafile_name)
        self.responses_file = Path(responses_file)

        question_specs, survey_meta = load_questions_yaml(self.questions_yaml_path)
        response_records = load_agent_responses(self.responses_file)

        self._survey_metadata = survey_meta
        self._question_specs = question_specs
        self._response_records = response_records

        question_names = [spec.question_name for spec in question_specs]
        question_texts = [spec.question_text for spec in question_specs]
        question_types = [spec.question_type for spec in question_specs]
        question_options = [spec.question_options for spec in question_specs]

        question_names_to_question_text = {
            spec.question_name.lower(): spec.question_text for spec in question_specs if spec.question_text
        }

        raw_data, respondent_ids = self._build_raw_data(question_names, response_records)
        self.respondent_ids = respondent_ids
        self.derived_hints_by_question = {
            spec.question_name: spec.derived_hints for spec in question_specs
        }

        super().__init__(
            datafile_name=str(self.questions_yaml_path),
            config=config or {},
            raw_data=raw_data,
            question_names=question_names,
            question_texts=question_texts,
            question_types=question_types,
            question_options=question_options,
            question_names_to_question_text=question_names_to_question_text,
            **kwargs,
        )

    def _build_raw_data(
        self,
        question_names: List[str],
        response_records,
    ) -> tuple[List[List], List[str]]:
        respondent_order = []
        response_lookup: Dict[tuple, object] = {}

        for record in response_records:
            key = (record.respondent_id, record.question_name)
            response_lookup[key] = record.response
            if record.respondent_id not in respondent_order:
                respondent_order.append(record.respondent_id)

        raw_data = []
        for question_name in question_names:
            responses_for_question: List[object] = []
            for respondent_id in respondent_order:
                responses_for_question.append(
                    response_lookup.get((respondent_id, question_name), "missing")
                )
            raw_data.append(responses_for_question)

        return raw_data, respondent_order

    def get_question_texts(self) -> List[str]:
        return [spec.question_text for spec in self._question_specs]

    def get_question_names(self) -> List[str]:
        return [spec.question_name for spec in self._question_specs]

    def get_raw_data(self) -> List[List]:
        return self.raw_data
