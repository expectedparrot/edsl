from typing import Protocol, TYPE_CHECKING
import sys

# from edsl.scenarios.FileStore import HTMLFileStore
from ..config import CONFIG

if TYPE_CHECKING:
    pass


from .exceptions import JobsErrors


class ResultsProtocol(Protocol):
    """Protocol defining the required interface for Results objects."""

    @property
    def has_unfixed_exceptions(self) -> bool:
        ...

    @property
    def task_history(self) -> "TaskHistoryProtocol":
        ...


class TaskHistoryProtocol(Protocol):
    """Protocol defining the required interface for TaskHistory objects."""

    @property
    def indices(self) -> list:
        ...

    def html(self, cta: str, open_in_browser: bool, return_link: bool) -> str:
        ...


class RunParametersProtocol(Protocol):
    """Protocol defining the required interface for RunParameters objects."""

    @property
    def print_exceptions(self) -> bool:
        ...


class ResultsExceptionsHandler:
    """Handles exception reporting and display functionality."""

    def __init__(
        self, results: ResultsProtocol, parameters: RunParametersProtocol
    ) -> None:
        self.results = results
        self.parameters = parameters

        self.open_in_browser = self._get_browser_setting()

        # Debug: Show what would happen if remote logging was enabled
        print("DEBUG: Remote logging is currently hard-coded to False", flush=True)
        print(
            "DEBUG: To enable remote logging, uncomment the line below and set remote_logging in Coop settings",
            flush=True,
        )

        # Uncomment this line to enable remote logging from Coop settings:
        # self.remote_logging = self._get_remote_logging_setting()
        self.remote_logging = False

        print(
            f"DEBUG: ResultsExceptionsHandler initialized with remote_logging={self.remote_logging}",
            flush=True,
        )

    def _get_browser_setting(self) -> bool:
        """Determine if exceptions should be opened in browser based on config."""
        setting = CONFIG.get("EDSL_OPEN_EXCEPTION_REPORT_URL")
        if setting == "True":
            return True
        elif setting == "False":
            return False
        else:
            raise JobsErrors(
                "EDSL_OPEN_EXCEPTION_REPORT_URL must be either True or False"
            )

    def _get_remote_logging_setting(self) -> bool:
        """Get remote logging setting from coop."""
        try:
            from ..coop.coop import Coop

            print("DEBUG: Checking remote logging settings from Coop", flush=True)
            coop = Coop()
            remote_logging_enabled = coop.edsl_settings["remote_logging"]
            print(
                f"DEBUG: Remote logging setting from Coop: {remote_logging_enabled}",
                flush=True,
            )
            return remote_logging_enabled
        except Exception as e:
            print(
                f"DEBUG: Failed to get remote logging settings from Coop: {e}",
                flush=True,
            )
            return False

    def _generate_error_message(self, indices) -> str:
        """Generate appropriate error message based on number of exceptions."""
        msg = "Exceptions were raised.\n"
        return msg

    def handle_exceptions(self) -> None:
        """Handle exceptions by printing messages and generating reports as needed."""
        print(
            f"DEBUG: handle_exceptions() called - has_unfixed_exceptions={self.results.has_unfixed_exceptions}, print_exceptions={self.parameters.print_exceptions}",
            flush=True,
        )

        if not (
            self.results.has_unfixed_exceptions and self.parameters.print_exceptions
        ):
            print(
                "DEBUG: No exceptions to handle or printing disabled, returning early",
                flush=True,
            )
            return

        print(
            "DEBUG: Processing exceptions - generating error message and HTML report",
            flush=True,
        )

        # Print error message
        error_msg = self._generate_error_message(self.results.task_history.indices)
        print(error_msg, file=sys.stderr)

        # Generate HTML report
        filepath = self.results.task_history.html(
            open_in_browser=self.open_in_browser,
            return_link=True,
        )
        print(f"DEBUG: HTML exception report generated at: {filepath}", flush=True)

        # Handle remote logging if enabled
        print(
            f"DEBUG: Checking remote logging - enabled: {self.remote_logging}",
            flush=True,
        )
        if self.remote_logging:
            print(
                "DEBUG: Remote logging is enabled, uploading exception report to Coop",
                flush=True,
            )
            try:
                from ..scenarios import FileStore

                filestore = FileStore(filepath)
                print(
                    f"DEBUG: Created FileStore object for path: {filepath}", flush=True
                )

                print("DEBUG: Starting upload to Coop via filestore.push()", flush=True)
                coop_details = filestore.push(description="Exceptions Report")
                print(
                    f"DEBUG: Successfully uploaded exception report to Coop: {coop_details}",
                    flush=True,
                )
                print(coop_details)

            except Exception as e:
                print(
                    f"DEBUG: Failed to upload exception report to Coop: {e}", flush=True
                )
                raise
        else:
            print("DEBUG: Remote logging is disabled, skipping Coop upload", flush=True)
