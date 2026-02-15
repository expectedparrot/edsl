"""
Visualization module for EDSL Job Execution System.

Provides terminal-based visualization of job progress, task states,
and queue depths.
"""

from datetime import datetime
from typing import Any, TYPE_CHECKING

from .models import TaskStatus
from .storage import StorageProtocol
from .stores import JobStore, InterviewStore, TaskStore
from .queues import QueueRegistry

if TYPE_CHECKING:
    from .coordinator import ExecutionCoordinator


# ANSI color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


# Unicode characters for visualization
class Symbols:
    DOT_FILLED = "●"
    DOT_EMPTY = "○"
    DOT_HALF = "◐"
    BRACKET_LEFT = "["
    BRACKET_RIGHT = "]"
    ARROW = "→"
    QUEUE = "▸"


def colored_dot(status: TaskStatus) -> str:
    """Return a colored dot based on task status."""
    if status == TaskStatus.COMPLETED:
        return f"{Colors.GREEN}{Symbols.DOT_FILLED}{Colors.RESET}"
    elif status == TaskStatus.FAILED:
        return f"{Colors.RED}{Symbols.DOT_FILLED}{Colors.RESET}"
    elif status == TaskStatus.SKIPPED:
        return f"{Colors.GRAY}{Symbols.DOT_EMPTY}{Colors.RESET}"
    elif status == TaskStatus.RUNNING:
        # Actively waiting on LLM response - blue
        return f"{Colors.BLUE}{Symbols.DOT_HALF}{Colors.RESET}"
    elif status in (TaskStatus.RENDERING, TaskStatus.QUEUED):
        # In queue or being rendered - magenta
        return f"{Colors.MAGENTA}{Symbols.DOT_HALF}{Colors.RESET}"
    else:  # PENDING, READY, BLOCKED
        return f"{Colors.YELLOW}{Symbols.DOT_FILLED}{Colors.RESET}"


