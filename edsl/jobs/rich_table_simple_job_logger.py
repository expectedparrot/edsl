import time
from datetime import datetime
from typing import Optional
from threading import Lock

try:
    from rich.console import Console
    from rich.spinner import Spinner
    from rich.text import Text
    from rich.live import Live
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .jobs_remote_inference_logger import JobLogger
from .jobs_status_enums import JobsStatus


class RichTableSimpleJobLogger(JobLogger):
    """A simple job logger that displays initialization, progress URL, then streams messages"""
    
    def __init__(self, verbose=True, **kwargs):
        if not RICH_AVAILABLE:
            raise ImportError("Rich package is required for RichTableSimpleJobLogger. Install with: pip install rich")
        
        super().__init__(verbose=verbose)
        self.console = Console()
        self.current_message = ""
        self.current_status = JobsStatus.RUNNING
        self.live_display: Optional[Live] = None
        self.update_lock = Lock()
        self.last_update_time = 0
        self.update_interval = 0.1  # Limit updates to 10 per second
        self.progress_url_shown = False
        self.initialization_shown = False
        
        # Status icons
        self.status_icons = {
            JobsStatus.RUNNING: "⚡",
            JobsStatus.COMPLETED: "✅",
            JobsStatus.PARTIALLY_FAILED: "⚠️",
            JobsStatus.FAILED: "❌",
        }
        
        # Status colors
        self.status_colors = {
            JobsStatus.RUNNING: "blue",
            JobsStatus.COMPLETED: "green",
            JobsStatus.PARTIALLY_FAILED: "yellow",
            JobsStatus.FAILED: "red",
        }
        
        # Print initialization message
        if self.verbose:
            self.console.print("Initializing...")
            self.initialization_shown = True

    def _start_live_display(self):
        """Start the live display"""
        if self.live_display is None:
            self.live_display = Live(
                self._create_display(),
                console=self.console,
                refresh_per_second=10,
                auto_refresh=True
            )
            self.live_display.start()
    
    def _show_progress_url_if_available(self):
        """Show progress URL on separate line if available and not already shown"""
        if (not self.progress_url_shown and 
            hasattr(self.jobs_info, 'progress_bar_url') and 
            self.jobs_info.progress_bar_url):
            self.console.print(f"Progress: {self.jobs_info.progress_bar_url}")
            self.console.print()  # Add blank line before streaming messages
            self.progress_url_shown = True
            # Now start the live display for streaming messages
            self._start_live_display()

    def _stop_live_display(self):
        """Stop the live display"""
        if self.live_display is not None:
            self.live_display.stop()
            self.live_display = None

    def _create_display(self) -> Text:
        """Create the single line display with spinner and message"""
        text = Text()
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        text.append(f"[{timestamp}] ", style="dim")
        
        # Add status indicator
        if self.current_status == JobsStatus.RUNNING:
            # Use a simple rotating spinner for running status
            spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            text.append(f"{spinner_chars[spinner_idx]} ", style="blue")
        else:
            icon = self.status_icons.get(self.current_status, "•")
            color = self.status_colors.get(self.current_status, "white")
            text.append(f"{icon} ", style=color)
        
        # Add completion info if available
        completion_info = ""
        if (hasattr(self.jobs_info, 'completed_interviews') and 
            hasattr(self.jobs_info, 'failed_interviews') and
            self.jobs_info.completed_interviews is not None and
            self.jobs_info.failed_interviews is not None):
            total = self.jobs_info.completed_interviews + self.jobs_info.failed_interviews
            if total > 0:
                completion_info = f" ({self.jobs_info.completed_interviews}/{total})"
        
        # Add current message
        if self.current_message:
            text.append(f"{self.current_message}{completion_info}", style="white")
        else:
            text.append("Starting...", style="dim")
        
        return text

    def update(self, message: str, status: JobsStatus = JobsStatus.RUNNING):
        """Update the display with new message and status"""
        with self.update_lock:
            current_time = time.time()
            
            # Rate limiting to prevent too frequent updates
            if current_time - self.last_update_time < self.update_interval:
                return
                
            self.current_message = message
            self.current_status = status
            
            if self.verbose:
                # Check if we should show progress URL
                self._show_progress_url_if_available()
                
                if self.live_display:
                    try:
                        self.live_display.update(self._create_display())
                    except Exception as e:
                        # Fallback to console print if live display fails
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        icon = self.status_icons.get(status, "•")
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