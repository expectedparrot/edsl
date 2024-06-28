from collections import UserDict
from edsl.conjure.RawResponseColumn import RawResponseColumn
from typing import Dict, List, Any


class RawResponses(UserDict):
    def __init__(
        self,
        responses: Dict[str, RawResponseColumn],
        question_name_to_question_text: Dict[str, str],
        answer_codebook: Dict[str, Dict[str, str]],
    ):
        """
        :param responses: A dictionary mapping question names to RawResponseColumn objects.
        :param question_name_to_question_text: A dictionary mapping question names to question text.
        :param answer_codebook: A dictionary mapping question names to dictionaries mapping raw responses to answer text.
        """
        data = {}
        for question_name, raw_responses in responses.items():
            raw_question_response = RawResponseColumn(
                question_name=question_name,
                raw_responses=raw_responses,
                answer_codebook=answer_codebook.get(question_name, {}),
                question_text=question_name_to_question_text[question_name],
            )
            data[question_name] = raw_question_response
        super().__init__(data)

    def get_observations(self) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries, where each dictionary is an observation.

        >>> sb = SurveyBuilder.example()
        >>> sb.get_observations()
        [{'q1': '1', 'q2': '2', 'q3': '3'}, {'q1': '4', 'q2': '5', 'q3': '6'}]

        """
        observations = []
        for question_name, question_responses in self.items():
            for index, response in enumerate(question_responses.responses):
                if len(observations) <= index:
                    observations.append({question_name: response})
                else:
                    observations[index][question_name] = response
        return observations
