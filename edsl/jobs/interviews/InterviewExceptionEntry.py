import traceback
import datetime
import time
from collections import UserDict
from edsl.jobs.FailedQuestion import FailedQuestion


class InterviewExceptionEntry:
    """Class to record an exception that occurred during the interview.

    >>> entry = InterviewExceptionEntry.example()
    >>> entry.to_dict()['exception']
    "ValueError('An error occurred.')"
    """

    def __init__(
        self,
        *,
        exception: Exception,
        failed_question: FailedQuestion,
        invigilator: "Invigilator",
        traceback_format="html",
    ):
        self.time = datetime.datetime.now().isoformat()
        self.exception = exception
        self.failed_question = failed_question
        self.invigilator = invigilator
        self.traceback_format = traceback_format

    def __getitem__(self, key):
        # Support dict-like access obj['a']
        return str(getattr(self, key))

    @classmethod
    def example(cls):
        try:
            raise ValueError("An error occurred.")
        except Exception as e:
            entry = InterviewExceptionEntry(e)
        return entry

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

    def to_dict(self) -> dict:
        """Return the exception as a dictionary.

        >>> entry = InterviewExceptionEntry.example()
        >>> entry.to_dict()['exception']
        "ValueError('An error occurred.')"

        """
        return {
            "exception": repr(self.exception),
            "time": self.time,
            "traceback": self.traceback,
        }

    def push(self):
        from edsl import Coop

        coop = Coop()
        results = coop.error_create(self.to_dict())
        return results


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
