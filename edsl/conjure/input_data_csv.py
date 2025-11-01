from typing import List, Optional
import pandas as pd
from .input_data import InputDataABC
from .utilities import convert_value
from rich.console import Console


class InputDataCSV(InputDataABC):
    def __init__(self, datafile_name: str, config: Optional[dict] = None, **kwargs):
        if config is None:
            config = {"skiprows": None, "delimiter": ","}

        super().__init__(datafile_name, config, **kwargs)

    def get_df(self, verbose: bool = False) -> pd.DataFrame:
        if not hasattr(self, "_df"):
            console = Console(stderr=True)

            if verbose:
                console.print(f"[dim]Loading CSV data from {self.datafile_name}[/dim]")

            self._df = pd.read_csv(
                self.datafile_name,
                skiprows=self.config["skiprows"],
                encoding_errors="ignore",
            )

            if verbose:
                console.print(
                    f"[dim]Loaded {len(self._df)} rows, {len(self._df.columns)} columns[/dim]"
                )

            float_columns = self._df.select_dtypes(include=["float64"]).columns
            if len(float_columns) > 0:
                self._df.loc[:, float_columns] = self._df.loc[:, float_columns].astype(
                    str
                )
            self._df = self._df.fillna("")
            self._df = self._df.astype(str)

            if verbose:
                console.print("[green]✓[/green] CSV data loaded and processed")

        return self._df

    def get_raw_data(self) -> List[List[str]]:
        verbose = getattr(self, "_verbose", False)
        data = [
            [convert_value(obs) for obs in v]
            for k, v in self.get_df(verbose=verbose).to_dict(orient="list").items()
        ]
        return data

    def get_question_texts(self):
        verbose = getattr(self, "_verbose", False)
        return list(self.get_df(verbose=verbose).columns)

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
