from typing import Dict, List

import pandas as pd

from edsl.conjure.SurveyBuilder import SurveyBuilder
from edsl.conjure.utilities import RCodeSnippet
from edsl.conjure.SurveyResponses import SurveyResponses


class SurveyBuilderCSV(SurveyBuilder):
    @staticmethod
    def get_dataframe(datafile_name, skiprows=None):
        return pd.read_csv(datafile_name, skiprows=skiprows)

    def get_raw_data(self) -> Dict:
        """Returns a dataframe of responses by reading the datafile_name.

        The structure should be a dictionary, where the keys are the question codes,
        and the values are the responses.

        >>> sb = SurveyBuilderCSV.example()
        >>> sb.get_responses()
        {'q1': ['1', '4'], 'q2': ['2', '5'], 'q3': ['3', '6']}

        """
        df = self.get_dataframe(self.datafile_name, skiprows=self.skiprows)
        df.fillna("", inplace=True)
        df = df.astype(str)
        data = {k: v for k, v in df.to_dict(orient="list").items()}
        return SurveyResponses(data)

    def get_question_name_to_text(self) -> Dict:
        """
        Get the question name to text mapping.

        >>> sb = SurveyBuilderCSV.example()
        >>> sb.get_question_name_to_text()
        {'Q1': 'Q1', 'Q2': 'Q2', 'Q3': 'Q3'}

        """
        d = {}
        df = self.get_dataframe(self.datafile_name, skiprows=self.skiprows)
        for col in df.columns:
            if col in self.replacement_finder:
                d[col] = self.replacement_finder[col]
            else:
                raise ValueError(
                    f"Question name {col} not found in replacement finder."
                )
                d[col] = col

        return d

    def get_question_name_to_answer_book(self):
        """Returns a dictionary mapping question codes to a dictionary mapping answer codes to answer text."""
        d = self.get_question_name_to_text()
        return {k: {} for k, v in d.items()}

    @classmethod
    def example(cls):
        import tempfile

        named_temp_file = tempfile.NamedTemporaryFile(delete=False)
        named_temp_file.write(b"Q1,Q2,Q3\n1,2,3\n4,5,6\n")
        named_temp_file.close()
        return cls(named_temp_file.name)


class SurveyBuilderStata(SurveyBuilderCSV):
    @staticmethod
    def get_dataframe(datafile_name):
        return pd.read_stata(datafile_name)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    # sb = SurveyBuilderCSV("responses.csv")
    # sb.save("podcast_survey")
