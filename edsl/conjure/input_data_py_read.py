import pandas as pd
from typing import List

from .input_data import InputDataABC
from .utilities import convert_value
from edsl.utilities import is_valid_variable_name

try:
    import pyreadstat
except ImportError as e:
    raise ImportError(
        "The 'pyreadstat' package is required for this feature. Please install it by running:\n"
        "pip install pyreadstat\n"
    ) from e


class InputDataPyRead(InputDataABC):
    def pyread_function(self, datafile_name):
        raise NotImplementedError

    def _parse(self) -> None:
        try:
            df, meta = self.pyread_function(self.datafile_name)
        except Exception as e:
            raise ValueError(
                f"An error occurred while reading the file {self.datafile_name}."
            ) from e
        float_columns = df.select_dtypes(include=["float64"]).columns
        if len(float_columns) > 0:
            df.loc[:, float_columns] = df.loc[:, float_columns].astype(str)

        df = df.fillna("")
        df = df.astype(str)
        self._df = df
        self._meta = meta

    def get_df(self) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            self._parse()
        return self._df

    def get_answer_codebook(self):
        if not hasattr(self, "_meta"):
            self._parse()

        question_name_to_label_name = self._meta.variable_to_label
        label_name_to_labels = self._meta.value_labels
        return {
            qn: label_name_to_labels[label_name]
            for qn, label_name in question_name_to_label_name.items()
        }

    def get_raw_data(self) -> List[List[str]]:
        df = self.get_df()
        data = [
            [convert_value(obs) for obs in v]
            for k, v in df.to_dict(orient="list").items()
        ]
        return data

    @property
    def question_names_to_question_texts(self):
        """Return a dictionary of question names to question texts.
        This will repair the question names if they are not valid Python identifiers using the
        same question_name_repair_func that was passed in.
        """
        if not hasattr(self, "_meta"):
            self._parse()
        d = {}
        for qn, label in self._meta.column_names_to_labels.items():
            new_name = qn
            if not is_valid_variable_name(qn):
                new_name = self.question_name_repair_func(qn)
                if not is_valid_variable_name(new_name):
                    raise ValueError(
                        f"""Question names must be valid Python identifiers. '{qn}' is not.""",
                        """You can pass an entry in question_name_repair_dict to fix this.""",
                    )
            if label is not None:
                d[new_name] = label
        return d

    def get_question_texts(self):
        if not hasattr(self, "_meta"):
            self._parse()
        return [
            self.question_names_to_question_texts.get(qn, qn)
            for qn in self.question_names
        ]

    def get_question_names(self):
        return self.get_df().columns.tolist()
