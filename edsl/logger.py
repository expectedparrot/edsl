"""
Logger module for EDSL.

This module provides a centralized logging configuration for the EDSL package.
It configures console and file logging with appropriate formatting.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Union, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList

# Create the logger
logger = logging.getLogger("edsl")
logger.setLevel(logging.ERROR)  # Default level

# Avoid adding handlers multiple times when imported in different modules
if not logger.handlers:
    # Console handler removed - logs only go to file now

    # File handler - create logs directory if it doesn't exist
    try:
        log_dir = Path.home() / ".edsl" / "logs"
        os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / "edsl.log", maxBytes=5 * 1024 * 1024, backupCount=3  # 5 MB
        )
        file_handler.setLevel(logging.ERROR)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Don't fail if file logging can't be set up
        # No console handler to adjust
        print(f"WARNING: Could not set up file logging: {e}")


def get_logger(name):
    """
    Get a logger for a specific module.

    Args:
        name: Usually __name__ of the module

    Returns:
        A Logger instance configured with the EDSL settings
    """
    return logging.getLogger(f"edsl.{name}")


def set_level(level):
    """
    Set the logging level for the EDSL logger.

    Args:
        level: A logging level (e.g., logging.DEBUG, logging.INFO, etc.)
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

    # Update child loggers
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith("edsl."):
            logging.getLogger(logger_name).setLevel(level)


# Convenience function to avoid importing logging in every file
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)


def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)


def exception(msg, *args, **kwargs):
    """Log an exception with traceback at the ERROR level"""
    logger.exception(msg, *args, **kwargs)


def configure_from_config():
    """
    Configure logging based on EDSL_LOG_LEVEL environment variable or config.

    This function looks for the EDSL_LOG_LEVEL setting in the config and sets
    the logging level accordingly. Valid values are:
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL
    If no configuration is found, the default level (ERROR) is maintained.

    """
    try:
        import os

        # First check environment variable
        log_level = os.environ.get("EDSL_LOG_LEVEL")

        # If not in environment, try to get from config
        if not log_level:
            try:
                from edsl.config import CONFIG

                log_level = CONFIG.EDSL_LOG_LEVEL
            except (ImportError, AttributeError):
                # Config might not be available or doesn't have EDSL_LOG_LEVEL
                pass

        if log_level:
            # Convert to uppercase to match logging constants
            log_level = log_level.upper()

            # Map string to logging level
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }

            if log_level in level_map:
                set_level(level_map[log_level])
                info(f"Log level set to {log_level} from configuration")
            else:
                warning(f"Invalid log level in configuration: {log_level}")
    except Exception as e:
        # Catch any exceptions to ensure logging configuration doesn't break the application
        warning(f"Error configuring logging from config: {e}")


# LogManager classes for filtering and managing EDSL log entries


@dataclass
class LogEntry:
    """Represents a single log entry with parsed components."""

    timestamp: datetime
    logger_name: str
    level: str
    message: str
    raw_line: str

    def __post_init__(self):
        """Convert level string to logging level integer for comparison."""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self.level_int = level_map.get(self.level, logging.NOTSET)


