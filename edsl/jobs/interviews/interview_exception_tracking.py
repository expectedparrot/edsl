from collections import UserDict

from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry


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
