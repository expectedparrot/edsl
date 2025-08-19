import time
from datetime import datetime
from typing import Union, List, Optional
from dataclasses import dataclass
from threading import Lock

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.columns import Columns
    from rich.align import Align
    from rich.box import ROUNDED

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .jobs_remote_inference_logger import JobLogger
from .jobs_status_enums import JobsStatus


@dataclass
class MessageEntry:
    """A message entry with timestamp and status"""

    text: str
    status: JobsStatus
    timestamp: datetime


class RichTableJobLogger(JobLogger):
    """A job logger that uses Rich to display beautiful terminal output"""

    def __init__(self, verbose=True, **kwargs):
        if not RICH_AVAILABLE:
            raise ImportError(
                "Rich package is required for RichTableJobLogger. Install with: pip install rich"
            )

        super().__init__(verbose=verbose)
        self.console = Console()
        self.messages: List[MessageEntry] = []
        self.current_message = None
        self.live_display = None
        self.update_lock = Lock()
        self.last_update_time = 0
        self.update_interval = 0.1  # Limit updates to 10 per second

        # Status icons and colors
        self.status_config = {
            JobsStatus.RUNNING: {"icon": "⚡", "color": "blue", "style": "bold blue"},
            JobsStatus.COMPLETED: {
                "icon": "✅",
                "color": "green",
                "style": "bold green",
            },
            JobsStatus.PARTIALLY_FAILED: {
                "icon": "⚠️",
                "color": "yellow",
                "style": "bold yellow",
            },
            JobsStatus.FAILED: {"icon": "❌", "color": "red", "style": "bold red"},
        }

        # Spinner for running status
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0

        # Start live display if verbose
        if self.verbose:
            self._start_live_display()

    def _start_live_display(self):
        """Start the live display"""
        if self.live_display is None:
            self.live_display = Live(
                self._create_display(),
                console=self.console,
                refresh_per_second=10,
                vertical_overflow="visible",
            )
            self.live_display.start()

    def _stop_live_display(self):
        """Stop the live display"""
        if self.live_display is not None:
            self.live_display.stop()
            self.live_display = None

    def _get_status_icon(self, status: JobsStatus) -> str:
        """Get the appropriate icon for a job status"""
        if status == JobsStatus.RUNNING:
            spinner = self.spinner_chars[self.spinner_idx]
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            return f"[blue]{spinner}[/blue]"

        config = self.status_config.get(status, {"icon": "•", "color": "white"})
        return config["icon"]

    def _get_status_style(self, status: JobsStatus) -> str:
        """Get the appropriate style for a job status"""
        config = self.status_config.get(status, {"style": "white"})
        return config["style"]

    def _format_url(self, url: str, label: Optional[str] = None) -> str:
        """Format a URL for display as plain text"""
        if not url:
            return ""

        # Return the full URL as plain text for terminal compatibility
        return f"[cyan]{url}[/cyan]"

    def _format_uuid(self, uuid_value: str) -> str:
        """Format a UUID for display"""
        if not uuid_value:
            return ""

        # Show full UUID instead of truncated version
        return f"[dim]{uuid_value}[/dim]"

    def _create_job_info_table(self) -> Table:
        """Create a table with job information"""
        table = Table(
            title="Job Information",
            title_style="bold cyan",
            box=ROUNDED,
            show_header=True,
            header_style="bold blue",
        )

        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Item", style="magenta", no_wrap=True)
        table.add_column("Value", style="green")

        # Group fields by category
        url_fields = []
        uuid_fields = []
        other_fields = []

        for field, _ in self.jobs_info.__annotations__.items():
            if field in [
                "pretty_names",
                "completed_interviews",
                "failed_interviews",
                "exception_summary",
                "model_costs",
            ]:
                continue

            value = getattr(self.jobs_info, field)
            if not value:
                continue

            pretty_name = self.jobs_info.pretty_names.get(
                field, field.replace("_", " ").title()
            )

            if "url" in field.lower():
                url_fields.append((field, pretty_name, value))
            elif "uuid" in field.lower():
                uuid_fields.append((field, pretty_name, value))
            else:
                other_fields.append((field, pretty_name, value))

        # Add URL fields
        for field, pretty_name, value in url_fields:
            label = pretty_name.replace(" URL", "")
            formatted_value = self._format_url(value, label) if value else ""
            table.add_row("Links", label, formatted_value)

        # Add UUID fields
        for field, pretty_name, value in uuid_fields:
            formatted_value = self._format_uuid(value) if value else ""
            table.add_row("Identifiers", pretty_name, formatted_value)

        # Add other fields
        for field, pretty_name, value in other_fields:
            table.add_row("Other", pretty_name, str(value))

        return table

    def _create_status_panel(self, current_status: JobsStatus) -> Panel:
        """Create a status panel"""
        icon = self._get_status_icon(current_status)
        style = self._get_status_style(current_status)

        status_text = current_status.name.replace("_", " ").title()
        if current_status == JobsStatus.PARTIALLY_FAILED:
            status_text = "Partially Failed"

        # Add completion info if available
        completion_info = ""
        if (
            hasattr(self.jobs_info, "completed_interviews")
            and hasattr(self.jobs_info, "failed_interviews")
            and self.jobs_info.completed_interviews is not None
            and self.jobs_info.failed_interviews is not None
        ):
            completion_info = f" ({self.jobs_info.completed_interviews:,} completed, {self.jobs_info.failed_interviews:,} failed)"

        current_msg = ""
        if self.current_message:
            current_msg = f"\n[dim]Current: {self.current_message}[/dim]"

        content = (
            f"{icon} [{style}]{status_text}[/{style}]{completion_info}{current_msg}"
        )

        return Panel(
            Align.center(content),
            title="Status",
            title_align="center",
            border_style=self.status_config.get(current_status, {}).get(
                "color", "white"
            ),
        )

    def _create_messages_panel(self) -> Panel:
        """Create a panel with the most recent message shown one at a time"""
        if not self.messages:
            return Panel(
                "No messages yet", title="Recent Message", border_style="yellow"
            )

        # Show only the most recent message
        msg = self.messages[-1]
        status_style = self._get_status_style(msg.status)
        status_text = msg.status.name.replace("_", " ").title()

        content = f"[{status_style}]{status_text}[/{status_style}] | {msg.timestamp.strftime('%H:%M:%S')} | {msg.text}"

        return Panel(
            Align.center(content), title="Recent Message", border_style="yellow"
        )

    def _create_exceptions_table(self) -> Union[Table, None]:
        """Create a table with exception information"""
        if not self.jobs_info.exception_summary:
            return None

        table = Table(
            title="Exception Summary",
            title_style="bold red",
            box=ROUNDED,
            show_header=True,
            header_style="bold blue",
        )

        table.add_column("Exception Type", style="red")
        table.add_column("Service", style="cyan")
        table.add_column("Model", style="magenta")
        table.add_column("Question", style="yellow")
        table.add_column("Count", style="bold red", justify="right")

        for exc in self.jobs_info.exception_summary:
            table.add_row(
                exc.exception_type or "-",
                exc.inference_service or "-",
                exc.model or "-",
                exc.question_name or "-",
                f"{exc.exception_count:,}",
            )

        return table

    def _create_model_costs_table(self) -> Union[Table, None]:
        """Create a table with model costs information"""
        if not hasattr(self.jobs_info, "model_costs") or not self.jobs_info.model_costs:
            return None

        table = Table(
            title="Model Costs",
            title_style="bold green",
            box=ROUNDED,
            show_header=True,
            header_style="bold blue",
        )

        table.add_column("Service", style="cyan")
        table.add_column("Model", style="magenta")
        table.add_column("Input Tokens", style="yellow", justify="right")
        table.add_column("Input Cost", style="green", justify="right")
        table.add_column("Output Tokens", style="yellow", justify="right")
        table.add_column("Output Cost", style="green", justify="right")
        table.add_column("Total Cost", style="bold green", justify="right")
        table.add_column("Total Credits", style="bold cyan", justify="right")

        total_cost = 0
        total_credits = 0

        for cost in self.jobs_info.model_costs:
            row_total = (cost.input_cost_usd or 0) + (cost.output_cost_usd or 0)
            row_credits = (cost.input_cost_credits_with_cache or 0) + (
                cost.output_cost_credits_with_cache or 0
            )

            total_cost += row_total
            total_credits += row_credits

            table.add_row(
                cost.service or "-",
                cost.model or "-",
                f"{cost.input_tokens:,}" if cost.input_tokens else "-",
                f"${cost.input_cost_usd:.4f}" if cost.input_cost_usd else "-",
                f"{cost.output_tokens:,}" if cost.output_tokens else "-",
                f"${cost.output_cost_usd:.4f}" if cost.output_cost_usd else "-",
                f"${row_total:.4f}",
                f"{row_credits:,.2f}",
            )

        # Add totals row
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            "",
            "",
            f"[bold]${total_cost:.4f}[/bold]",
            f"[bold]{total_credits:,.2f}[/bold]",
        )

        return table

    def _create_display(self) -> Layout:
        """Create the main display layout"""
        layout = Layout()

        # Create main sections
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Header with title and timestamp
        header_text = Text("🦜 EDSL Job Status", style="bold magenta")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header_content = Panel(
            Align.center(f"{header_text}\n[dim]Last updated: {timestamp}[/dim]"),
            style="bright_blue",
        )
        layout["header"].update(header_content)

        # Main content
        current_status = JobsStatus.RUNNING
        if self.messages:
            current_status = self.messages[-1].status

        # Create status panel
        status_panel = self._create_status_panel(current_status)

        # Create info table
        info_table = self._create_job_info_table()

        # Create messages panel
        messages_panel = self._create_messages_panel()

        # Create optional tables
        exceptions_table = self._create_exceptions_table()
        costs_table = self._create_model_costs_table()

        # Organize content
        main_content = []

        # Add status panel
        main_content.append(status_panel)

        # Add info table if it has content
        if info_table.row_count > 0:
            main_content.append(info_table)

        # Add messages panel
        main_content.append(messages_panel)

        # Add exceptions table if it exists
        if exceptions_table:
            main_content.append(exceptions_table)

        # Add costs table if it exists
        if costs_table:
            main_content.append(costs_table)

        # If no content, show a simple message
        if not main_content:
            main_content.append(Panel("No information available yet", style="dim"))

        layout["main"].update(Columns(main_content, equal=False, expand=True))

        # Footer
        footer_content = Panel(
            Align.center("[dim]Use Ctrl+C to stop[/dim]"), style="bright_black"
        )
        layout["footer"].update(footer_content)

        return layout

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and status"""
        with self.update_lock:
            current_time = time.time()

            # Rate limiting
            if current_time - self.last_update_time < self.update_interval:
                return

            self.current_message = message
            self.messages.append(
                MessageEntry(text=message, status=status, timestamp=datetime.now())
            )

            # Keep only last 100 messages to avoid memory issues
            if len(self.messages) > 100:
                self.messages = self.messages[-100:]

            if self.verbose and self.live_display:
                try:
                    self.live_display.update(self._create_display())
                except Exception:
                    # Fallback to console print if live display fails
                    icon = self._get_status_icon(status)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.console.print(f"[{timestamp}] {icon} {message}")

            self.last_update_time = current_time

    def stop(self):
        """Explicitly stop the live display"""
        self._stop_live_display()

    def __del__(self):
        """Cleanup when the logger is destroyed"""
        try:
            self._stop_live_display()
        except (ImportError, AttributeError):
            # Ignore errors during Python shutdown
            pass
