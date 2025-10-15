class QuestionTypeModule:
    def __init__(self, input_data):
        self.input_data = input_data
        self._question_types = None
    
    @property
    def question_types(self):
        if self._question_types is None:
            self.question_types = None
        return self._question_types

    @question_types.setter
    def question_types(self, value):
        if value is None:
            value = [self._infer_question_type(qn) for qn in self.input_data.question_names]
        self._question_types = value

    def _infer_question_type(self, question_name) -> str:
        qt = self.input_data.question_stats.question_statistics(question_name)
        if qt.num_unique_responses > self.input_data.NUM_UNIQUE_THRESHOLD:
            if qt.frac_numerical > self.input_data.FRAC_NUMERICAL_THRESHOLD:
                return "numerical"
            if qt.frac_obs_from_top_5 > self.input_data.MULTIPLE_CHOICE_OTHER_THRESHOLD:
                return "multiple_choice_with_other"
            return "free_text"
        else:
            return "multiple_choice"
