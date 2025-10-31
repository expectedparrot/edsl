from pathlib import Path
from typing import List, Optional, Dict, Callable, Union

from edsl import FileStore


class Conjure:
    def __new__(cls, datafile_name: Union[str, FileStore], *args, **kwargs):
        from .input_data_csv import InputDataCSV
        from .input_data_spss import InputDataSPSS
        from .input_data_stata import InputDataStata
        from .input_data_yaml import InputDataYAML
        from .input_data_normalized import InputDataNormalized
        from .pipelines.profiles import detect_csv_profile
        from .pipelines.pipeline import normalize_survey_file
        from .pipelines.format_inference import refine_profile_with_llm

        if isinstance(datafile_name, FileStore):
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file_with_extension = temp_file.name + "." + datafile_name.suffix
                datafile_name.write(temp_file_with_extension)
                datafile_name = temp_file_with_extension

        file_type = datafile_name.split(".")[-1].lower()

        if file_type == "csv":
            csv_path = Path(datafile_name)
            normalized_instance = cls._maybe_normalize_csv(
                csv_path,
                InputDataNormalized,
                detect_csv_profile,
                refine_profile_with_llm,
                normalize_survey_file,
                *args,
                **kwargs,
            )
            if normalized_instance is not None:
                return normalized_instance

        handlers = {
            "csv": InputDataCSV,
            "sav": InputDataSPSS,
            "dta": InputDataStata,
            "yaml": InputDataYAML,
            "yml": InputDataYAML,
        }

        handler = handlers.get(file_type)
        if handler is None:
            raise ValueError(f"Unsupported file type: {file_type}")

        instance = handler(datafile_name, *args, **kwargs)
        return instance

    @staticmethod
    def _maybe_normalize_csv(
        csv_path: Path,
        normalized_cls,
        detect_csv_profile,
        refine_profile_with_llm,
        normalize_survey_file,
        *args,
        **kwargs,
    ):
        try:
            profile = detect_csv_profile(csv_path)
            profile = refine_profile_with_llm(csv_path, profile)
        except Exception:
            return None

        from .pipelines.profiles import CsvFormat

        if profile.format == CsvFormat.SIMPLE:
            return None

        try:
            normalized = normalize_survey_file(csv_path, profile=profile)
        except Exception:
            return None

        return normalized_cls(
            normalized_survey=normalized,
            datafile_name=str(csv_path),
            *args,
            **kwargs,
        )

    def __init__(
        self,
        datafile_name: str,
        config: Optional[dict] = None,
        naming_function: Optional[Callable] = None,
        raw_data: Optional[List] = None,
        question_names: Optional[List[str]] = None,
        question_texts: Optional[List[str]] = None,
        question_names_to_question_text: Optional[Dict[str, str]] = None,
        answer_codebook: Optional[Dict] = None,
        question_types: Optional[List[str]] = None,
        question_options: Optional[List] = None,
        order_options=False,
        question_name_repair_func: Callable = None,
    ):
        # The __init__ method in Conjure won't be called because __new__ returns a different class instance.
        pass

    @classmethod
    def example(cls):
        from InputData import InputDataABC

        return InputDataABC.example()
