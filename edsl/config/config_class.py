"""This module provides a Config class that loads environment variables from a .env file and sets them as class attributes."""

import os
import platformdirs
from dotenv import load_dotenv, find_dotenv
from ..base import BaseException
from ..base.base_class import RepresentationMixin
import logging

logger = logging.getLogger(__name__)


class InvalidEnvironmentVariableError(BaseException):
    """Raised when an environment variable is invalid."""

    pass


class MissingEnvironmentVariableError(BaseException):
    """Raised when an expected environment variable is missing."""

    pass


cache_dir = platformdirs.user_cache_dir("edsl")
os.makedirs(cache_dir, exist_ok=True)

# valid values for EDSL_RUN_MODE
EDSL_RUN_MODES = [
    "development",
    "development-testrun",
    "production",
]

# valid values for EDSL_DEFAULT_TABLE_RENDERER
EDSL_TABLE_RENDERERS = [
    "pandas",
    "datatables",
    "rich",
    "tabulator",
]

# `default` is used to impute values only in "production" mode
# `info` gives a brief description of the env var
CONFIG_MAP = {
    "EDSL_RUN_MODE": {
        "default": "production",
        "info": "This config var determines the run mode of the application.",
    },
    "EDSL_API_TIMEOUT": {
        "default": "60",
        "info": "This config var determines the maximum number of seconds to wait for an API call to return.",
    },
    "EDSL_BACKOFF_START_SEC": {
        "default": "1",
        "info": "This config var determines the number of seconds to wait before retrying a failed API call.",
    },
    "EDSL_BACKOFF_MAX_SEC": {
        "default": "60",
        "info": "This config var determines the maximum number of seconds to wait before retrying a failed API call.",
    },
    "EDSL_DATABASE_PATH": {
        # "default": f"sqlite:///{os.path.join(os.getcwd(), '.edsl_cache/data.db')}",
        "default": f"sqlite:///{os.path.join(platformdirs.user_cache_dir('edsl'), 'lm_model_calls.db')}",
        "info": "This config var determines the path to the cache file.",
    },
    "EDSL_DEFAULT_MODEL": {
        "default": "gpt-4o",
        "info": "This config var holds the default model that will be used if a model is not explicitly passed.",
    },
    "EDSL_FETCH_TOKEN_PRICES": {
        "default": "True",
        "info": "This config var determines whether to fetch prices for tokens used in remote inference",
    },
    "EDSL_LOG_DIR": {
        "default": str(os.path.join(platformdirs.user_data_dir("edsl"), "logs")),
        "info": "This config var determines the directory where logs are stored.",
    },
    "EDSL_LOG_LEVEL": {
        "default": "ERROR",
        "info": "This config var determines the logging level for the EDSL package (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    },
    "EDSL_MAX_ATTEMPTS": {
        "default": "3",
        "info": "This config var determines the maximum number of times to retry a failed API call.",
    },
    "EDSL_SERVICE_RPM_BASELINE": {
        "default": "1000",
        "info": "This config var holds the maximum number of requests per minute. Model-specific values provided in env vars such as EDSL_SERVICE_RPM_OPENAI will override this. value for the corresponding model",
    },
    "EDSL_SERVICE_TPM_BASELINE": {
        "default": "2000000",
        "info": "This config var holds the maximum number of tokens per minute for all models. Model-specific values provided in env vars such as EDSL_SERVICE_TPM_OPENAI will override this value for the corresponding model.",
    },
    "EXPECTED_PARROT_URL": {
        "default": "https://www.expectedparrot.com",
        "info": "This config var holds the URL of the Expected Parrot API.",
    },
    "EDSL_MAX_CONCURRENT_TASKS": {
        "default": "50",
        "info": "This config var determines the maximum number of concurrent tasks that can be run by the async job-runner. Reduced from 1000 to 50 for better performance with fewer context switches.",
    },
    "EDSL_OPEN_EXCEPTION_REPORT_URL": {
        "default": "False",
        "info": "This config var determines whether to open the exception report URL in the browser",
    },
    "EDSL_REMOTE_TOKEN_BUCKET_URL": {
        "default": "None",
        "info": "This config var holds the URL of the remote token bucket server.",
    },
    "EDSL_SQLLIST_MEMORY_THRESHOLD": {
        "default": "10",  # Change to a very low threshold (10 bytes) to test SQLite offloading
        "info": "This config var determines the memory threshold in bytes before SQLList offloads data to SQLite.",
    },
    "EDSL_SQLLIST_DB_PATH": {
        "default": f"sqlite:///{os.path.join(platformdirs.user_cache_dir('edsl'), 'sql_list_data.db')}",
        "info": "This config var determines the default database path for SQLList instances.",
    },
    "EDSL_RESULTS_MEMORY_THRESHOLD": {
        "default": "10",  # Change to a very low threshold (10 bytes) to test SQLite offloading
        "info": "This config var determines the memory threshold in bytes before Results' SQLList offloads data to SQLite.",
    },
    "EDSL_MAX_PRICE_BEFORE_CONFIRM": {
        "default": "90",
        "info": "This config var determines the maximum price before a confirmation prompt is shown.",
    },
    "EDSL_USE_SQLITE_FOR_SCENARIO_LIST": {
        "default": "False",
        "info": "This config var determines whether to use SQLite for ScenarioList instances.",
    },
    "EDSL_VERBOSE_MODE": {
        "default": "False",
        "info": "This config var determines whether to enable verbose output mode throughout the application.",
    },
    "EDSL_DEFAULT_TABLE_RENDERER": {
        "default": "pandas",
        "info": "This config var determines the default table renderer for displaying datasets in notebooks (options: 'pandas', 'datatables', 'rich', 'tabulator').",
        "valid_values": EDSL_TABLE_RENDERERS,
    },
}


class Config(RepresentationMixin):
    """A class that loads environment variables from a .env file and sets them as class attributes."""

    def __init__(self):
        """Initialize the Config class."""
        logger.debug("Initializing Config class")
        self._set_run_mode()
        self._load_dotenv()
        self._set_env_vars()
        logger.info(f"Config initialized with run mode: {self.EDSL_RUN_MODE}")

    def show_path_to_dot_env(self):
        print(find_dotenv(usecwd=True))

    def _set_run_mode(self) -> None:
        """
        Sets EDSL_RUN_MODE as a class attribute.
        """
        run_mode = os.getenv("EDSL_RUN_MODE")
        default = CONFIG_MAP.get("EDSL_RUN_MODE").get("default")
        if run_mode is None:
            run_mode = default
            logger.debug(f"EDSL_RUN_MODE not set, using default: {default}")
        else:
            logger.debug(f"EDSL_RUN_MODE set to: {run_mode}")

        if run_mode not in EDSL_RUN_MODES:
            logger.error(f"Invalid EDSL_RUN_MODE: {run_mode}")
            raise InvalidEnvironmentVariableError(
                f"Value `{run_mode}` is not allowed for EDSL_RUN_MODE."
            )
        self.EDSL_RUN_MODE = run_mode

    def _load_dotenv(self) -> None:
        """
        Loads the .env
        - The .env will override existing env vars **unless** EDSL_RUN_MODE=="development-testrun"
        """

        if self.EDSL_RUN_MODE == "development-testrun":
            override = False
        else:
            override = True
        _ = load_dotenv(dotenv_path=find_dotenv(usecwd=True), override=override)

    def __contains__(self, env_var: str) -> bool:
        """
        Checks if an env var is set as a class attribute.
        """
        return env_var in self.__dict__

    def _set_env_vars(self) -> None:
        """
        Sets env vars as class attributes.
        - EDSL_RUN_MODE is not set my this method, but by _set_run_mode
        - If an env var is not set and has a default value in the CONFIG_MAP, sets it to the default value.
        - Validates values against valid_values if specified in CONFIG_MAP
        """
        # for each env var in the CONFIG_MAP
        for env_var, config in CONFIG_MAP.items():
            # EDSL_RUN_MODE is already set by _set_run_mode
            if env_var == "EDSL_RUN_MODE":
                continue
            value = os.getenv(env_var)
            default_value = config.get("default")
            valid_values = config.get("valid_values")

            # if an env var exists, validate and set it as a class attribute
            if value:
                # Validate the value if valid_values is specified
                if valid_values and value not in valid_values:
                    logger.error(f"Invalid value for {env_var}: {value}")
                    raise InvalidEnvironmentVariableError(
                        f"Invalid value '{value}' for {env_var}. "
                        f"Valid values are: {', '.join(valid_values)}"
                    )
                setattr(self, env_var, value)
            # otherwise, if EDSL_RUN_MODE == "production" set it to its default value
            elif self.EDSL_RUN_MODE == "production":
                setattr(self, env_var, default_value)

    def get_extension_gateway_url(self) -> str:
        """
        Dynamically generates extension gateway URL based on EXPECTED_PARROT_URL value.
        """
        # Get EXPECTED_PARROT_URL value
        expected_parrot_url = getattr(
            self, "EXPECTED_PARROT_URL", os.getenv("EXPECTED_PARROT_URL", "")
        )

        if "localhost" in expected_parrot_url:
            extension_gateway_url = "http://localhost:8008"
        elif "chick" in expected_parrot_url:
            extension_gateway_url = "https://test.extensions.expectedparrot.com"
        else:
            extension_gateway_url = "https://extensions.expectedparrot.com"

        logger.debug(
            f"Generated extension gateway URL: {extension_gateway_url} based on EXPECTED_PARROT_URL: {expected_parrot_url}"
        )
        return extension_gateway_url

    def get(self, env_var: str) -> str:
        """
        Returns the value of an environment variable.
        """
        logger.debug(f"Getting config value for: {env_var}")

        if env_var not in CONFIG_MAP:
            logger.error(f"Invalid environment variable requested: {env_var}")
            raise InvalidEnvironmentVariableError(f"{env_var} is not a valid env var. ")
        elif env_var not in self.__dict__:
            info = CONFIG_MAP[env_var].get("info")
            logger.error(f"Missing environment variable: {env_var}")
            raise MissingEnvironmentVariableError(f"{env_var} is not set. {info}")

        value = self.__dict__.get(env_var)
        logger.debug(f"Config value for {env_var}: {value}")
        return value

    def __iter__(self):
        """Iterate over the environment variables."""
        return iter(self.__dict__)

    def items(self):
        """Iterate over the environment variables and their values."""
        return self.__dict__.items()

    def to_dict(self) -> dict:
        """Return the config settings as a dictionary.

        Returns:
            dict: A dictionary of all current configuration settings
        """
        return dict(self.__dict__)

    def modify(self, **kwargs) -> None:
        """
        Modify EDSL configuration settings at runtime and persist them to .env file.

        This method allows you to update configuration settings on the Config object.
        It will:
        1. Validate that the setting names are valid
        2. Validate that the setting values are valid (if constraints exist)
        3. Update the in-memory CONFIG object
        4. Update or create the .env file in the current working directory

        Args:
            **kwargs: Key-value pairs of configuration settings to update.
                     Keys should be valid CONFIG_MAP variable names.

        Raises:
            InvalidEnvironmentVariableError: If an invalid configuration variable name
                                            or value is provided.

        Examples:
            >>> from edsl import Config
            >>> Config.modify(EDSL_DEFAULT_TABLE_RENDERER="datatables")
            >>> Config.modify(EDSL_LOG_LEVEL="INFO", EDSL_VERBOSE_MODE="True")

        Note:
            Changes take effect immediately in the current session and are persisted
            to .env for future sessions.
        """
        from pathlib import Path

        # Validate all settings first
        for key, value in kwargs.items():
            if key not in CONFIG_MAP:
                available = ", ".join(CONFIG_MAP.keys())
                raise InvalidEnvironmentVariableError(
                    f"'{key}' is not a valid configuration variable. "
                    f"Available settings: {available}"
                )

            # Validate the value if valid_values is specified
            config = CONFIG_MAP[key]
            valid_values = config.get("valid_values")
            if valid_values and str(value) not in valid_values:
                raise InvalidEnvironmentVariableError(
                    f"Invalid value '{value}' for {key}. "
                    f"Valid values are: {', '.join(valid_values)}"
                )

        # Update the in-memory CONFIG object
        for key, value in kwargs.items():
            setattr(self, key, str(value))
            logger.info(f"Updated {key} to {value}")

        # Update the .env file using dotenv's set_key for safe updates
        from dotenv import set_key

        env_path = Path.cwd() / ".env"

        # Use dotenv's set_key which properly handles updating existing files
        for key, value in kwargs.items():
            set_key(env_path, key, str(value))

        print(f"Configuration updated successfully. Changes saved to {env_path}")
        print("\nUpdated settings:")
        for key, value in kwargs.items():
            print(f"  {key} = {value}")

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Config object.

        Returns:
            str: A string representation that shows the config settings
        """
        return f"Config({dict(self.__dict__)})"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the Config object with Rich formatting.

        Returns:
            str: A formatted summary representation of the configuration
        """
        from edsl.config import RICH_STYLES
        from rich.console import Console
        from rich.text import Text
        import io

        # Get all config items
        config_items = dict(self.__dict__)
        num_settings = len(config_items)

        # Build the Rich text
        output = Text()
        output.append("Config(\n", style=RICH_STYLES["primary"])
        output.append(
            f"    num_settings={num_settings},\n", style=RICH_STYLES["default"]
        )
        output.append("    settings={\n", style=RICH_STYLES["default"])

        # Add each config setting with its info
        for key in sorted(config_items.keys()):
            value = config_items[key]
            # Get info for this setting if available
            config_entry = CONFIG_MAP.get(key, {})
            info = config_entry.get("info", "")

            # Format the line
            output.append(f"        '{key}'", style=RICH_STYLES["key"])
            output.append(f": {repr(value)}", style=RICH_STYLES["default"])

            if info:
                output.append(f"  # {info}", style=RICH_STYLES["dim"])

            output.append(",\n", style=RICH_STYLES["default"])

        output.append("    }\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])

        # Render to string
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True, width=200)
        console.print(output, end="")
        return string_io.getvalue()

    def to_scenario_list(self):
        """Convert Config to a ScenarioList for easy display and manipulation.

        Returns:
            ScenarioList: A ScenarioList where each scenario represents one config setting
        """
        from edsl.scenarios import Scenario, ScenarioList

        scenarios = []
        for key in sorted(self.__dict__.keys()):
            value = self.__dict__[key]
            config_entry = CONFIG_MAP.get(key, {})
            info = config_entry.get("info", "")

            scenarios.append(
                Scenario({"setting": key, "value": str(value), "description": info})
            )

        return ScenarioList(scenarios)

    def _repr_html_(self):
        """Generate an HTML representation for Jupyter notebooks.

        Converts the Config to a ScenarioList and uses its HTML representation.

        Returns:
            str: HTML representation of the Config object
        """
        # Create header
        class_name = self.__class__.__name__
        num_settings = len(self.__dict__)
        header = f"<p><strong>{class_name}</strong> (num_settings={num_settings})</p>"

        # Convert to ScenarioList and get its HTML representation
        scenario_list = self.to_scenario_list()
        table_html = scenario_list._repr_html_(include_class_info=False)

        return header + table_html

    def show(self) -> str:
        """Print the currently set environment vars."""
        max_env_var_length = max(len(env_var) for env_var in self.__dict__)
        print("Here are the current configuration settings:")
        for env_var, value in self.__dict__.items():
            print(f"{env_var:<{max_env_var_length}} : {value}")


# Note: Python modules are singletons. As such, once this module is imported
# the same instance of it is reused across the application.
CONFIG = Config()


def modify_settings(**kwargs) -> None:
    """
    Modify EDSL configuration settings at runtime and persist them to .env file.

    This function is maintained for backward compatibility. It delegates to CONFIG.modify().
    For new code, consider using `Config.modify()` directly:

        >>> from edsl import Config
        >>> Config.modify(EDSL_DEFAULT_TABLE_RENDERER="datatables")

    Args:
        **kwargs: Key-value pairs of configuration settings to update.
                 Keys should be valid CONFIG_MAP variable names (e.g., EDSL_DEFAULT_TABLE_RENDERER).

    Raises:
        InvalidEnvironmentVariableError: If an invalid configuration variable name is provided.

    Examples:
        >>> from edsl import modify_settings
        >>> modify_settings(EDSL_DEFAULT_TABLE_RENDERER="datatables")
        >>> modify_settings(EDSL_LOG_LEVEL="INFO", EDSL_VERBOSE_MODE="True")

    Note:
        Changes take effect immediately in the current session and are persisted to .env
        for future sessions.
    """
    CONFIG.modify(**kwargs)


def show_settings() -> None:
    """
    Display all current EDSL configuration settings.

    This is a convenience wrapper around CONFIG.show() that displays
    all configuration variables and their current values.

    Examples:
        >>> from edsl import show_settings
        >>> show_settings()  # doctest: +SKIP
        Here are the current configuration settings:
        EDSL_RUN_MODE              : production
        EDSL_DEFAULT_TABLE_RENDERER: pandas
        ...
    """
    CONFIG.show()
