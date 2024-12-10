class ResponseValidatorFactory:
    def __init__(self, question):
        self.question = question

    @property
    def response_model(self) -> type["BaseModel"]:
        if self.question._response_model is not None:
            return self.question._response_model
        else:
            return self.question.create_response_model()

    @property
    def response_validator(self) -> "ResponseValidatorBase":
        """Return the response validator."""
        params = (
            {
                "response_model": self.question.response_model,
            }
            | {k: getattr(self.question, k) for k in self.validator_parameters}
            | {"exception_to_throw": getattr(self.question, "exception_to_throw", None)}
            | {"override_answer": getattr(self.question, "override_answer", None)}
        )
        return self.question.response_validator_class(**params)

    @property
    def validator_parameters(self) -> list[str]:
        """Return the parameters required for the response validator."""
        return self.question.response_validator_class.required_params
