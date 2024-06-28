class QuestionTypeMixin:
    @property
    def question_types(self):
        if not hasattr(self, "_question_types"):
            self.question_types = None
        return self._question_types

    @question_types.setter
    def question_types(self, value):
        if value is None:
            value = [self._infer_question_type(qn) for qn in self.question_names]
        self._question_types = value

    def _infer_question_type(self, question_name) -> str:
        qt = self.question_statistics(question_name)
        if qt.num_unique_responses > self.NUM_UNIQUE_THRESHOLD:
            if qt.frac_numerical > self.FRAC_NUMERICAL_THRESHOLD:
                return "numerical"
            if qt.frac_obs_from_top_5 > self.MULTIPLE_CHOICE_OTHER_THRESHOLD:
                return "multiple_choice_with_other"
            return "free_text"
        else:
            return "multiple_choice"