class LogManager:
    """
    Manager class for filtering and processing EDSL log entries.

    Provides comprehensive filtering capabilities for EDSL log files including
    level-based, time-based, pattern-based, and logger-based filtering.

    Examples:
        # Get last 100 error entries
        from edsl.logger import LogManager
        log_manager = LogManager()
        errors = log_manager.get_filtered_entries(n=100, level='ERROR')

        # Get entries from last 24 hours with pattern matching
        recent_errors = log_manager.get_filtered_entries(
            since_hours=24,
            level='ERROR',
            pattern='exception|error|failed'
        )

        # Convert to scenarios for EDSL analysis
        scenarios = log_manager.to_scenario_list(level='ERROR', n=50)
    """

    def __init__(self, log_file_path: Optional[Path] = None):
        """
        Initialize LogManager with optional custom log file path.

        Args:
            log_file_path: Path to log file. If None, uses default EDSL log path.
        """
        self.log_file_path = (
            log_file_path or Path.home() / ".edsl" / "logs" / "edsl.log"
        )
        self._cached_stats = None

    def __repr__(self) -> str:
        """
        Return a string representation of the LogManager with overview and help.
        """
        try:
            # Get basic stats, using cache if available
            if self._cached_stats is None:
                self._cached_stats = self.get_stats()
            stats = self._cached_stats

            if stats["total"] == 0:
                return f"LogManager(log_file='{self.log_file_path}', entries=0, status='No log entries found')"

            # Format date range
            earliest = stats["date_range"]["earliest"].strftime("%Y-%m-%d %H:%M")
            latest = stats["date_range"]["latest"].strftime("%Y-%m-%d %H:%M")

            # Format level counts
            levels = []
            for level, count in sorted(
                stats["level_counts"].items(), key=lambda x: x[1], reverse=True
            ):
                levels.append(f"{level}:{count}")
            level_str = ", ".join(levels)

            # Top logger
            top_logger = (
                list(stats["top_loggers"].keys())[0] if stats["top_loggers"] else "N/A"
            )

            repr_str = f"""LogManager(
  📁 Log file: {self.log_file_path}
  📊 Total entries: {stats['total']:,}
  📅 Date range: {earliest} to {latest}
  📈 Levels: {level_str}
  🔍 Top logger: {top_logger}

  💡 Common commands:
    .get_filtered_entries(level='ERROR', n=50)          # Get recent errors
    .to_scenario_list(level='ERROR', since_hours=24)    # Convert to scenarios
    .analyze_patterns(n=100)                            # Pattern analysis
    .export_filtered_logs(Path('errors.log'), level='ERROR')  # Export logs
    .archive()                                          # Archive and clear logs
    .clear()                                            # Clear all log entries
)"""
            return repr_str

        except Exception as e:
            return f"LogManager(log_file='{self.log_file_path}', error='{str(e)}')"

    def _repr_html_(self) -> str:
        """
        Return HTML representation for Jupyter notebooks.
        """
        try:
            # Get basic stats
            if self._cached_stats is None:
                self._cached_stats = self.get_stats()
            stats = self._cached_stats

            if stats["total"] == 0:
                return f"""
                <div style="border: 1px solid #ddd; border-radius: 5px; padding: 15px; font-family: monospace;">
                    <h3 style="margin: 0 0 10px 0; color: #666;">📋 EDSL LogManager</h3>
                    <p><strong>Log file:</strong> {self.log_file_path}</p>
                    <p><strong>Status:</strong> <span style="color: #f39c12;">No log entries found</span></p>
                </div>
                """

            # Format date range
            earliest = stats["date_range"]["earliest"].strftime("%Y-%m-%d %H:%M")
            latest = stats["date_range"]["latest"].strftime("%Y-%m-%d %H:%M")

            # Create level counts table
            level_rows = []
            for level, count in sorted(
                stats["level_counts"].items(), key=lambda x: x[1], reverse=True
            ):
                color = {
                    "CRITICAL": "#e74c3c",
                    "ERROR": "#e74c3c",
                    "WARNING": "#f39c12",
                    "INFO": "#3498db",
                    "DEBUG": "#95a5a6",
                }.get(level, "#7f8c8d")
                level_rows.append(
                    f'<tr><td style="color: {color}; font-weight: bold;">{level}</td><td>{count:,}</td></tr>'
                )

            # Top loggers
            top_logger_rows = []
            for logger, count in list(stats["top_loggers"].items())[:5]:
                top_logger_rows.append(
                    f'<tr><td style="font-family: monospace; color: #2c3e50;">{logger}</td><td>{count:,}</td></tr>'
                )

            html = f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; font-family: Arial, sans-serif; background: #f8f9fa;">
                <h3 style="margin: 0 0 15px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
                    📋 EDSL LogManager
                </h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        <h4 style="margin: 0 0 10px 0; color: #34495e;">📊 Overview</h4>
                        <p style="margin: 5px 0;"><strong>📁 Log file:</strong> <code style="background: #ecf0f1; padding: 2px 4px; border-radius: 3px;">{self.log_file_path}</code></p>
                        <p style="margin: 5px 0;"><strong>📈 Total entries:</strong> {stats['total']:,}</p>
                        <p style="margin: 5px 0;"><strong>📅 Date range:</strong><br><small>{earliest} → {latest}</small></p>
                    </div>
                    
                    <div>
                        <h4 style="margin: 0 0 10px 0; color: #34495e;">📈 Log Levels</h4>
                        <table style="width: 100%; border-collapse: collapse;">
                            {''.join(level_rows)}
                        </table>
                    </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <h4 style="margin: 0 0 10px 0; color: #34495e;">🔍 Top Loggers</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        {''.join(top_logger_rows)}
                    </table>
                </div>
                
                <div style="background: #e8f6f3; border: 1px solid #1abc9c; border-radius: 5px; padding: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: #16a085;">💡 Quick Start Commands</h4>
                    <div style="font-family: monospace; font-size: 12px; line-height: 1.4;">
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Get recent errors</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>log_manager.get_filtered_entries(level='ERROR', n=50)</code></div>
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Convert to scenarios for analysis</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>scenarios = log_manager.to_scenario_list(level='ERROR', since_hours=24)</code></div>
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Pattern analysis</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>analysis = log_manager.analyze_patterns(n=100)</code></div>
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Export filtered logs</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>log_manager.export_filtered_logs(Path('errors.log'), level='ERROR')</code></div>
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Archive and clear logs</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>log_manager.archive()</code></div>
                        <div style="margin: 5px 0;"><code style="color: #2c3e50;"># Clear all log entries</code></div>
                        <div style="margin: 5px 0; color: #8e44ad;"><code>log_manager.clear()</code></div>
                    </div>
                </div>
            </div>
            """
            return html

        except Exception as e:
            return f"""
            <div style="border: 1px solid #e74c3c; border-radius: 5px; padding: 15px; background: #fdf2f2; color: #e74c3c;">
                <h3 style="margin: 0 0 10px 0;">❌ LogManager Error</h3>
                <p><strong>Log file:</strong> {self.log_file_path}</p>
                <p><strong>Error:</strong> {str(e)}</p>
            </div>
            """

    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a LogEntry object.

        Args:
            line: Raw log line string

        Returns:
            LogEntry object if parsing successful, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        # Pattern to match: timestamp - logger_name - level - message
        pattern = (
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.*?) - (\w+) - (.*)$"
        )
        match = re.match(pattern, line)

        if not match:
            return None

        timestamp_str, logger_name, level, message = match.groups()

        try:
            # Parse timestamp
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
        except ValueError:
            return None

        return LogEntry(
            timestamp=timestamp,
            logger_name=logger_name,
            level=level,
            message=message,
            raw_line=line,
        )

    def _read_log_entries(self) -> List[LogEntry]:
        """
        Read and parse all log entries from the log file.

        Returns:
            List of LogEntry objects

        Raises:
            FileNotFoundError: If log file doesn't exist
        """
        if not self.log_file_path.exists():
            raise FileNotFoundError(f"Log file not found at {self.log_file_path}")

        entries = []
        try:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = self._parse_log_line(line)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            raise Exception(f"Error reading log file: {e}")

        return entries

    def get_filtered_entries(
        self,
        n: Optional[int] = None,
        level: Optional[Union[str, List[str]]] = None,
        min_level: Optional[str] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        since_hours: Optional[float] = None,
        since_minutes: Optional[float] = None,
        pattern: Optional[str] = None,
        logger_pattern: Optional[str] = None,
        case_sensitive: bool = False,
        reverse: bool = True,
    ) -> List[LogEntry]:
        """
        Get filtered log entries based on various criteria.

        Args:
            n: Maximum number of entries to return (applied after filtering)
            level: Specific log level(s) to include ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            min_level: Minimum log level (includes this level and higher)
            start_date: Start date for filtering (string 'YYYY-MM-DD' or datetime object)
            end_date: End date for filtering (string 'YYYY-MM-DD' or datetime object)
            since_hours: Include entries from last N hours
            since_minutes: Include entries from last N minutes
            pattern: Regex pattern to match in message content
            logger_pattern: Regex pattern to match logger names
            case_sensitive: Whether pattern matching is case sensitive
            reverse: Return entries in reverse chronological order (newest first)

        Returns:
            List of filtered LogEntry objects
        """
        entries = self._read_log_entries()

        # Apply level filtering
        if level:
            if isinstance(level, str):
                level = [level]
            level_upper = [level_name.upper() for level_name in level]
            entries = [e for e in entries if e.level in level_upper]

        # Apply minimum level filtering
        if min_level:
            min_level_int = getattr(logging, min_level.upper(), logging.NOTSET)
            entries = [e for e in entries if e.level_int >= min_level_int]

        # Apply time-based filtering
        now = datetime.now()

        if since_hours:
            cutoff = now - timedelta(hours=since_hours)
            entries = [e for e in entries if e.timestamp >= cutoff]

        if since_minutes:
            cutoff = now - timedelta(minutes=since_minutes)
            entries = [e for e in entries if e.timestamp >= cutoff]

        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            entries = [e for e in entries if e.timestamp >= start_date]

        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                # Add 24 hours to include the entire end date
                end_date = end_date + timedelta(days=1)
            entries = [e for e in entries if e.timestamp < end_date]

        # Apply pattern filtering
        if pattern:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern_re = re.compile(pattern, flags)
            entries = [e for e in entries if pattern_re.search(e.message)]

        # Apply logger pattern filtering
        if logger_pattern:
            flags = 0 if case_sensitive else re.IGNORECASE
            logger_re = re.compile(logger_pattern, flags)
            entries = [e for e in entries if logger_re.search(e.logger_name)]

        # Sort entries
        entries.sort(key=lambda e: e.timestamp, reverse=reverse)

        # Apply count limit
        if n:
            entries = entries[:n]

        return entries

    def get_entry_lines(self, entries: List[LogEntry]) -> List[str]:
        """
        Convert LogEntry objects back to raw log lines.

        Args:
            entries: List of LogEntry objects

        Returns:
            List of raw log line strings
        """
        return [entry.raw_line for entry in entries]

    def get_stats(self, entries: Optional[List[LogEntry]] = None) -> Dict[str, Any]:
        """
        Get statistics about log entries.

        Args:
            entries: List of entries to analyze. If None, analyzes all entries.

        Returns:
            Dictionary containing statistics
        """
        if entries is None:
            entries = self._read_log_entries()

        if not entries:
            return {"total": 0}

        level_counts = {}
        logger_counts = {}

        for entry in entries:
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
            logger_counts[entry.logger_name] = (
                logger_counts.get(entry.logger_name, 0) + 1
            )

        return {
            "total": len(entries),
            "date_range": {
                "earliest": min(entries, key=lambda e: e.timestamp).timestamp,
                "latest": max(entries, key=lambda e: e.timestamp).timestamp,
            },
            "level_counts": level_counts,
            "top_loggers": dict(
                sorted(logger_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }

    def export_filtered_logs(self, output_path: Path, **filter_kwargs) -> int:
        """
        Export filtered log entries to a file.

        Args:
            output_path: Path where filtered logs should be saved
            **filter_kwargs: Arguments to pass to get_filtered_entries()

        Returns:
            Number of entries exported
        """
        entries = self.get_filtered_entries(**filter_kwargs)
        lines = self.get_entry_lines(entries)

        with open(output_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        return len(lines)

    def to_scenario_list(
        self, entries: Optional[List[LogEntry]] = None, **filter_kwargs
    ) -> "ScenarioList":
        """
        Convert log entries to a ScenarioList for analysis with EDSL.

        Each log entry becomes a Scenario with fields:
        - timestamp_str: timestamp as string
        - logger_name: name of the logger
        - level: log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - level_int: numeric level for comparison
        - message: log message content
        - raw_line: original log line
        - hour: hour of the day (0-23)
        - minute: minute of the hour (0-59)
        - weekday: day of the week (0=Monday, 6=Sunday)
        - date_str: date as YYYY-MM-DD string

        Args:
            entries: Pre-filtered entries to convert. If None, applies filter_kwargs
            **filter_kwargs: Arguments to pass to get_filtered_entries() if entries is None

        Returns:
            ScenarioList containing log entry scenarios

        Examples:
            # Convert recent errors to scenarios
            from edsl.logger import LogManager
            log_manager = LogManager()
            scenarios = log_manager.to_scenario_list(level='ERROR', n=50)

            # Analyze patterns using EDSL
            from edsl import QuestionFreeText
            q = QuestionFreeText(
                question_name="error_analysis",
                question_text="Analyze this error: {{ message }}"
            )
            results = q.by(scenarios).run()
        """
        # Import here to avoid circular imports
        from edsl.scenarios import Scenario, ScenarioList

        if entries is None:
            entries = self.get_filtered_entries(**filter_kwargs)

        scenarios = []
        for entry in entries:
            scenario_data = {
                "timestamp_str": entry.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "logger_name": entry.logger_name,
                "level": entry.level,
                "level_int": entry.level_int,
                "message": entry.message,
                "raw_line": entry.raw_line,
                # Additional derived fields for analysis
                "hour": entry.timestamp.hour,
                "minute": entry.timestamp.minute,
                "weekday": entry.timestamp.weekday(),
                "date_str": entry.timestamp.strftime("%Y-%m-%d"),
                # Extract common patterns
                "is_error": entry.level in ["ERROR", "CRITICAL"],
                "is_warning_or_above": entry.level_int >= logging.WARNING,
                "logger_module": entry.logger_name.split(".")[-1]
                if "." in entry.logger_name
                else entry.logger_name,
                "has_exception": "exception" in entry.message.lower(),
                "has_failed": "fail" in entry.message.lower(),
                "message_length": len(entry.message),
                "words_count": len(entry.message.split()),
            }
            scenarios.append(Scenario(scenario_data))

        return ScenarioList(scenarios)

    def analyze_patterns(self, **filter_kwargs) -> Dict[str, Any]:
        """
        Analyze log patterns by converting to ScenarioList and extracting insights.

        Args:
            **filter_kwargs: Arguments to pass to get_filtered_entries()

        Returns:
            Dictionary containing pattern analysis results
        """
        scenario_list = self.to_scenario_list(**filter_kwargs)

        if len(scenario_list) == 0:
            return {"total_entries": 0, "patterns": {}}

        analysis = {
            "total_entries": len(scenario_list),
            "time_patterns": {},
            "level_patterns": {},
            "logger_patterns": {},
            "content_patterns": {},
            "error_patterns": {},
        }

        # Time pattern analysis
        hourly_counts = {}
        daily_counts = {}
        for scenario in scenario_list:
            hour = scenario["hour"]
            date = scenario["date_str"]
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            daily_counts[date] = daily_counts.get(date, 0) + 1

        analysis["time_patterns"] = {
            "busiest_hour": max(hourly_counts.items(), key=lambda x: x[1])
            if hourly_counts
            else None,
            "hourly_distribution": hourly_counts,
            "daily_distribution": daily_counts,
            "peak_days": sorted(daily_counts.items(), key=lambda x: x[1], reverse=True)[
                :5
            ],
        }

        # Level and logger patterns
        level_counts = {}
        logger_counts = {}
        for scenario in scenario_list:
            level = scenario["level"]
            logger = scenario["logger_module"]
            level_counts[level] = level_counts.get(level, 0) + 1
            logger_counts[logger] = logger_counts.get(logger, 0) + 1

        analysis["level_patterns"] = level_counts
        analysis["logger_patterns"] = dict(
            sorted(logger_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Content analysis
        error_scenarios = [s for s in scenario_list if s["is_error"]]
        if error_scenarios:
            analysis["error_patterns"] = {
                "total_errors": len(error_scenarios),
                "error_percentage": len(error_scenarios) / len(scenario_list) * 100,
                "exception_count": sum(
                    1 for s in error_scenarios if s["has_exception"]
                ),
                "failure_count": sum(1 for s in error_scenarios if s["has_failed"]),
                "avg_message_length": sum(s["message_length"] for s in error_scenarios)
                / len(error_scenarios),
            }

        # Message patterns
        avg_msg_length = sum(s["message_length"] for s in scenario_list) / len(
            scenario_list
        )
        analysis["content_patterns"] = {
            "avg_message_length": avg_msg_length,
            "long_messages": len(
                [s for s in scenario_list if s["message_length"] > avg_msg_length * 2]
            ),
            "short_messages": len(
                [s for s in scenario_list if s["message_length"] < avg_msg_length * 0.5]
            ),
        }

        return analysis

    def clear(self, confirm: bool = False) -> bool:
        """
        Clear all log entries by truncating the log file.

        This method removes all log entries from the log file, effectively
        starting with a clean slate. Use with caution as this action cannot be undone.

        Args:
            confirm: If True, skip confirmation prompt and clear immediately.
                    If False, prompt user for confirmation (default).

        Returns:
            True if log was cleared successfully, False if cancelled or failed.

        Raises:
            FileNotFoundError: If log file doesn't exist
            PermissionError: If insufficient permissions to modify log file

        Examples:
            # Clear with confirmation prompt
            success = log_manager.clear()

            # Clear without confirmation (use carefully!)
            success = log_manager.clear(confirm=True)
        """
        if not self.log_file_path.exists():
            raise FileNotFoundError(f"Log file not found at {self.log_file_path}")

        # Get current stats before clearing
        try:
            current_stats = self.get_stats()
            total_entries = current_stats.get("total", 0)
        except Exception:
            total_entries = "unknown"

        # Confirmation prompt unless explicitly confirmed
        if not confirm:
            print("⚠️  About to clear EDSL log file:")
            print(f"   📁 File: {self.log_file_path}")
            print(f"   📊 Entries: {total_entries}")
            print("   ⚠️  This action cannot be undone!")

            response = input("   Continue? (type 'yes' to confirm): ").strip().lower()
            if response != "yes":
                print("   🚫 Log clear cancelled.")
                return False

        try:
            # Clear the file by truncating it
            with open(self.log_file_path, "w"):
                pass  # Just open in write mode, which truncates the file

            # Clear cached stats
            self._cached_stats = None

            print("✅ Log file cleared successfully.")
            print(f"   📁 File: {self.log_file_path}")
            print(f"   📊 Removed: {total_entries} entries")

            return True

        except Exception as e:
            print(f"❌ Failed to clear log file: {e}")
            return False

    def archive(
        self,
        archive_path: Optional[Path] = None,
        clear_after_archive: bool = True,
        compress: bool = True,
        confirm: bool = False,
    ) -> Optional[Path]:
        """
        Archive the current log file to a backup location.

        Creates a backup copy of the current log file with timestamp, optionally
        compresses it, and optionally clears the original log file afterward.

        Args:
            archive_path: Directory to store archive. If None, uses ~/.edsl/archives/
            clear_after_archive: Whether to clear original log after archiving (default: True)
            compress: Whether to gzip compress the archive (default: True)
            confirm: If True, skip confirmation prompt (default: False)

        Returns:
            Path to created archive file if successful, None if failed or cancelled.

        Raises:
            FileNotFoundError: If log file doesn't exist

        Examples:
            # Archive and clear log with compression
            archive_file = log_manager.archive()

            # Archive only, don't clear original
            archive_file = log_manager.archive(clear_after_archive=False)

            # Archive to custom location without compression
            custom_path = Path('~/my_backups')
            archive_file = log_manager.archive(archive_path=custom_path, compress=False)
        """
        import gzip
        import shutil
        from datetime import datetime

        if not self.log_file_path.exists():
            raise FileNotFoundError(f"Log file not found at {self.log_file_path}")

        # Get current stats
        try:
            current_stats = self.get_stats()
            total_entries = current_stats.get("total", 0)
            if current_stats.get("date_range"):
                earliest = current_stats["date_range"]["earliest"]
                latest = current_stats["date_range"]["latest"]
                date_info = (
                    f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}"
                )
            else:
                date_info = "no entries"
        except Exception:
            total_entries = "unknown"
            date_info = "unknown range"

        # Set up archive directory
        if archive_path is None:
            archive_path = Path.home() / ".edsl" / "archives"
        archive_path = Path(archive_path).expanduser()
        archive_path.mkdir(parents=True, exist_ok=True)

        # Generate archive filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"edsl_log_{timestamp}.log"
        if compress:
            archive_name += ".gz"

        archive_file_path = archive_path / archive_name

        # Confirmation prompt unless explicitly confirmed
        if not confirm:
            print("📦 About to archive EDSL log file:")
            print(f"   📁 Source: {self.log_file_path}")
            print(f"   📊 Entries: {total_entries} ({date_info})")
            print(f"   📦 Archive: {archive_file_path}")
            print(f"   🗜️  Compress: {'Yes' if compress else 'No'}")
            print(f"   🧹 Clear after: {'Yes' if clear_after_archive else 'No'}")

            response = input("   Continue? (type 'yes' to confirm): ").strip().lower()
            if response != "yes":
                print("   🚫 Archive cancelled.")
                return None

        try:
            # Create archive
            if compress:
                with open(self.log_file_path, "rb") as f_in:
                    with gzip.open(archive_file_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(self.log_file_path, archive_file_path)

            archive_size = archive_file_path.stat().st_size
            print("✅ Archive created successfully:")
            print(f"   📦 Archive: {archive_file_path}")
            print(f"   📏 Size: {archive_size:,} bytes")

            # Clear original log if requested
            if clear_after_archive:
                print("   🧹 Clearing original log file...")
                success = self.clear(
                    confirm=True
                )  # Skip prompt since already confirmed
                if success:
                    print("   ✅ Original log cleared")
                else:
                    print("   ⚠️  Failed to clear original log")

            return archive_file_path

        except Exception as e:
            print(f"❌ Failed to create archive: {e}")
            return None
