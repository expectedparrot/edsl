import datetime
import json
import traceback
from collections import UserDict

from ..invigilators import InvigilatorBase


class InterviewExceptionEntry:
    """Class to record an exception that occurred during the interview."""

    def __init__(
        self,
        *,
        exception: Exception,
        invigilator: "InvigilatorBase",
        traceback_format="text",
        answers=None,
    ):
        self.time = datetime.datetime.now().isoformat()
        self.exception = exception
        self.invigilator = invigilator
        self.traceback_format = traceback_format
        self.answers = answers

    @property
    def question_type(self) -> str:
        """Return the type of the question that failed."""
        return self.invigilator.question.question_type

    @property
    def name(self) -> str:
        """Return the name of the exception."""
        return repr(self.exception)

    @property
    def rendered_prompts(self) -> str:
        """Return the rendered prompts."""
        return self.invigilator.get_prompts()

    @property
    def key_sequence(self) -> tuple[str, ...]:
        """Return the key sequence."""
        return self.invigilator.model.key_sequence

    @property
    def generated_token_string(self) -> str:
        """Return the generated token string."""
        if self.invigilator.raw_model_response is None:
            return "No raw model response available."
        else:
            return self.invigilator.model.get_generated_token_string(
                self.invigilator.raw_model_response
            )

    @property
    def raw_model_response(self) -> dict:
        """Return the raw model response."""
        if self.invigilator.raw_model_response is None:
            return "No raw model response available."
        return json.dumps(self.invigilator.raw_model_response, indent=2)

    def __getitem__(self, key):
        # Support dict-like access obj['a']
        return str(getattr(self, key))

    @classmethod
    def example(cls):
        """Return an example InterviewExceptionEntry.

        >>> entry = InterviewExceptionEntry.example()
        """
        from ..language_models import LanguageModel
        from ..questions import QuestionFreeText

        m = LanguageModel.example(test_model=True)
        q = QuestionFreeText.example(exception_to_throw=ValueError)
        results = q.by(m).run(
            skip_retry=True,
            print_exceptions=False,
            raise_validation_errors=True,
            disable_remote_cache=True,
            disable_remote_inference=True,
            cache=False,
        )
        return results.task_history.exceptions[0]["how_are_you"][0]

    @property
    def code_to_reproduce(self):
        """Return the code to reproduce the exception."""
        return self.code(run=False)

    def code(self, run=True):
        """Return the code to reproduce the exception."""
        lines = []
        lines.append("from edsl import Question, Model, Scenario, Agent")

        lines.append(f"q = {repr(self.invigilator.question)}")
        lines.append(f"scenario = {repr(self.invigilator.scenario)}")
        lines.append(f"agent = {repr(self.invigilator.agent)}")
        lines.append(f"model = {repr(self.invigilator.model)}")
        lines.append("results = q.by(model).by(agent).by(scenario).run()")
        code_str = "\n".join(lines)

        if run:
            # Create a new namespace to avoid polluting the global namespace
            namespace = {}
            exec(code_str, namespace)
            return namespace["results"]
        return code_str

    @property
    def traceback(self) -> str:
        """Return the exception as HTML."""
        if self.traceback_format == "html":
            return self.html_traceback
        else:
            return self.text_traceback

    @property
    def text_traceback(self) -> str:
        """
        >>> entry = InterviewExceptionEntry.example()
        >>> entry.text_traceback
        'Traceback (most recent call last):...'
        """
        e = self.exception
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        return tb_str

    @property
    def html_traceback(self) -> str:
        from io import StringIO

        from rich.console import Console
        from rich.traceback import Traceback

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
        """Serialize an exception to a dictionary.

        >>> entry = InterviewExceptionEntry.example()
        >>> _ = entry.serialize_exception(entry.exception)
        """
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
        """Deserialize an exception from a dictionary.

        >>> entry = InterviewExceptionEntry.example()
        >>> _ = entry.deserialize_exception(entry.to_dict()["exception"])
        """
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
        from ..questions.exceptions import QuestionAnswerValidationError

        invigilator = (
            self.invigilator.to_dict() if self.invigilator is not None else None
        )
        d = {
            "exception": self.serialize_exception(self.exception),
            "time": self.time,
            "traceback": self.traceback,
            "invigilator": invigilator,
            "additional_data": {},
        }

        if isinstance(self.exception, QuestionAnswerValidationError):
            d["additional_data"]["edsl_response"] = json.dumps(self.exception.data)
            d["additional_data"]["validating_model"] = json.dumps(
                self.exception.model.model_json_schema()
            )
            d["additional_data"]["error_message"] = str(self.exception.message)

        return d

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewExceptionEntry":
        """Create an InterviewExceptionEntry from a dictionary."""
        from ..invigilators import InvigilatorAI

        exception = cls.deserialize_exception(data["exception"])
        if data["invigilator"] is None:
            invigilator = None
        else:
            invigilator = InvigilatorAI.from_dict(data["invigilator"])
        return cls(exception=exception, invigilator=invigilator)


class InterviewExceptionCollection(UserDict):
    """A collection of exceptions that occurred during the interview."""

    def __init__(self):
        """Initialize the InterviewExceptionCollection."""
        super().__init__()
        self.fixed = set()

    def unfixed_exceptions(self) -> list:
        """Return a list of unfixed exceptions."""
        return {k: v for k, v in self.data.items() if k not in self.fixed}

    def num_exceptions(self) -> int:
        """Return the total number of exceptions."""
        return sum(len(v) for v in self.data.values())

    def num_unfixed_exceptions(self) -> int:
        """Return the number of unfixed exceptions."""
        return sum(len(v) for v in self.unfixed_exceptions().values())

    def num_unfixed(self) -> int:
        """Return a list of unfixed questions."""
        return len([k for k in self.data.keys() if k not in self.fixed])

    def record_fixed_question(self, question_name: str) -> None:
        """Record that a question has been fixed."""
        self.fixed.add(question_name)

    def add(self, question_name: str, entry: InterviewExceptionEntry) -> None:
        """Add an exception entry to the collection."""
        question_name = question_name
        if question_name not in self.data:
            self.data[question_name] = []
        self.data[question_name].append(entry)

    def to_dict(self, include_traceback=True) -> dict:
        """Return the collection of exceptions as a dictionary."""
        newdata = {k: [e.to_dict() for e in v] for k, v in self.data.items()}
        return newdata

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewExceptionCollection":
        """Create an InterviewExceptionCollection from a dictionary."""
        collection = cls()
        for question_name, entries in data.items():
            for entry in entries:
                collection.add(question_name, InterviewExceptionEntry.from_dict(entry))
        return collection

    def _repr_html_(self) -> str:
        from ..utilities.utilities import data_to_html

        return data_to_html(self.to_dict(include_traceback=True))

    def ascii_table(self, traceback: bool = False) -> None:
        """Print the collection of exceptions as an ASCII table."""
        headers = ["Question name", "Exception", "Time", "Traceback"]
        from tabulate import tabulate

        data = []
        for question, exceptions in self.data.items():
            for exception in exceptions:
                if traceback:
                    row = [
                        question,
                        exception["exception"],
                        exception["time"],
                        exception["traceback"],
                    ]
                else:
                    row = [question, exception["exception"], exception["time"]]
                data.append(row)

        print(tabulate(data, headers=headers, tablefmt="grid"))


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
