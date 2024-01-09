class ValidatorMixin:
    def validate_question_name(self, value):
        if not value:
            raise ValueError("Question name cannot be empty")
        return value
