import textwrap
from typing import Dict
import json

import pandas as pd

from edsl.conjure.SurveyBuilder import SurveyBuilder
from edsl.conjure.utilities import RCodeSnippet


class SurveyBuilderSPSS(SurveyBuilder):
    header_r_code = RCodeSnippet(
        textwrap.dedent(
            """ 
    library(haven)
    library(jsonlite)
    args <- commandArgs(trailingOnly = TRUE)
    sav_file_path <- args[1]
    data <- read_sav(sav_file_path)
    """
        )
    )

    get_responses_r_code = header_r_code + RCodeSnippet(
        """
    write.csv(data, file = stdout(), row.names = FALSE)
    """
    )

    get_question_code_to_question_text_r_code = header_r_code + RCodeSnippet(
        textwrap.dedent(
            """
    question_codes <- colnames(data)
    question_labels <- as.character(sapply(data, function(x) {
        lbl <- attr(x, "label")
        if (is.null(lbl)) "" else lbl
    }))
    df <- data.frame(question_codes, question_labels)
    write.csv(df, file = stdout(), row.names = FALSE)
    """
        )
    )

    get_answer_code_to_answer_text_r_code = header_r_code + RCodeSnippet(
        textwrap.dedent(
            """
    convert_label <- function(d){
        df <- data.frame(name = names(d), value = as.numeric(d))
        json_representation <- toJSON(df, pretty = TRUE)
        json_representation
    }

    question_codes <- colnames(data)
    answer_codes <- sapply(data, function(x) convert_label(attr(x, "labels")))

    df <- data.frame(question_codes, answer_codes)
    write.csv(df, file = stdout(), row.names = FALSE)
    """
        )
    )

    def get_df(self) -> pd.DataFrame:
        df = self.get_responses_r_code(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        return df

    def get_raw_data(self) -> List[List[str]]:
        df = self.get_df()
        data = [
            [convert_value(obs) for obs in v]
            for k, v in df.to_dict(orient="list").items()
        ]
        return data

    def get_question_texts(self):
        return list(self.get_df().columns)

    def get_responses(self):
        """Returns a dataframe of responses.
        The structure should be a dictionary, where the keys are the question codes,
        and the values are the responses.

        For example, {"Q1": [1, 2, 3], "Q2": [4, 5, 6]}
        """
        df = self.get_responses_r_code(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        data_dict = df.to_dict(orient="list")
        return {k.lower(): v for k, v in data_dict.items()}

    def get_question_name_to_text(self) -> Dict:
        df = self.get_question_code_to_question_text_r_code(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        data_dict = df.to_dict(orient="list")

        question_codes = [q.lower() for q in data_dict["question_codes"]]
        question_text = data_dict["question_labels"]
        d = dict(zip(question_codes, question_text))
        try:
            assert len(d) == len(question_codes)
        except AssertionError:
            raise ValueError("Duplicate question codes found.")

        return d

    def get_question_name_to_answer_book(self):
        """Returns a dictionary mapping question codes to a dictionary mapping answer codes to answer text.

        e.g., {'q1': {1: 'yes', 2:'no'}}
        """
        df = self.get_answer_code_to_answer_text_r_code(self.datafile_name)
        df.fillna("", inplace=True)
        df = df.astype(str)
        data_dict = df.to_dict(orient="list")
        question_codes = [q.lower() for q in data_dict["question_codes"]]
        answer_dicts = []
        for answer_code in data_dict["answer_codes"]:
            try:
                parsed_list = json.loads(answer_code)
                value = {entry["value"]: entry["name"] for entry in parsed_list}
            except json.JSONDecodeError as e:
                value = answer_code
                print(
                    f"Warning: Could not parse answer_codes for {answer_code} as JSON. Using raw value instead."
                )
            answer_dicts.append(value)

        d = dict(zip(question_codes, answer_dicts))
        return d


if __name__ == "__main__":
    spss_builder = SurveyBuilderSPSS("job_satisfaction.sav", 100)
