"""
This module contains the ChatTranscript class for displaying conversation results.

The ChatTranscript class provides a rich, formatted view of questions asked to an agent
and their corresponding responses, making it easy to review interview conversations
in a chat-like format.
"""

from typing import TYPE_CHECKING
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

if TYPE_CHECKING:
    from .result import Result


class ChatTranscript:
    """
    A class for displaying Result objects as formatted chat transcripts.
    
    This class takes a Result object and provides methods to display the conversation
    between questions and agent responses in a visually appealing format using the
    Rich library.    
    """
    
    def __init__(self, result: "Result"):
        """
        Initialize the ChatTranscript with a Result object.
        
        Args:
            result: A Result object containing the conversation data
        """
        self.result = result
        self.console = Console()
    
    def view(self, show_options: bool = True, show_agent_info: bool = True) -> None:
        """
        Display the chat transcript in a formatted view.
        
        Args:
            show_options: Whether to display question options if available
            show_agent_info: Whether to show agent information at the top
        """
        self.console.print()  # Add some spacing
        
        if show_agent_info:
            self._display_agent_info()
        
        # Get all questions and answers
        questions_and_answers = self._get_questions_and_answers()
        
        if not questions_and_answers:
            self.console.print("[yellow]No questions found in this result.[/yellow]")
            return
        
        # Display each question-answer pair
        for i, (question_name, question_data, answer) in enumerate(questions_and_answers):
            self._display_question(question_name, question_data, show_options)
            self._display_answer(answer)
            
            # Add spacing between Q&A pairs (except for the last one)
            if i < len(questions_and_answers) - 1:
                self.console.print()
    
    def _display_agent_info(self) -> None:
        """Display agent information at the top of the transcript."""
        agent = self.result.agent
        
        # Create agent info text
        agent_info = Text()
        agent_info.append("Agent: ", style="bold cyan")
        
        if hasattr(agent, 'name') and agent.name:
            agent_info.append(agent.name, style="cyan")
        else:
            agent_info.append("Unnamed Agent", style="dim cyan")
        
        # Add traits if available
        if hasattr(agent, 'traits') and agent.traits:
            agent_info.append("\nTraits: ", style="bold dim")
            traits_text = ", ".join([f"{k}: {v}" for k, v in agent.traits.items()])
            agent_info.append(traits_text, style="dim")
        
        # Add instruction if available
        if hasattr(agent, 'instruction') and agent.instruction:
            agent_info.append(f"\nInstruction: {agent.instruction}", style="italic dim")
        
        panel = Panel(
            agent_info,
            title="[bold blue]Agent Information[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def _get_questions_and_answers(self) -> list:
        """
        Extract questions and answers from the result.
        
        Returns:
            List of tuples containing (question_name, question_data, answer)
        """
        questions_and_answers = []
        
        for question_name, answer in self.result.answer.items():
            question_data = self.result.question_to_attributes.get(question_name, {})
            questions_and_answers.append((question_name, question_data, answer))
        
        return questions_and_answers
    
    def _display_question(self, question_name: str, question_data: dict, show_options: bool) -> None:
        """Display a question with its text and options."""
        question_text = question_data.get('question_text', question_name)
        question_type = question_data.get('question_type', 'unknown')
        question_options = question_data.get('question_options', None)
        
        # Create the main question text
        content = Text()
        content.append(question_text, style="bold white")
        
        # Add question type info
        if question_type != 'unknown':
            content.append(f"\n[{question_type}]", style="dim italic")
        
        # Add options if they exist and should be shown
        if show_options and question_options:
            content.append("\n\nOptions:", style="bold dim")
            if isinstance(question_options, list):
                for i, option in enumerate(question_options, 1):
                    content.append(f"\n  {i}. {option}", style="dim")
            elif isinstance(question_options, dict):
                for key, value in question_options.items():
                    content.append(f"\n  {key}: {value}", style="dim")
            else:
                content.append(f"\n  {question_options}", style="dim")
        
        # Create panel for question
        question_panel = Panel(
            content,
            title=f"[bold green]Question: {question_name}[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(question_panel)
    
    def _display_answer(self, answer) -> None:
        """Display the agent's answer."""
        # Format the answer based on its type
        if isinstance(answer, dict):
            answer_text = self._format_dict_answer(answer)
        elif isinstance(answer, list):
            answer_text = self._format_list_answer(answer)
        else:
            answer_text = str(answer)
        
        # Create panel for answer
        answer_panel = Panel(
            Text(answer_text, style="white"),
            title="[bold yellow]Agent Response[/bold yellow]",
            border_style="yellow",
            padding=(1, 2)
        )
        
        self.console.print(answer_panel)
    
    def _format_dict_answer(self, answer_dict: dict) -> str:
        """Format a dictionary answer for display."""
        formatted_lines = []
        for key, value in answer_dict.items():
            formatted_lines.append(f"{key}: {value}")
        return "\n".join(formatted_lines)
    
    def _format_list_answer(self, answer_list: list) -> str:
        """Format a list answer for display."""
        if not answer_list:
            return "[]"
        
        # If it's a simple list, join with commas
        if all(isinstance(item, (str, int, float, bool)) for item in answer_list):
            return ", ".join(str(item) for item in answer_list)
        else:
            # For complex lists, show each item on a new line
            formatted_lines = []
            for i, item in enumerate(answer_list, 1):
                formatted_lines.append(f"{i}. {item}")
            return "\n".join(formatted_lines)
    
    def summary(self) -> None:
        """Display a brief summary of the conversation."""
        num_questions = len(self.result.answer)
        agent_name = getattr(self.result.agent, 'name', 'Unnamed Agent')
        
        summary_text = Text()
        summary_text.append("Conversation Summary", style="bold magenta")
        summary_text.append(f"\nAgent: {agent_name}", style="cyan")
        summary_text.append(f"\nQuestions answered: {num_questions}", style="green")
        
        if hasattr(self.result, 'model'):
            model_name = getattr(self.result.model, 'model', 'Unknown model')
            summary_text.append(f"\nModel used: {model_name}", style="blue")
        
        panel = Panel(
            summary_text,
            title="[bold magenta]Summary[/bold magenta]",
            border_style="magenta",
            padding=(1, 2)
        )
        
        self.console.print(panel) 