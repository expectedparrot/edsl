from functools import partial
from itertools import chain
from edsl.report.InputOutputDataTypes import (
    CategoricalData,
    NumericalData,
    FreeTextData,
)


class ResultsFetchMixin:
    def fetch_list(self, data_type, key) -> list:
        print("Change to using _fetch_list here")
        return self._fetch_list(data_type, key)

    def _fetch_list(self, data_type, key) -> list:
        """
        For a given data type and key, return a list of values from the data.
        It uses the filtered data, not the original data.
        >>> r = Results.create_example()
        >>> r._fetch_list('answer', 'how_feeling')
        ['Bad', 'Bad', 'Great', 'Great']
        """
        returned_list = []
        for row in self.data:
            returned_list.append(row.sub_dicts[data_type].get(key, None))

        return returned_list

    def _fetch_answer_data(self, key, element_data_class):
        """Extracts data from a results object and returns in in the corresponding element_data_class."""
        question = self.survey.get_question(key)
        question_type = question.question_type
        options = getattr(question, "question_options", None)
        responses = self._fetch_list("answer", key)

        if hasattr(question, "short_names_dict"):
            short_names_dict = getattr(question, "short_names_dict", {})
        else:
            short_names_dict = {}

        data = {
            "text": question.question_text,
            "short_names_dict": short_names_dict,
        }

        if element_data_class == CategoricalData:
            if question_type in ["checkbox"]:
                data["responses"] = [
                    str(r) for r in list(chain.from_iterable(responses))
                ]
            else:
                data["responses"] = [str(r) for r in responses]

            data["options"] = [str(o) for o in options]

        elif element_data_class == NumericalData:
            data["responses"] = [float(x) for x in responses]
        elif element_data_class == FreeTextData:
            data["responses"] = [str(r) for r in responses]
        else:
            raise Exception(f"Not yet implemented")

        return element_data_class(**data)

    def _fetch_other_data(self, data_type, key, element_data_class):
        if element_data_class == CategoricalData:
            responses = self._fetch_list(data_type, key)
            options = list(set(responses))
            if data_type == "agent":
                text = "Agent attributes:" + self[0].agent.get_original_name(key)
            else:
                text = data_type + "." + key
            return CategoricalData(
                responses=[str(r) for r in responses],
                options=[str(o) for o in options],
                text=text,
            )
        else:
            raise Exception(f"Not yet implemented")

    def _fetch_element(self, data_type, key, element_data_class):
        """Extracts data from a results object and returns in in the corresponding element_data_class."""
        data_types_to_functions = {
            "answer": self._fetch_answer_data,
            "agent": partial(self._fetch_other_data, "agent"),
            "survey": partial(self._fetch_other_data, "survey"),
            "model": partial(self._fetch_other_data, "model"),
            "scenario": partial(self._fetch_other_data, "scenario"),
        }
        return data_types_to_functions[data_type](key, element_data_class)
