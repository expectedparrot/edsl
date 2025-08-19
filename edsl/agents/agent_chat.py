from typing import Optional, TYPE_CHECKING
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.rule import Rule
from rich import box
from edsl import QuestionFreeText, Model, Agent, Survey
from edsl.results import Results

if TYPE_CHECKING:
    from ..questions import QuestionBase

console = Console()


class AgentChat:
    def __init__(self, agent: "Agent", model: Optional["Model"] = None):
        self.agent = agent
        if model is None:
            model = Model()
        self.model = model

        self.history = []
        self._questions = []
        self._answers = {}
        self._question_counter = 0
        self.console = Console()

    def send_message(self, message: str) -> str:
        self._question_counter += 1
        question_name = f"question_{self._question_counter}"

        q = QuestionFreeText(question_text=f"{message}", question_name=question_name)

        # Add question to the list
        self._questions.append(q)

        self.agent.instruction = (
            f"This is your conversation history so far: {self.history}"
        )

        # Show spinner while waiting for LLM response
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            progress.add_task("🤖 Thinking...", total=None)
            results = q.by(self.agent).run(verbose=False)

        response = results.select(question_name).first()

        # Store answer in dictionary
        self._answers[question_name] = response

        # Store in history with consistent format
        self.history.append(
            {
                "question": message,
                "response": response,
                "timestamp": datetime.now(),
                "question_name": question_name,
            }
        )
        return response

    def _format_history_for_agent(self) -> str:
        """Format history for agent context"""
        return str(
            [
                {"question": h["question"], "response": h["response"]}
                for h in self.history[-10:]
            ]
        )  # Keep last 10 exchanges

    def display_message(self, message: str, is_user: bool = True):
        """Display a message with rich formatting"""
        if is_user:
            panel = Panel(
                Text(message, style="bold cyan"),
                title="[bold blue]You[/bold blue]",
                title_align="left",
                border_style="blue",
                box=box.ROUNDED,
                padding=(1, 2),
                expand=False,
                width=min(len(message) + 10, 80),
            )
            self.console.print(Align.left(panel))
        else:
            # Try to render as markdown for better formatting
            try:
                content = Markdown(message)
            except (ValueError, TypeError):
                content = Text(message, style="white")

            panel = Panel(
                content,
                title=f"[bold green]{self.agent.name if hasattr(self.agent, 'name') else 'Agent'}[/bold green]",
                title_align="left",
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 2),
                expand=False,
                width=min(80, self.console.width - 4),
            )
            self.console.print(Align.left(panel))

    def display_welcome(self):
        """Display welcome message"""
        welcome_text = Text.from_markup(
            f"[bold cyan]Welcome to Agent Chat![/bold cyan]\n\n"
            f"[dim]Chatting with: {self.agent.name if hasattr(self.agent, 'name') else 'AI Agent'}[/dim]\n"
            f"[dim]Model: {self.model}[/dim]\n"
            f"[dim]Questions asked: {self._question_counter}[/dim]\n\n"
            f"[yellow]Commands:[/yellow]\n"
            f"  • Type your message and press Enter\n"
            f"  • Type [bold]/history[/bold] to view conversation history\n"
            f"  • Type [bold]/clear[/bold] to clear the screen\n"
            f"  • Type [bold]/stats[/bold] to view chat statistics\n"
            f"  • Type [bold]/results[/bold] to convert to EDSL Results object\n"
            f"  • Type [bold]/exit[/bold] or [bold]/quit[/bold] to end the chat\n"
        )

        panel = Panel(
            welcome_text,
            title="[bold magenta]💬 Terminal Chat[/bold magenta]",
            border_style="magenta",
            box=box.DOUBLE,
            padding=(2, 4),
        )

        self.console.print(panel)
        self.console.print()

    def display_history(self):
        """Display conversation history"""
        if not self.history:
            self.console.print("[dim]No conversation history yet.[/dim]")
            return

        self.console.print(Rule("[bold yellow]Conversation History[/bold yellow]"))

        for i, exchange in enumerate(self.history, 1):
            timestamp = exchange["timestamp"].strftime("%H:%M:%S")
            question_name = exchange.get("question_name", f"question_{i}")

            # User message
            self.console.print(
                f"\n[dim]{timestamp} ({question_name})[/dim] [bold blue]You:[/bold blue]"
            )
            self.console.print(f"  {exchange['question']}")

            # Agent response
            self.console.print(
                f"\n[dim]{timestamp}[/dim] [bold green]Agent:[/bold green]"
            )
            self.console.print(f"  {exchange['response']}")

            if i < len(self.history):
                self.console.print(Rule(style="dim"))

    def display_stats(self):
        """Display chat statistics"""
        stats_text = Text.from_markup(
            f"[bold yellow]Chat Statistics[/bold yellow]\n\n"
            f"[cyan]Questions asked:[/cyan] {self._question_counter}\n"
            f"[cyan]Total exchanges:[/cyan] {len(self.history)}\n"
            f"[cyan]Questions logged:[/cyan] {len(self._questions)}\n"
            f"[cyan]Answers stored:[/cyan] {len(self._answers)}\n"
        )

        panel = Panel(
            stats_text,
            title="[bold yellow]📊 Statistics[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        )

        self.console.print(panel)

    def clear_history(self):
        """Clear conversation history and reset counters"""
        self.history = []
        self._questions = []
        self._answers = {}
        self._question_counter = 0
        self.console.print("[bold green]✓[/bold green] History cleared!")

    def to_results(self) -> Results:
        """Convert the chat questions and answers to an EDSL Results object"""
        if not self._questions or not self._answers:
            raise ValueError(
                "No questions or answers available. Run some chat interactions first."
            )

        # Create an agent with direct question answering method
        chat_agent = Agent(name="ChatAgent")

        def construct_answer_dict_function(answers_dict: dict):
            def func(self, question: "QuestionBase", scenario=None):
                return answers_dict.get(question.question_name, None)

            return func

        # Add the direct question answering method with our stored answers
        chat_agent.add_direct_question_answering_method(
            construct_answer_dict_function(self._answers)
        )

        # Create a survey from our questions
        survey = Survey(questions=self._questions)

        # Run the survey with our agent to get Results
        results = survey.by(chat_agent).run(disable_remote_inference=True)

        # Remove the direct question answering method to clean up
        chat_agent.remove_direct_question_answering_method()

        return results

    def run(self):
        """Run the interactive chat session and return EDSL Results object when finished"""
        self.console.clear()
        self.display_welcome()

        try:
            while True:
                # Get user input with styled prompt
                user_input = Prompt.ask(
                    "\n[bold blue]You[/bold blue]", console=self.console
                )

                # Handle commands
                if user_input.lower() in ["/exit", "/quit"]:
                    self.console.print("\n[bold red]Goodbye![/bold red] 👋")
                    break
                elif user_input.lower() == "/clear":
                    self.console.clear()
                    self.display_welcome()
                    continue
                elif user_input.lower() == "/history":
                    self.display_history()
                    continue
                elif user_input.lower() == "/stats":
                    self.display_stats()
                    continue
                elif user_input.lower() == "/reset":
                    self.clear_history()
                    continue
                elif user_input.lower() == "/results":
                    try:
                        results = self.to_results()
                        self.console.print(
                            f"[bold green]✓[/bold green] Successfully converted to Results object with {len(results)} responses"
                        )
                        self.console.print("[dim]Access via: chat.to_results()[/dim]")
                    except ValueError as e:
                        self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
                    continue
                elif not user_input.strip():
                    continue

                # Display user message
                self.console.print()
                self.display_message(user_input, is_user=True)

                # Get and display agent response
                self.console.print()
                response = self.send_message(user_input)
                self.display_message(response, is_user=False)

        except KeyboardInterrupt:
            self.console.print("\n\n[bold red]Chat interrupted![/bold red] 👋")
        except Exception as e:
            self.console.print(f"\n[bold red]Error:[/bold red] {str(e)}")

        # Return the Results object when chat ends
        if self._questions and self._answers:
            return self.to_results()
        else:
            # Return empty Results if no conversation occurred
            return Results([])

    def __repr__(self) -> str:
        return f"AgentChat(agent={self.agent}, model={self.model}, questions={self._question_counter})"

    def __str__(self) -> str:
        return f"AgentChat(agent={self.agent}, model={self.model}, questions={self._question_counter})"


# Example usage
if __name__ == "__main__":
    # Create your agent
    agent = Agent(name="Assistant")

    # Create and run the chat
    chat = AgentChat(agent)
    chat_results = chat.run()  # Returns Results object directly

    # Now you can use all EDSL Results methods on the chat data
    if len(chat_results) > 0:
        print(f"\nChat session ended with {len(chat_results)} responses")
        print(f"Results columns: {chat_results.columns}")

        # Access the raw data if needed
        questions = chat._questions
        answers = chat._answers

        print(f"\nQuestions asked: {len(questions)}")
        for i, question in enumerate(questions, 1):
            print(f"  {i}. {question.question_text}")

        # Use EDSL Results methods
        print("\nAnswers:")
        print(chat_results.select("answer").print())
