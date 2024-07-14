from typing import Union, List


class QuestionOptionMixin:
    @property
    def question_options(self):
        if not hasattr(self, "_question_options"):
            self.question_options = None
        return self._question_options

    @question_options.setter
    def question_options(self, value):
        if value is None:
            value = [self._get_question_options(qn) for qn in self.question_names]
        self._question_options = value

    def _get_question_options(self, question_name) -> Union[List[str], None]:
        """Return the options for a question.

        >>> from edsl.conjure.InputData import InputDataABC
        >>> id = InputDataABC.example()
        >>> sorted(id._get_question_options('morning'))
        ['1', '4']

        """
        qt = self.question_statistics(question_name)
        idx = self.question_names.index(question_name)
        question_type = self.question_types[idx]
        if question_type == "multiple_choice":
            return [str(o) for o in qt.unique_responses]
        else:
            if question_type == "multiple_choice_with_other":
                options = self.unique_responses_more_than_k(2)[
                    self.question_names.index(question_name)
                ] + [self.OTHER_STRING]
                return [str(o) for o in options]
            else:
                return None

    def order_options(self) -> None:
        """Order the options for multiple choice questions using an LLM."""
        from edsl import QuestionList, ScenarioList
        import textwrap

        scenarios = (
            ScenarioList.from_list("example_question_name", self.question_names)
            .add_list("example_question_text", self.question_texts)
            .add_list("example_question_type", self.question_types)
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
            If there is not natural order, just put then in order they were presented.
            """
            ),
            question_name="ordering",
        )
        proposed_ordering = question.by(scenarios).run()
        d = dict(
            proposed_ordering.select("example_question_name", "ordering").to_list()
        )
        self._question_options = [d.get(qn, None) for qn in self.question_names]


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
