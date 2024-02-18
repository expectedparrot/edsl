from rich.table import Table
from rich.text import Text
from rich.box import SIMPLE


class JobsRunnerStatusMixin:

    def _generate_status_table(self, data, elapsed_time):
        currently_waiting = sum([getattr(interview, "num_tasks_waiting", 0) for interview in self.interviews])
        pct_complete = len(data) / len(self.interviews) * 100
        average_time = elapsed_time / len(data) if len(data) > 0 else 0

        table = Table(show_header=True, header_style="bold magenta", box=SIMPLE)
        table.add_column("Key", style="dim", no_wrap=True)
        table.add_column("Value")

        # Add rows for each key-value pair
        table.add_row(Text("Task status", style = "bold red"), "")
        table.add_row("Total interviews requested", str(len(self.interviews)))
        table.add_row("Completed interviews", str(len(data)))
        table.add_row("Percent complete", f"{pct_complete:.2f}%")
        table.add_row("", "")
        table.add_row(Text("Timing", style = "bold red"), "")
        table.add_row("Elapsed time (seconds)", f"{elapsed_time:.3f}")
        table.add_row("Average time/interview (seconds)", f"{average_time:.3f}")
        table.add_row("", "")
        table.add_row(Text("Queues", style = "bold red"), "")
        table.add_row("Tasks currently waiting", str(currently_waiting))
        table.add_row("", "")
        table.add_row(Text("Usage", style = "bold red"), "")
        table.add_row("Total request tokens","Not implemented")
        table.add_row("Total recevied tokens","Not implemented")
        table.add_row("Total used tokens","Not implemented")
        table.add_row("Total cost", "Not implemented")
        return table
