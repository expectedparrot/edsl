from ..base import EndOfSurvey
from . import DAG
from ..exceptions import SurveyError, SurveyPipingReferenceError


class ConstructDAG:
    def __init__(self, survey):
        self.survey = survey
        self.questions = survey.questions

        self.parameters_by_question = self.survey.parameters_by_question
        self.question_name_to_index = self.survey.question_name_to_index

    def dag(self, textify: bool = False) -> DAG:
        memory_dag = self.survey.memory_plan.dag
        rule_dag = self.survey.rule_collection.dag
        piping_dag = self.piping_dag
        if textify:
            memory_dag = DAG(self.textify(memory_dag))
            rule_dag = DAG(self.textify(rule_dag))
            piping_dag = DAG(self.textify(piping_dag))
        return memory_dag + rule_dag + piping_dag

    @property
    def piping_dag(self) -> DAG:
        """Figures out the DAG of piping dependencies.

        >>> from edsl import Survey
        >>> from edsl import QuestionFreeText
        >>> q0 = QuestionFreeText(question_text="Here is a question", question_name="q0")
        >>> q1 = QuestionFreeText(question_text="You previously answered {{ q0 }}---how do you feel now?", question_name="q1")
        >>> s = Survey([q0, q1])
        >>> ConstructDAG(s).piping_dag
        {1: {0}}
        """
        d = {}
        forward_references = []

        for question_name, depenencies in self.parameters_by_question.items():
            if depenencies:
                question_index = self.question_name_to_index[question_name]
                for dependency in depenencies:
                    if dependency not in self.question_name_to_index:
                        pass
                    else:
                        dependency_index = self.question_name_to_index[dependency]

                        # Check for forward reference: question depends on a later question
                        if question_index < dependency_index:
                            forward_references.append(
                                {
                                    "question": question_name,
                                    "question_index": question_index,
                                    "depends_on": dependency,
                                    "depends_on_index": dependency_index,
                                }
                            )

                        if question_index not in d:
                            d[question_index] = set()
                        d[question_index].add(dependency_index)

        # Raise error if forward references detected
        if forward_references:
            error_details = []
            for ref in forward_references:
                error_details.append(
                    f"Question '{ref['question']}' (index {ref['question_index']}) "
                    f"references '{ref['depends_on']}' (index {ref['depends_on_index']}), "
                    f"which comes later in the survey"
                )
            error_message = (
                "Survey has invalid question ordering with forward piping references:\n"
                + "\n".join(f"  - {detail}" for detail in error_details)
                + "\n\nQuestions can only reference answers from questions that appear earlier in the survey."
            )
            raise SurveyPipingReferenceError(error_message)

        return d

    def textify(self, index_dag: DAG) -> DAG:
        """Convert the DAG of question indices to a DAG of question names.

        :param index_dag: The DAG of question indices.

        Example:

        >>> from edsl import Survey
        >>> s = Survey.example()
        >>> d = s.dag()
        >>> d
        {1: {0}, 2: {0}}
        >>> ConstructDAG(s).textify(d)
        {'q1': {'q0'}, 'q2': {'q0'}}
        """

        def get_name(index: int):
            """Return the name of the question given the index."""
            if index >= len(self.questions):
                return EndOfSurvey
            try:
                return self.questions[index].question_name
            except IndexError:
                print(
                    f"The index is {index} but the length of the questions is {len(self.questions)}"
                )
                raise SurveyError

        try:
            text_dag = {}
            for child_index, parent_indices in index_dag.items():
                parent_names = {get_name(index) for index in parent_indices}
                child_name = get_name(child_index)
                text_dag[child_name] = parent_names
            return text_dag
        except IndexError:
            raise


if __name__ == "__main__":
    import doctest

    doctest.testmod()