def format_timestamp(ts: float | datetime | None) -> str:
    """Format a timestamp for display."""
    if ts is None:
        return "unknown"
    if isinstance(ts, datetime):
        return ts.strftime("%H:%M:%S")
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class JobVisualizer:
    """Visualizes job progress and queue state."""

    def __init__(
        self,
        storage: StorageProtocol,
        registry: QueueRegistry | None = None,
        coordinator: "ExecutionCoordinator | None" = None,
    ):
        self._storage = storage
        self._registry = registry
        self._coordinator = coordinator
        self._jobs = JobStore(storage)
        self._interviews = InterviewStore(storage)
        self._tasks = TaskStore(storage)

    def render_job(self, job_id: str, show_details: bool = False) -> str:
        """Render a single job's status as a string."""
        lines = []

        # Get job definition
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return f"Job {job_id[:8]}... not found"

        # Job header
        timestamp = format_timestamp(job_def.created_at)
        lines.append(
            f"{Colors.BOLD}Job {job_id[:8]}...{Colors.RESET} "
            f"{Colors.GRAY}({timestamp}){Colors.RESET}"
        )

        # Get all interviews for this job
        interview_ids = job_def.interview_ids

        # Build interview visualizations
        interview_lines = []
        stats = {
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "queued": 0,
            "in_flight": 0,
            "skipped": 0,
        }

        for interview_id in interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            # Get task statuses for this interview
            task_dots = []
            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                task_dots.append(colored_dot(status))

                # Count stats
                if status == TaskStatus.COMPLETED:
                    stats["completed"] += 1
                elif status == TaskStatus.FAILED:
                    stats["failed"] += 1
                elif status == TaskStatus.SKIPPED:
                    stats["skipped"] += 1
                elif status == TaskStatus.RUNNING:
                    stats["in_flight"] += 1
                elif status in (TaskStatus.RENDERING, TaskStatus.QUEUED):
                    stats["queued"] += 1
                else:
                    stats["pending"] += 1

            # Format as [●●●] for this interview
            interview_str = (
                f"{Symbols.BRACKET_LEFT}{''.join(task_dots)}{Symbols.BRACKET_RIGHT}"
            )
            interview_lines.append(interview_str)

        # Show interviews (wrap if too many)
        max_per_line = 10
        for i in range(0, len(interview_lines), max_per_line):
            chunk = interview_lines[i : i + max_per_line]
            lines.append("  " + " ".join(chunk))

        # Stats summary
        total = sum(stats.values())
        stats_line = (
            f"  {Colors.GREEN}✓{stats['completed']}{Colors.RESET} "
            f"{Colors.YELLOW}○{stats['pending']}{Colors.RESET} "
            f"{Colors.MAGENTA}◐{stats['queued']}{Colors.RESET} "
            f"{Colors.BLUE}◐{stats['in_flight']}{Colors.RESET} "
            f"{Colors.RED}✗{stats['failed']}{Colors.RESET} "
            f"{Colors.GRAY}⊘{stats['skipped']}{Colors.RESET} "
            f"/ {total} tasks"
        )
        lines.append(stats_line)

        if show_details:
            lines.append("")
            lines.append(self._render_task_details(job_id))

        return "\n".join(lines)

    def render_job_compact(
        self, job_id: str, max_rows: int = 6, max_per_line: int = 8
    ) -> str:
        """
        Render a compact job status suitable for Rich Live updates.

        Shows interview dots (colored by task status) but truncated to max_rows.
        This keeps the display height bounded for proper in-place updates.

        Args:
            max_rows: Maximum number of interview rows to show (default 6).
            max_per_line: Maximum interviews per line (default 8 to avoid wrapping).
        """
        lines = []

        # Get job definition
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return f"Job {job_id[:8]}... not found"

        # Job header
        timestamp = format_timestamp(job_def.created_at)
        lines.append(
            f"{Colors.BOLD}Job {job_id[:8]}...{Colors.RESET} "
            f"{Colors.GRAY}({timestamp}){Colors.RESET}"
        )

        # Get all interviews for this job
        interview_ids = job_def.interview_ids

        # Build interview visualizations
        interview_lines = []
        stats = {
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "queued": 0,
            "in_flight": 0,
            "skipped": 0,
        }

        for interview_id in interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            # Get task statuses for this interview
            task_dots = []
            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                task_dots.append(colored_dot(status))

                # Count stats
                if status == TaskStatus.COMPLETED:
                    stats["completed"] += 1
                elif status == TaskStatus.FAILED:
                    stats["failed"] += 1
                elif status == TaskStatus.SKIPPED:
                    stats["skipped"] += 1
                elif status == TaskStatus.RUNNING:
                    stats["in_flight"] += 1
                elif status in (TaskStatus.RENDERING, TaskStatus.QUEUED):
                    stats["queued"] += 1
                else:
                    stats["pending"] += 1

            # Format as [●●●] for this interview
            interview_str = (
                f"{Symbols.BRACKET_LEFT}{''.join(task_dots)}{Symbols.BRACKET_RIGHT}"
            )
            interview_lines.append(interview_str)

        # Show interviews (wrap if too many, but cap at max_rows)
        total_interviews = len(interview_lines)
        max_interviews_to_show = max_rows * max_per_line

        for i in range(
            0, min(len(interview_lines), max_interviews_to_show), max_per_line
        ):
            chunk = interview_lines[i : i + max_per_line]
            lines.append("  " + " ".join(chunk))

        # Show "+N more" if truncated
        if total_interviews > max_interviews_to_show:
            remaining = total_interviews - max_interviews_to_show
            lines.append(
                f"  {Colors.GRAY}... +{remaining} more interviews{Colors.RESET}"
            )

        # Stats summary
        total = sum(stats.values())
        stats_line = (
            f"  {Colors.GREEN}✓{stats['completed']}{Colors.RESET} "
            f"{Colors.YELLOW}○{stats['pending']}{Colors.RESET} "
            f"{Colors.MAGENTA}◐{stats['queued']}{Colors.RESET} "
            f"{Colors.BLUE}◐{stats['in_flight']}{Colors.RESET} "
            f"{Colors.RED}✗{stats['failed']}{Colors.RESET} "
            f"{Colors.GRAY}⊘{stats['skipped']}{Colors.RESET} "
            f"/ {total} tasks"
        )
        lines.append(stats_line)

        # Legend
        legend = (
            f"  {Colors.GRAY}Legend: "
            f"{Colors.GREEN}✓{Colors.GRAY}=done "
            f"{Colors.YELLOW}○{Colors.GRAY}=pending "
            f"{Colors.MAGENTA}◐{Colors.GRAY}=queued "
            f"{Colors.BLUE}◐{Colors.GRAY}=in-flight "
            f"{Colors.RED}✗{Colors.GRAY}=failed "
            f"⊘=skipped{Colors.RESET}"
        )
        lines.append(legend)

        # Error breakdown if there are failures
        if stats["failed"] > 0:
            error_counts = self._get_error_counts(job_id)
            if error_counts:
                error_parts = [
                    f"{k}:{v}"
                    for k, v in sorted(error_counts.items(), key=lambda x: -x[1])
                ]
                lines.append(
                    f"  {Colors.RED}Errors: {', '.join(error_parts)}{Colors.RESET}"
                )

        return "\n".join(lines)

    def _get_error_counts(self, job_id: str) -> dict[str, int]:
        """Get counts of errors by type for a job."""
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return {}

        error_counts: dict[str, int] = {}

        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                if status == TaskStatus.FAILED:
                    state = self._tasks.get_state(task_id)
                    error_type = state.last_error_type or "unknown"
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return error_counts

    def _render_task_details(self, job_id: str) -> str:
        """Render detailed task information."""
        lines = [f"  {Colors.BOLD}Task Details:{Colors.RESET}"]

        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return ""

        for interview_id in job_def.interview_ids[:5]:  # Limit to first 5
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            lines.append(f"    Interview {interview_id[:8]}...:")
            for task_id in interview_def.task_ids:
                task_def = self._tasks.get_definition(job_id, interview_id, task_id)
                status = self._tasks.get_status(task_id)
                dot = colored_dot(status)
                q_name = task_def.question_name if task_def else "?"
                lines.append(f"      {dot} {task_id[:8]}... ({q_name}): {status.value}")

        if len(job_def.interview_ids) > 5:
            lines.append(
                f"    ... and {len(job_def.interview_ids) - 5} more interviews"
            )

        return "\n".join(lines)

    def render_queues(self, max_lines: int | None = None) -> str:
        """Render queue status.

        Args:
            max_lines: Maximum number of queue lines to show. None means no limit.
        """
        if self._registry is None:
            return "No queue registry available"

        lines = [f"{Colors.BOLD}Active Queues:{Colors.RESET}"]

        queues = self._registry.list_queues()
        active_queues = []

        for q_meta in queues:
            queue = self._registry.get_queue(q_meta.queue_id)
            if queue.depth > 0:
                active_queues.append((q_meta, queue))

        if not active_queues:
            lines.append(f"  {Colors.GRAY}(no tasks queued){Colors.RESET}")
            return "\n".join(lines)

        # Sort by service/model for stable order (not by depth)
        active_queues.sort(key=lambda x: (x[0].service, x[0].model))

        # Limit number of queues shown if specified
        display_queues = active_queues[:max_lines] if max_lines else active_queues
        remaining = len(active_queues) - len(display_queues)

        # Calculate max name length for alignment
        max_name_len = max(
            len(f"{q.service}/{q.model[:20]}") for q, _ in display_queues
        )

        for q_meta, queue in display_queues:
            # Check if queue is available for immediate execution
            task = queue.peek()
            estimated_tokens = task.get("estimated_tokens", 500) if task else 500
            is_available = queue.time_until_available(estimated_tokens) == 0

            # Create dots for tasks in queue (show up to 50)
            max_dots = 50
            depth = queue.depth
            dots = f"{Colors.CYAN}{Symbols.DOT_FILLED}{Colors.RESET}" * min(
                depth, max_dots
            )
            if depth > max_dots:
                dots += f" +{depth - max_dots}"

            # Color queue name green if available, gray otherwise
            name_color = Colors.GREEN if is_available else Colors.GRAY
            name = f"{q_meta.service}/{q_meta.model[:20]}"
            padded_name = name.ljust(max_name_len)

            # Format: ▸ service/model [●●●●●] (depth)
            lines.append(
                f"  {Symbols.QUEUE} {name_color}{padded_name}{Colors.RESET}"
                f" {Symbols.BRACKET_LEFT}{dots}{Symbols.BRACKET_RIGHT}"
                f" {Colors.GRAY}({depth}){Colors.RESET}"
            )

        if remaining > 0:
            lines.append(
                f"  {Colors.GRAY}... and {remaining} more queues{Colors.RESET}"
            )

        return "\n".join(lines)

    def render_queues_compact(
        self, max_lines: int = 10, bar_width: int = 40, total_tasks: int = 0
    ) -> str:
        """
        Render a compact queue status with fixed height for Rich Live updates.

        Shows two bars per queue:
        - Magenta: tasks waiting in queue
        - Blue: tasks in-flight (waiting on LLM)

        Args:
            max_lines: Maximum number of queue lines to show.
            bar_width: Width of the progress bar in characters.
            total_tasks: Total tasks in job, used for dynamic scaling.
        """
        if self._registry is None:
            return "No queue registry available"

        lines = [f"{Colors.BOLD}Active Queues:{Colors.RESET}"]

        queues = self._registry.list_queues()
        active_queues = []
        total_queued = 0
        total_in_flight = 0

        # Get in-flight counts per queue from coordinator
        in_flight_by_queue: dict[str, int] = {}
        if self._coordinator is not None:
            in_flight_by_queue = self._coordinator.get_in_flight_by_queue()

        for q_meta in queues:
            queue = self._registry.get_queue(q_meta.queue_id)
            in_flight = in_flight_by_queue.get(q_meta.queue_id, 0)
            # Show queues that have tasks OR have been used (processed requests)
            stats = queue.get_throughput_stats()
            if queue.depth > 0 or in_flight > 0 or stats["request_count"] > 0:
                active_queues.append((q_meta, queue, in_flight))
                total_queued += queue.depth
                total_in_flight += in_flight

        if not active_queues:
            lines.append(f"  {Colors.GRAY}(no active queues){Colors.RESET}")
            # Pad to fixed height
            while len(lines) < max_lines + 4:
                lines.append("")
            return "\n".join(lines)

        # Sort by total activity (depth + in_flight) highest first
        active_queues.sort(key=lambda x: -(x[1].depth + x[2]))

        # Show top N queues
        display_queues = active_queues[:max_lines]

        # Calculate dynamic scale based on max tasks per queue
        max_tasks_per_queue = max(
            max(q.depth, in_flight) for _, q, in_flight in display_queues
        )
        # Use total_tasks to set a reasonable scale, or fall back to max observed
        if total_tasks > 0:
            scale_max = max(total_tasks // len(display_queues), max_tasks_per_queue, 10)
        else:
            scale_max = max(max_tasks_per_queue, 10)

        # Calculate max name length for alignment
        max_name_len = max(
            len(f"{q.service}/{q.model[:15]}") for q, _, _ in display_queues
        )

        for q_meta, queue, in_flight in display_queues:
            depth = queue.depth

            # Build two progress bars with dynamic scaling
            # Scale: each char = scale_max / bar_width tasks
            chars_per_task = bar_width / scale_max if scale_max > 0 else 1

            # Queued bar (magenta)
            queued_chars = min(int(depth * chars_per_task), bar_width)
            # In-flight bar (blue)
            in_flight_chars = min(int(in_flight * chars_per_task), bar_width)

            queued_bar = f"{Colors.MAGENTA}{'█' * queued_chars}{Colors.RESET}"
            in_flight_bar = f"{Colors.BLUE}{'█' * in_flight_chars}{Colors.RESET}"

            # Pad bars to fixed width with gray dots
            queued_padding = bar_width - queued_chars
            in_flight_padding = bar_width - in_flight_chars
            queued_bar += f"{Colors.GRAY}{'░' * queued_padding}{Colors.RESET}"
            in_flight_bar += f"{Colors.GRAY}{'░' * in_flight_padding}{Colors.RESET}"

            # Get throughput stats (actual average usage)
            stats = queue.get_throughput_stats()
            rpm_limit = int(queue.rpm_bucket.capacity)
            tpm_limit = int(queue.tpm_bucket.capacity)
            avg_tpm = stats["avg_tpm"]
            tpm_util = stats["tpm_utilization"]
            is_frozen = stats.get("is_frozen", False)

            name = f"{q_meta.service}/{q_meta.model[:15]}"
            padded_name = name.ljust(max_name_len)

            # Status indicator
            if is_frozen and depth == 0 and in_flight == 0:
                status = f"{Colors.GREEN}done{Colors.RESET}"
            else:
                status = f"Q:{depth:3d} F:{in_flight:3d}"

            # Format: name [queued][in_flight] status  TPM: current/limit (%)
            avg_tpm_str = f"{avg_tpm:,.0f}"
            tpm_limit_str = f"{tpm_limit:,}"
            lines.append(
                f"  {Colors.CYAN}{padded_name}{Colors.RESET} "
                f"[{queued_bar}][{in_flight_bar}] {status} "
                f"{Colors.GRAY}TPM:{Colors.RESET}{avg_tpm_str}/{tpm_limit_str} ({tpm_util:4.0f}%)"
            )

        # Summary line with totals
        remaining = len(active_queues) - len(display_queues)
        summary = f"  {Colors.MAGENTA}█{Colors.RESET}queued:{total_queued:,} {Colors.BLUE}█{Colors.RESET}in-flight:{total_in_flight:,}"
        if remaining > 0:
            summary += f" {Colors.GRAY}(+{remaining} more queues){Colors.RESET}"
        lines.append(summary)

        # Scale legend
        lines.append(
            f"  {Colors.GRAY}(scale: {bar_width} chars = {scale_max} tasks){Colors.RESET}"
        )

        # Pad to fixed height
        while len(lines) < max_lines + 4:
            lines.append("")

        return "\n".join(lines)

    def render_all(self, job_ids: list[str] | None = None) -> str:
        """Render all jobs and queues."""
        lines = []

        # Header
        lines.append(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        lines.append(f"{Colors.BOLD}EDSL Job Execution Status{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        lines.append("")

        # Jobs
        if job_ids:
            for job_id in job_ids:
                lines.append(self.render_job(job_id))
                lines.append("")
        else:
            lines.append(f"  {Colors.GRAY}(no jobs to display){Colors.RESET}")
            lines.append("")

        # Queues
        lines.append(self.render_queues())
        lines.append("")

        # Legend
        lines.append(
            f"{Colors.GRAY}Legend: "
            f"{Colors.GREEN}●{Colors.GRAY}=completed "
            f"{Colors.YELLOW}●{Colors.GRAY}=pending "
            f"{Colors.MAGENTA}◐{Colors.GRAY}=queued "
            f"{Colors.BLUE}◐{Colors.GRAY}=in-flight "
            f"{Colors.RED}●{Colors.GRAY}=failed "
            f"{Colors.GRAY}○=skipped{Colors.RESET}"
        )

        return "\n".join(lines)


class JobHandleVisualizer:
    """Visualization methods that can be called from JobHandle."""

    def __init__(
        self,
        job_id: str,
        storage: StorageProtocol,
        registry: QueueRegistry | None = None,
        coordinator: "ExecutionCoordinator | None" = None,
    ):
        self._job_id = job_id
        self._visualizer = JobVisualizer(storage, registry, coordinator)

    def show(self, details: bool = False, compact: bool = False) -> None:
        """Print job visualization to terminal."""
        if compact:
            output = self._visualizer.render_job_compact(self._job_id)
        else:
            output = self._visualizer.render_job(self._job_id, show_details=details)
        print(output)

    def show_queues(self) -> None:
        """Print queue visualization to terminal."""
        output = self._visualizer.render_queues()
        print(output)

    def show_all(self) -> None:
        """Print full visualization to terminal."""
        output = self._visualizer.render_all([self._job_id])
        print(output)

    def status_line(self) -> str:
        """Return a single-line status summary."""
        job_def = self._visualizer._jobs.get_definition(self._job_id)
        if job_def is None:
            return f"Job {self._job_id[:8]}... not found"

        # Count task statuses
        stats = {
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "queued": 0,
            "in_flight": 0,
            "skipped": 0,
        }

        for interview_id in job_def.interview_ids:
            interview_def = self._visualizer._interviews.get_definition(
                self._job_id, interview_id
            )
            if interview_def is None:
                continue

            for task_id in interview_def.task_ids:
                status = self._visualizer._tasks.get_status(task_id)
                if status == TaskStatus.COMPLETED:
                    stats["completed"] += 1
                elif status == TaskStatus.FAILED:
                    stats["failed"] += 1
                elif status == TaskStatus.SKIPPED:
                    stats["skipped"] += 1
                elif status == TaskStatus.RUNNING:
                    stats["in_flight"] += 1
                elif status in (TaskStatus.RENDERING, TaskStatus.QUEUED):
                    stats["queued"] += 1
                else:
                    stats["pending"] += 1

        total = sum(stats.values())
        return (
            f"Job {self._job_id[:8]}... "
            f"{Colors.GREEN}✓{stats['completed']}{Colors.RESET}/"
            f"{Colors.YELLOW}○{stats['pending']}{Colors.RESET}/"
            f"{Colors.MAGENTA}◐{stats['queued']}{Colors.RESET}/"
            f"{Colors.BLUE}◐{stats['in_flight']}{Colors.RESET}/"
            f"{Colors.RED}✗{stats['failed']}{Colors.RESET} "
            f"({total} tasks)"
        )


def demo():
    """Demo visualization with mock data."""
    print(f"{Colors.BOLD}Visualization Demo{Colors.RESET}")
    print()

    # Show color samples
    print("Task status colors:")
    print(f"  {Colors.GREEN}{Symbols.DOT_FILLED}{Colors.RESET} Completed")
    print(f"  {Colors.YELLOW}{Symbols.DOT_FILLED}{Colors.RESET} Pending/Ready/Blocked")
    print(f"  {Colors.MAGENTA}{Symbols.DOT_HALF}{Colors.RESET} Queued/Rendering")
    print(f"  {Colors.BLUE}{Symbols.DOT_HALF}{Colors.RESET} In-Flight (waiting on LLM)")
    print(f"  {Colors.RED}{Symbols.DOT_FILLED}{Colors.RESET} Failed")
    print(f"  {Colors.GRAY}{Symbols.DOT_EMPTY}{Colors.RESET} Skipped")
    print()

    # Show sample job visualization
    print("Sample job visualization:")
    print(
        f"  {Colors.BOLD}Job a1b2c3d4...{Colors.RESET} {Colors.GRAY}(14:32:15){Colors.RESET}"
    )
    print(
        f"  [{Colors.GREEN}●●●{Colors.RESET}{Colors.YELLOW}●{Colors.RESET}] "
        f"[{Colors.GREEN}●●{Colors.RESET}{Colors.BLUE}◐{Colors.RESET}{Colors.YELLOW}●{Colors.RESET}] "
        f"[{Colors.GREEN}●{Colors.RESET}{Colors.RED}●{Colors.RESET}{Colors.GRAY}○○{Colors.RESET}]"
    )
    print(
        f"  {Colors.GREEN}✓6{Colors.RESET} {Colors.YELLOW}○2{Colors.RESET} "
        f"{Colors.BLUE}◐1{Colors.RESET} {Colors.RED}✗1{Colors.RESET} "
        f"{Colors.GRAY}⊘2{Colors.RESET} / 12 tasks"
    )
    print()

    # Show sample queue visualization (names padded for alignment)
    print("Sample queue visualization:")
    print(
        f"  {Symbols.QUEUE} {Colors.GREEN}openai/gpt-4o               {Colors.RESET} "
        f"[{Colors.CYAN}●●●●●{Colors.RESET}] {Colors.GRAY}(5){Colors.RESET}"
    )
    print(
        f"  {Symbols.QUEUE} {Colors.GREEN}anthropic/claude-3-5-sonnet {Colors.RESET} "
        f"[{Colors.CYAN}●●●{Colors.RESET}] {Colors.GRAY}(3){Colors.RESET}"
    )
    print(
        f"  {Symbols.QUEUE} {Colors.GRAY}google/gemini-2.0-flash     {Colors.RESET} "
        f"[{Colors.CYAN}●{Colors.RESET}] {Colors.GRAY}(1){Colors.RESET}"
    )


if __name__ == "__main__":
    demo()
