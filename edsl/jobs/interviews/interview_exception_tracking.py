import traceback
import datetime
import time
from collections import UserDict

from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry

#                 #traceback=traceback.format_exc(),
#                 #traceback = frame_summary_to_dict(traceback.extract_tb(e.__traceback__))
#                 #traceback = [frame_summary_to_dict(f) for f in traceback.extract_tb(e.__traceback__)]

# class InterviewExceptionEntry:
#     """Class to record an exception that occurred during the interview.
    
#     >>> entry = InterviewExceptionEntry.example()
#     >>> entry.to_dict()['exception']
#     "ValueError('An error occurred.')"
#     """

#     def __init__(self, exception: Exception):
#         self.time = datetime.datetime.now().isoformat()
#         self.exception = exception

#     def __getitem__(self, key):
#         # Support dict-like access obj['a']
#         return str(getattr(self, key))

#     @classmethod
#     def example(cls):
#         try: 
#             raise ValueError("An error occurred.")
#         except Exception as e:
#             entry = InterviewExceptionEntry(e)
#         return entry
    
#     @property
#     def traceback(self):
#         """Return the exception as HTML."""
#         e = self.exception
#         tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
#         return tb_str
    

#     @property
#     def html(self):
#         from rich.console import Console
#         from rich.table import Table
#         from rich.traceback import Traceback

#         from io import StringIO
#         html_output = StringIO()
    
#         console = Console(file=html_output, record=True)
#         tb = Traceback(show_locals=True)
#         console.print(tb)

#         tb = Traceback.from_exception(type(self.exception), self.exception, self.exception.__traceback__, show_locals=True)
#         console.print(tb)
#         return html_output.getvalue()
     
#     def to_dict(self) -> dict:
#         """Return the exception as a dictionary."""
#         return {
#             'exception': repr(self.exception),
#             'time': self.time,
#             'traceback': self.traceback
#         }


class InterviewExceptionCollection(UserDict):
    """A collection of exceptions that occurred during the interview."""

    def add(self, question_name: str, entry: InterviewExceptionEntry) -> None:
        """Add an exception entry to the collection."""
        question_name = question_name
        if question_name not in self.data:
            self.data[question_name] = []
        self.data[question_name].append(entry)

    def to_dict(self, include_traceback=True) -> dict:
        """Return the collection of exceptions as a dictionary."""
        newdata = {k: [e.to_dict() for e in v] for k, v in self.data.items()}
        # if not include_traceback:
        #     for question in newdata:
        #         for exception in newdata[question]:
        #             exception[
        #                 "traceback"
        #             ] = "Traceback removed. Set include_traceback=True to include."
        return newdata

    def _repr_html_(self) -> str:
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict(include_traceback=True))

    def ascii_table(self, traceback: bool = False) -> None:
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

    def print(self, traceback=False):
        """Print the collection of exceptions."""
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Question name", style="dim", width=12)
        table.add_column("Exception", width=32)
        table.add_column("Time", justify="right")
        table.add_column("Traceback", min_width=20)

        for queue, exceptions in self.data.items():
            for exception in exceptions:
                if traceback:
                    traceback_string = exception["traceback"].replace("\n", "\n\n")
                else:
                    traceback_string = ""
                table.add_row(
                    queue,
                    exception["exception"],
                    str(exception["time"]),
                    traceback_string,  # Adding extra newlines for better readability
                )

        console.print(table)



if __name__ == "__main__":
    import doctest 
    doctest.testmod(optionflags=doctest.ELLIPSIS)
