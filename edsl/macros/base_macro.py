"""Base class for all macro types (Macro and CompositeMacro).

This module provides the abstract BaseMacro class that consolidates common
functionality shared between Macro and CompositeMacro, including:
- Smart constructor that can load from server or create new instances
- Display and representation methods
- Serialization infrastructure
- Deployment logic
- Common properties and utilities
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any
from abc import ABC, abstractmethod
import re
from html import escape

from ..base import Base
from ..scenarios import Scenario

if TYPE_CHECKING:
    from ..scenarios import ScenarioList
    from ..surveys import Survey
    from .output_formatter import OutputFormatters


class MacroMixin:
    """Mixin for shared class methods across all macro types.

    This provides methods that are available to both the Macro and CompositeMacro classes.
    """

    @classmethod
    def public_macros(cls) -> "ScenarioList":
        """List all deployed macros.

        Returns:
            List of deployed macro information.
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        # Fetch list of deployed macros
        response = requests.get(
            f"{BASE_URL}/api/v0/macros/deployed",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        macros_list = response.json()
        from ..scenarios import ScenarioList

        return ScenarioList.from_list_of_dicts(macros_list["deployed_macros"])

    @classmethod
    def get_public_macro_uuid(cls, owner: str, alias: str) -> str:
        """Get macro UUID from fully qualified name.

        GET /api/v0/macros/deployed/{owner}/{alias}/uuid

        Args:
            owner: The owner of the macro.
            alias: The alias of the macro.

        Returns:
            The macro UUID.
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        response = requests.get(
            f"{BASE_URL}/api/v0/macros/deployed/{owner}/{alias}/uuid",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        return response.json()["macro_uuid"]


class BaseMacro(Base, MacroMixin, ABC):
    """Abstract base class for all macro types.

    Provides common functionality for Macro and CompositeMacro including:
    - Smart constructor for loading from server or creating new
    - Display and representation
    - Serialization
    - Deployment
    """

    # Subclass identifier
    application_type: str = "base"

    def __new__(
        cls,
        __macro_identifier: Optional[str] = None,
        *,
        application_name: Optional[str] = None,
        first_macro: Optional[Any] = None,  # For CompositeMacro
        **kwargs,
    ):
        """Universal macro constructor.

        Usage:
            Macro("owner/alias")                    # Load from server
            Macro(application_name="foo", ...)      # Create new Macro
            CompositeMacro(first_macro=m1, ...)     # Create new CompositeMacro

        Args:
            __macro_identifier: Optional qualified name or UUID to load from server
            application_name: Application name for new Macro (required for Macro)
            first_macro: First macro for CompositeMacro (required for CompositeMacro)
            **kwargs: Additional constructor arguments

        Returns:
            BaseMacro instance (might be Macro or CompositeMacro depending on server data)
        """
        if __macro_identifier is not None:
            # Load from server (might return Macro or CompositeMacro)
            return cls._load_from_server(__macro_identifier)

        # For Macro: application_name is required
        # For CompositeMacro: first_macro is required (application_name is optional)
        if cls.__name__ == "CompositeMacro":
            if first_macro is None:
                raise TypeError(
                    f"{cls.__name__}() missing required argument: 'first_macro'. "
                    f"To load from server, use: {cls.__name__}('owner/alias')"
                )
        else:
            # For Macro and other subclasses
            if application_name is None:
                raise TypeError(
                    f"{cls.__name__}() missing required keyword argument: 'application_name'. "
                    f"To load from server, use: {cls.__name__}('owner/alias')"
                )

        # Normal construction
        return super().__new__(cls)

    @classmethod
    def list(cls) -> "ScenarioList":
        """List all macros.

        Returns:
            List of macro information.
        """
        scenario_list = super().list()
        return scenario_list.select("description", "owner_username", "alias").table()

    @classmethod
    def _load_from_server(cls, identifier: str) -> "BaseMacro":
        """Load macro from server - tries deployed then owned.

        Args:
            identifier: Either "owner/alias" or a UUID string

        Returns:
            Loaded macro instance (Macro or CompositeMacro)
        """
        # Try deployed public macro first if it looks like "owner/alias"
        if "/" in identifier:
            try:
                return cls._instantiate_deployed(identifier)
            except Exception as e:
                # Fall back to pulling user's own macro
                try:
                    return cls.pull(identifier)
                except Exception as e2:
                    raise ValueError(
                        f"Could not load macro '{identifier}'. "
                        f"Not found as deployed macro (error: {e}) "
                        f"or as user macro (error: {e2})"
                    )

        # Looks like UUID - try pull first, then deployed
        try:
            return cls.pull(identifier)
        except Exception as pull_error:
            try:
                return cls._instantiate_deployed(identifier)
            except Exception as deploy_error:
                raise ValueError(
                    f"Could not load macro '{identifier}'. "
                    f"Not found as user macro (error: {pull_error}) "
                    f"or as deployed macro (error: {deploy_error})"
                )

    @classmethod
    def _instantiate_deployed(cls, qualified_name: str) -> "BaseMacro":
        """Instantiate a deployed (public) macro by qualified name.

        This creates a client-mode macro that executes remotely.

        Args:
            qualified_name: The fully qualified name (owner/alias) or macro_id

        Returns:
            The instantiated macro in client mode
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        # Parse owner/alias if provided
        if "/" in qualified_name:
            alias = qualified_name.split("/")[-1]
            owner = qualified_name.split("/")[-2]

            # Fetch macro dictionary
            response = requests.get(
                f"{BASE_URL}/api/v0/macros/deployed/{owner}/{alias}/instantiate_macro_client",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            macro_dict = response.json()

            # Load using from_dict (will dispatch to correct subclass)
            m = cls.from_dict(macro_dict)
            m.macro_id = cls.get_public_macro_uuid(owner, alias)
            m.client_mode = True
            m._initialized = (
                True  # Mark as initialized to prevent __init__ from re-running
            )
            return m
        else:
            # Assume it's a macro_id
            response = requests.get(
                f"{BASE_URL}/api/v0/macros/{qualified_name}/instantiate_macro_client",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            macro_dict = response.json()

            m = cls.from_dict(macro_dict)
            m.client_mode = True
            m.macro_id = qualified_name
            m._initialized = (
                True  # Mark as initialized to prevent __init__ from re-running
            )
            return m

    def alias(self) -> str:
        """Return the alias of the macro.

        Converts application_name to alias format (underscores to hyphens).
        """
        return self.application_name.replace("_", "-")

    @staticmethod
    def _name_to_alias(name: str) -> str:
        """Convert a display name to a valid Python identifier alias.

        Args:
            name: Human-readable name

        Returns:
            Valid Python identifier
        """
        alias = name.lower()
        alias = re.sub(r"[\s\-]+", "_", alias)
        alias = re.sub(r"[^\w]", "", alias)
        if alias and alias[0].isdigit():
            alias = f"macro_{alias}"
        if not alias:
            alias = "macro"
        return alias

    def deploy(
        self, macro_uuid: Optional[str] = None, overwrite: bool = False
    ) -> Scenario:
        """Deploy the macro to the server.

        Args:
            macro_uuid: The UUID of the macro to deploy. If None, pushes to server first.
            overwrite: If True, overwrite any existing macro with the same owner/alias.

        Returns:
            Scenario containing deployment information
        """
        import requests
        from ..coop import Coop

        coop = Coop()
        BASE_URL = coop.api_url
        API_KEY = coop.api_key

        if macro_uuid is None:
            print("Deploying macro with no UUID, pushing to server...")
            info = self.push(overwrite=overwrite)
            macro_uuid = info["uuid"]
            print(f"Deployed macro with UUID: {macro_uuid}")

        MACRO_UUID = macro_uuid

        print(f"Deploying macro with UUID: {MACRO_UUID}")
        response = requests.post(
            f"{BASE_URL}/api/v0/macros/{MACRO_UUID}/deploy",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        result = response.json()

        print(f"Status: {result['status']}")
        print(f"Fully qualified name: {result['fully_qualified_name']}")
        print(f"Deployed: {result['deployed']}")

        return Scenario(result)

    @property
    def parameters(self) -> "Table":
        """Return ScenarioList of parameter info derived from the initial survey."""
        sl = self.parameters_scenario_list
        return (
            sl.select("question_name", "question_text", "question_type")
            .rename(
                {
                    "question_name": "parameter",
                    "question_text": "description",
                    "question_type": "input_type",
                }
            )
            .table()
        )

    @property
    def parameters_scenario_list(self) -> "ScenarioList":
        """Return ScenarioList of parameter info derived from the initial survey."""
        from ..scenarios.scenario_list import ScenarioList

        return ScenarioList(
            [
                Scenario(
                    {
                        "question_name": q.question_name,
                        "question_type": q.question_type,
                        "question_text": q.question_text,
                    }
                )
                for q in self.initial_survey
            ]
        )

    @staticmethod
    def _convert_markdown_to_html(md_text: str) -> str:
        """Convert markdown to HTML.

        Prefers the 'markdown' package if available. Falls back to a minimal
        regex-based converter that supports headings (#, ##, ###), bold, italics,
        and inline code, plus paragraph wrapping. Always escapes raw HTML first.
        """
        if md_text is None:
            return ""
        safe_text = escape(str(md_text))
        try:
            import markdown as md  # type: ignore

            return md.markdown(
                safe_text,
                extensions=["extra", "sane_lists", "tables"],
            )
        except Exception:
            pass

        text = safe_text
        # Headings
        text = re.sub(r"(?m)^######\s+(.+)$", r"<h6>\\1</h6>", text)
        text = re.sub(r"(?m)^#####\s+(.+)$", r"<h5>\\1</h5>", text)
        text = re.sub(r"(?m)^####\s+(.+)$", r"<h4>\\1</h4>", text)
        text = re.sub(r"(?m)^###\s+(.+)$", r"<h3>\\1</h3>", text)
        text = re.sub(r"(?m)^##\s+(.+)$", r"<h2>\\1</h2>", text)
        text = re.sub(r"(?m)^#\s+(.+)$", r"<h1>\\1</h1>", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\\1</code>", text)
        # Bold and italics (simple forms)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\\1</strong>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\\1</em>", text)
        # Paragraphs: split on blank lines
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        wrapped = [p if p.startswith("<h") else f"<p>{p}</p>" for p in parts]
        return "\n".join(wrapped)

    def __repr__(self) -> str:
        """Return a string representation of the macro.

        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability.
        """
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr_()
        else:
            return self._summary_repr()

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the macro.

        This representation provides a simplified view suitable for doctests.
        Used primarily for doctests and debugging.
        """
        cls_name = self.__class__.__name__
        return (
            f"{cls_name}(application_name='{self.application_name}', "
            f"display_name='{self.display_name}', "
            f"short_description='{self.short_description[:50]}...', "
            f"...)"
        )

    def _summary_repr(self, max_formatters: int = 5, max_params: int = 5) -> str:
        """Generate a summary representation of the macro with Rich formatting.

        Args:
            max_formatters: Maximum number of formatters to show before truncating
            max_params: Maximum number of parameters to show before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        # Build the Rich text
        output = Text()
        cls_name = self.__class__.__name__

        output.append(f"{cls_name}(\n", style=RICH_STYLES["primary"])

        # Application info
        output.append("    application_name=", style=RICH_STYLES["default"])
        output.append(f"'{self.application_name}'", style=RICH_STYLES["secondary"])
        output.append(",\n", style=RICH_STYLES["default"])

        output.append("    display_name=", style=RICH_STYLES["default"])
        output.append(f"'{self.display_name}'", style=RICH_STYLES["key"])
        output.append(",\n", style=RICH_STYLES["default"])

        # Short description (truncate if too long)
        desc = self.short_description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        output.append("    short_description=", style=RICH_STYLES["default"])
        output.append(f"'{desc}'", style=RICH_STYLES["primary"])
        output.append(",\n", style=RICH_STYLES["default"])

        # Application type - use getattr to get the actual class attribute value
        app_type = getattr(self.__class__, "application_type", "base")
        if not isinstance(app_type, str):
            app_type = self.__class__.__name__
        output.append("    application_type=", style=RICH_STYLES["default"])
        output.append(f"'{app_type}'", style=RICH_STYLES["secondary"])
        output.append(",\n", style=RICH_STYLES["default"])

        # Parameters
        try:
            param_names = [p["question_name"] for p in self.parameters_scenario_list]
            num_params = len(param_names)
        except Exception:
            param_names = []
            num_params = 0

        output.append(f"    num_parameters={num_params}", style=RICH_STYLES["default"])

        if num_params > 0:
            output.append(",\n    parameters=[", style=RICH_STYLES["default"])
            for i, name in enumerate(param_names[:max_params]):
                output.append(f"'{name}'", style=RICH_STYLES["secondary"])
                if i < min(num_params, max_params) - 1:
                    output.append(", ", style=RICH_STYLES["default"])
            if num_params > max_params:
                output.append(
                    f", ... ({num_params - max_params} more)", style=RICH_STYLES["dim"]
                )
            output.append("]", style=RICH_STYLES["default"])

        output.append(",\n", style=RICH_STYLES["default"])

        # Subclass-specific info
        self._add_summary_details(output, max_formatters)

        output.append("\n)", style=RICH_STYLES["primary"])

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    def _add_summary_details(self, output, max_formatters: int):
        """Add subclass-specific details to summary repr.

        Override in subclasses to add custom information.
        """
        from edsl.config import RICH_STYLES

        # Formatters
        try:
            fmt_names_list = list(getattr(self.output_formatters, "mapping", {}).keys())
            num_formatters = len(fmt_names_list)
        except Exception:
            fmt_names_list = []
            num_formatters = 0

        output.append(
            f"    num_formatters={num_formatters}", style=RICH_STYLES["default"]
        )

        if num_formatters > 0:
            output.append(",\n    formatters=[", style=RICH_STYLES["default"])
            for i, name in enumerate(fmt_names_list[:max_formatters]):
                output.append(f"'{name}'", style=RICH_STYLES["secondary"])
                if i < min(num_formatters, max_formatters) - 1:
                    output.append(", ", style=RICH_STYLES["default"])
            if num_formatters > max_formatters:
                output.append(
                    f", ... ({num_formatters - max_formatters} more)",
                    style=RICH_STYLES["dim"],
                )
            output.append("]", style=RICH_STYLES["default"])

        # Default formatter
        try:
            default_fmt_obj = (
                getattr(self.output_formatters, "default", None)
                or self.output_formatters.get_default()
            )
            default_fmt = (
                default_fmt_obj
                if isinstance(default_fmt_obj, str)
                else getattr(default_fmt_obj, "description", None)
                or getattr(default_fmt_obj, "name", "<none>")
            )
        except Exception:
            default_fmt = "<none>"

        if default_fmt != "<none>":
            output.append(",\n    default_formatter=", style=RICH_STYLES["default"])
            output.append(f"'{default_fmt}'", style=RICH_STYLES["secondary"])

    def _repr_html_(self) -> str:
        """Rich HTML representation used in notebooks and rich console renderers."""
        from .macro_html_renderer import MacroHTMLRenderer

        return MacroHTMLRenderer(self).render()

    # Abstract methods that subclasses must implement

    @property
    @abstractmethod
    def initial_survey(self) -> "Survey":
        """Return the initial survey for this macro."""
        pass

    @property
    @abstractmethod
    def output_formatters(self) -> "OutputFormatters":
        """Return the output formatters for this macro."""
        pass

    @abstractmethod
    def output(self, params: dict[str, Any] | None, **kwargs) -> Any:
        """Execute the macro and return formatted output."""
        pass

    @abstractmethod
    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Serialize this macro to a JSON-serializable dict."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseMacro":
        """Deserialize a macro from a dict payload."""
        pass

    @classmethod
    @abstractmethod
    def example(cls) -> "BaseMacro":
        """Return an example instance of this macro type."""
        pass
