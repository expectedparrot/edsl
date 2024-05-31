from typing import Dict

import pandas as pd

from edsl.conjure.SurveyBuilder import SurveyBuilder
from edsl.conjure.utilities import RCodeSnippet

class SurveyBuilderCSV(SurveyBuilder):


    @staticmethod
    def get_dataframe(datafile_name):
        return pd.read_csv(datafile_name)

    def get_responses(self) -> Dict:
        """Returns a dataframe of responses by reading the datafile_name.
        
        The structure should be a dictionary, where the keys are the question codes,
        and the values are the responses.

        For example, {"Q1": [1, 2, 3], "Q2": [4, 5, 6]}
        """
        df = self.get_dataframe(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        data_dict = df.to_dict(orient="list")
        return {k.lower(): v for k, v in data_dict.items()}

    def get_question_name_to_text(self) -> Dict:
        """
        Get the question name to text mapping.
        """
        d = {}
        df = self.get_dataframe(self.datafile_name)
        for col in df.columns:
            if col in self.lookup_dict():
                d[col] = self.lookup_dict()[col]
            else:
                d[col] = col

        return d

    def get_question_name_to_answer_book(self):
        """Returns a dictionary mapping question codes to a dictionary mapping answer codes to answer text.

        e.g., {'q1': {1: 'yes', 2:'no'}}
        """
        d = self.get_question_name_to_text()
        return {k: {} for k, v in d.items()}


class SurveyBuilderStata(SurveyBuilderCSV):

    @staticmethod
    def get_dataframe(datafile_name):
        return pd.read_stata(datafile_name)

if __name__ == "__main__":
    sb = SurveyBuilderCSV("responses.csv")
    sb.save("podcast_survey")
