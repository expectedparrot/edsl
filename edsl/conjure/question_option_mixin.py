from typing import Union, List


class QuestionOptionModule:
    def __init__(self, input_data):
        self.input_data = input_data
        self._question_options = None
    
    @property
    def question_options(self):
        if self._question_options is None:
            self.question_options = None
        return self._question_options

    @question_options.setter
    def question_options(self, value):
        if value is None:
            value = [self._get_question_options(qn) for qn in self.input_data.question_names]
        else:
            # Clean each option list in the value if it's a list of lists
            if isinstance(value, list):
                from .input_data import _clean_question_options
                value = [_clean_question_options(options) if options is not None else None for options in value]
        self._question_options = value

    def _get_question_options(self, question_name) -> Union[List[str], None]:
        """Return the options for a question.

        >>> from .input_data import InputDataABC
        >>> id = InputDataABC.example()
        >>> sorted(id.question_options._get_question_options('morning'))
        ['1', '4']

        """
        qt = self.input_data.question_stats.question_statistics(question_name)
        idx = self.input_data.question_names.index(question_name)
        question_type = self.input_data.question_type.question_types[idx]
        if question_type == "multiple_choice":
            options = [str(o).strip() for o in qt.unique_responses]
            return [opt for opt in options if opt]  # Remove empty options
        else:
            if question_type == "multiple_choice_with_other":
                options = self.input_data.question_stats.unique_responses_more_than_k(2)[
                    self.input_data.question_names.index(question_name)
                ] + [self.input_data.OTHER_STRING]
                cleaned_options = [str(o).strip() for o in options]
                return [opt for opt in cleaned_options if opt]  # Remove empty options
            else:
                return None

    def order_options(self) -> None:
        """Order the options for multiple choice questions using an LLM."""
        from edsl import QuestionList
        from edsl import ScenarioList
        import textwrap

        scenarios = (
            ScenarioList.from_list("example_question_name", self.input_data.question_names)
            .add_list("example_question_text", self.input_data.question_texts)
            .add_list("example_question_type", self.input_data.question_type.question_types)
            .add_list("example_question_options", self.question_options)
        ).filter(
            'example_question_type == "multiple_choice" or example_question_type == "multiple_choice_with_other"'
        )

        question = QuestionList(
            question_text=textwrap.dedent(
                """\
            We have a survey question: `{{ example_question_text }}`.
            
            The survey had following options: '{{ example_question_options }}'.
            The options might be out of order. Please put them in the correct order.
            If there is no natural order, just put then in order they were presented.
            """
            ),
            question_name="ordering",
        )
        proposed_ordering = question.by(scenarios).run()
        d = dict(
            proposed_ordering.select("example_question_name", "ordering").to_list()
        )
        self._question_options = [d.get(qn, None) for qn in self.input_data.question_names]


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
