import traceback
import datetime


class InterviewExceptionEntry:
    """Class to record an exception that occurred during the interview."""

    def __init__(
        self,
        *,
        exception: Exception,
        invigilator: "Invigilator",
        traceback_format="text",
        answers=None,
    ):
        self.time = datetime.datetime.now().isoformat()
        self.exception = exception
        # self.failed_question = failed_question
        self.invigilator = invigilator
        self.traceback_format = traceback_format
        self.answers = answers

    @property
    def question_type(self):
        # return self.failed_question.question.question_type
        return self.invigilator.question.question_type

    @property
    def name(self):
        return repr(self.exception)

    @property
    def rendered_prompts(self):
        return self.invigilator.get_prompts()

    @property
    def key_sequence(self):
        return self.invigilator.model.key_sequence

    @property
    def generated_token_string(self):
        # return "POO"
        if self.invigilator.raw_model_response is None:
            return "No raw model response available."
        else:
            return self.invigilator.model.get_generated_token_string(
                self.invigilator.raw_model_response
            )

    @property
    def raw_model_response(self):
        import json

        if self.invigilator.raw_model_response is None:
            return "No raw model response available."
        return json.dumps(self.invigilator.raw_model_response, indent=2)

    def __getitem__(self, key):
        # Support dict-like access obj['a']
        return str(getattr(self, key))

    @classmethod
    def example(cls):
        from edsl import QuestionFreeText
        from edsl.language_models import LanguageModel

        m = LanguageModel.example(test_model=True)
        q = QuestionFreeText.example(exception_to_throw=ValueError)
        results = q.by(m).run(
            skip_retry=True,
            print_exceptions=False,
            raise_validation_errors=True,
            disable_remote_cache=True,
            disable_remote_inference=True,
        )
        return results.task_history.exceptions[0]["how_are_you"][0]

    @property
    def code_to_reproduce(self):
        return self.code(run=False)

    def code(self, run=True):
        lines = []
        lines.append("from edsl import Question, Model, Scenario, Agent")

        lines.append(f"q = {repr(self.invigilator.question)}")
        lines.append(f"scenario = {repr(self.invigilator.scenario)}")
        lines.append(f"agent = {repr(self.invigilator.agent)}")
        lines.append(f"m = Model('{self.invigilator.model.model}')")
        lines.append("results = q.by(m).by(agent).by(scenario).run()")
        code_str = "\n".join(lines)

        if run:
            # Create a new namespace to avoid polluting the global namespace
            namespace = {}
            exec(code_str, namespace)
            return namespace["results"]
        return code_str

    @property
    def traceback(self):
        """Return the exception as HTML."""
        if self.traceback_format == "html":
            return self.html_traceback
        else:
            return self.text_traceback

    @property
    def text_traceback(self):
        """
        >>> entry = InterviewExceptionEntry.example()
        >>> entry.text_traceback
        'Traceback (most recent call last):...'
        """
        e = self.exception
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        return tb_str

    @property
    def html_traceback(self):
        from rich.console import Console
        from rich.table import Table
        from rich.traceback import Traceback

        from io import StringIO

        html_output = StringIO()

        console = Console(file=html_output, record=True)

        tb = Traceback.from_exception(
            type(self.exception),
            self.exception,
            self.exception.__traceback__,
            show_locals=True,
        )
        console.print(tb)
        return html_output.getvalue()

    @staticmethod
    def serialize_exception(exception: Exception) -> dict:
        return {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            ),
        }

    @staticmethod
    def deserialize_exception(data: dict) -> Exception:
        try:
            exception_class = globals()[data["type"]]
        except KeyError:
            exception_class = Exception
        return exception_class(data["message"])

    def to_dict(self) -> dict:
        """Return the exception as a dictionary.

        >>> entry = InterviewExceptionEntry.example()
        >>> _ = entry.to_dict()
        """
        return {
            "exception": self.serialize_exception(self.exception),
            "time": self.time,
            "traceback": self.traceback,
            "invigilator": self.invigilator.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewExceptionEntry":
        """Create an InterviewExceptionEntry from a dictionary."""
        from edsl.agents.Invigilator import InvigilatorAI

        exception = cls.deserialize_exception(data["exception"])
        invigilator = InvigilatorAI.from_dict(data["invigilator"])
        return cls(exception=exception, invigilator=invigilator)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
