from rich.table import Table
from rich.text import Text
from rich.box import SIMPLE

from collections import defaultdict

class JobsRunnerStatusMixin:

    def _generate_status_table(self, data, elapsed_time):
        models_to_tokens = defaultdict
        num_from_cache = 0
        waiting_dict = {}
        for interview in self.interviews:
            model = interview.model
            if model not in models_to_tokens:
                models_to_tokens[model] = interview.token_usage
            else:
                models_to_tokens[model] += interview.token_usage

            num_from_cache += interview.num_from_cache
            if model not in waiting_dict:
                waiting_dict[model] = 0
            waiting_dict[model] += getattr(interview, "num_tasks_waiting", 0)
                
        pct_complete = len(data) / len(self.interviews) * 100
        average_time = elapsed_time / len(data) if len(data) > 0 else 0

        table = Table(title="Job Status", show_header=True, header_style="bold magenta", box=SIMPLE)
        table.add_column("Key", style="dim", no_wrap=True)
        table.add_column("Value")

        # Add rows for each key-value pair
        table.add_row(Text("Task status", style = "bold red"), "")
        table.add_row("Total interviews requested", str(len(self.interviews)))
        table.add_row("Completed interviews", str(len(data)))
        table.add_row("Interviews from cache", str(num_from_cache))
        table.add_row("Percent complete", f"{pct_complete:.2f}%")
        table.add_row("", "")
      
        table.add_row(Text("Timing", style = "bold red"), "")
        table.add_row("Elapsed time (seconds)", f"{elapsed_time:.3f}")
        table.add_row("Average time/interview (seconds)", f"{average_time:.3f}")
        table.add_row("", "")
      
        table.add_row(Text("Model Queues", style = "bold red"), "")
        for model, num_waiting in waiting_dict.items():
            table.add_row(Text(f"{model.model}", style="blue"),"")
            table.add_row(f"-TPM limit (k)", str(model.TPM/1000))
            table.add_row(f"-RPM limit (k)", str(model.RPM/1000))
            table.add_row(f"-Num tasks waiting", str(num_waiting))
            #table.add_row(f"-Tokens", str(models_to_tokens[model].prompt_tokens))
            table.add_row("", "")

        #table.add_row("Tasks currently waiting", str(currently_waiting))


        # table.add_row(Text("Usage", style = "bold red"), "")
        # table.add_row("Total request tokens", str(prompt_tokens))
        # table.add_row("Total recevied tokens", str(completion_tokens))
        # table.add_row("Total used tokens","Not implemented")
        # table.add_row("Total cost", "Not implemented")
        # return table
