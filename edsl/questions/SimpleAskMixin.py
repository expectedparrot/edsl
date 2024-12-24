import math


def logprob_to_prob(logprob):
    if logprob is None:
        return None
    return math.exp(logprob)


def format_output(data):
    from rich.table import Table
    from rich.console import Console

    content = data["choices"][0]["logprobs"]["content"]
    table = Table(show_header=True, header_style="bold magenta")

    # First pass to determine the maximum number of top tokens
    max_tokens = max(len(item["top_logprobs"]) for item in content)

    # Set up the table columns
    table.add_column("Token", style="bold")
    for i in range(max_tokens):
        table.add_column(f"Top Token {i+1}")

    for item in content:
        token = item["token"].strip()
        top_tokens = [
            (top["token"].strip(), logprob_to_prob(top.get("logprob")))
            for top in item["top_logprobs"]
        ]

        # Row data starts with the main token
        row = [token]

        # Add each top token with coloring based on probability
        for token, probability in top_tokens:
            if probability is not None:
                # Assign color based on probability value
                if probability > 0.5:
                    color = "green"
                elif probability > 0.2:
                    color = "yellow"
                else:
                    color = "red"
                formatted_token = f"[{color}]{token} ({probability:.2f})[/]"
            else:
                formatted_token = f"{token} (N/A)"
            row.append(formatted_token)

        # Ensure row has enough columns
        while len(row) < max_tokens + 1:
            row.append("")

        table.add_row(*row)

    console = Console()
    console.print(table)


class SimpleAskMixin:
    # def simple_ask(self, question: QuestionBase, system_prompt = "You are a helpful agent pretending to be a human.", top_logprobs = 2):

    def simple_ask(
        self,
        model=None,
        system_prompt="You are a helpful agent pretending to be a human. Do not break character",
        top_logprobs=4,
    ):
        from edsl.language_models.model import Model

        if model is None:
            model = Model()
        response = model.simple_ask(self, system_prompt, top_logprobs)
        return format_output(response)
