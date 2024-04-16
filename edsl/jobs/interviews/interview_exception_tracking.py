from rich.console import Console
from rich.table import Table
from collections import UserDict


class InterviewExceptionEntry(UserDict):
    """Class to record an exception that occurred during the interview."""

    def __init__(self, exception, time, traceback):
        data = {"exception": exception, "time": time, "traceback": traceback}
        super().__init__(data)

    def to_dict(self) -> dict:
        """Return the exception as a dictionary."""
        return self.data


class InterviewExceptionCollection(UserDict):
    """A collection of exceptions that occurred during the interview."""

    def add(self, question_name: str, entry: InterviewExceptionEntry) -> None:
        """Add an exception entry to the collection."""
        question_name = question_name
        if question_name not in self.data:
            self.data[question_name] = []
        self.data[question_name].append(entry)

    def to_dict(self, include_traceback=False) -> dict:
        """Return the collection of exceptions as a dictionary."""
        newdata = {k: [e.to_dict() for e in v] for k, v in self.data.items()}
        if not include_traceback:
            for question in newdata:
                for exception in newdata[question]:
                    exception[
                        "traceback"
                    ] = "Traceback removed. Set include_traceback=True to include."
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

    def print(self):
        """Print the collection of exceptions."""
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Question name", style="dim", width=12)
        table.add_column("Exception", width=32)
        table.add_column("Time", justify="right")
        table.add_column("Traceback", min_width=20)

        for queue, exceptions in self.data.items():
            for exception in exceptions:
                table.add_row(
                    queue,
                    exception["exception"],
                    str(exception["time"]),
                    exception["traceback"].replace(
                        "\n", "\n\n"
                    ),  # Adding extra newlines for better readability
                )

        console.print(table)
