from typing import List, Optional
import pandas as pd
from edsl.conjure.InputData import InputDataABC
from edsl.conjure.utilities import convert_value


class InputDataCSV(InputDataABC):
    def __init__(self, datafile_name: str, config: Optional[dict] = None, **kwargs):
        if config is None:
            config = {"skiprows": None, "delimiter": ","}

        super().__init__(datafile_name, config, **kwargs)

    def get_df(self) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            self._df = pd.read_csv(
                self.datafile_name,
                skiprows=self.config["skiprows"],
                encoding_errors="ignore",
            )
            float_columns = self._df.select_dtypes(include=["float64"]).columns
            self._df[float_columns] = self._df[float_columns].astype(str)
            self._df.fillna("", inplace=True)
            self._df = self._df.astype(str)
        return self._df

    def get_raw_data(self) -> List[List[str]]:
        data = [
            [convert_value(obs) for obs in v]
            for k, v in self.get_df().to_dict(orient="list").items()
        ]
        return data

    def get_question_texts(self):
        return list(self.get_df().columns)

    def get_question_names(self):
        new_names = [self.naming_function(q) for q in self.question_texts]

        if len(new_names) > len(set(new_names)):
            from collections import Counter

            counter = Counter(new_names)
            for i, name in enumerate(new_names):
                if counter[name] > 1:
                    new_names[i] = name + str(counter[name])
                    counter[name] -= 1
        return new_names
