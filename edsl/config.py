"""This module provides a Config class that loads environment variables from a .env file and sets them as class attributes."""

import os
from dotenv import load_dotenv, find_dotenv
from edsl.exceptions import (
    InvalidEnvironmentVariableError,
    MissingEnvironmentVariableError,
)

# valid values for EDSL_RUN_MODE
EDSL_RUN_MODES = [
    "development",
    "development-testrun",
    "production",
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
        "default": f"sqlite:///{os.path.join(os.getcwd(), '.edsl_cache/data.db')}",
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
    "EDSL_MAX_ATTEMPTS": {
        "default": "5",
        "info": "This config var determines the maximum number of times to retry a failed API call.",
    },
    "EDSL_SERVICE_RPM_BASELINE": {
        "default": "100",
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
        "default": "500",
        "info": "This config var determines the maximum number of concurrent tasks that can be run by the async job-runner",
    },
    "EDSL_OPEN_EXCEPTION_REPORT_URL": {
        "default": "False",
        "info": "This config var determines whether to open the exception report URL in the browser",
    },
}


class Config:
    """A class that loads environment variables from a .env file and sets them as class attributes."""

    def __init__(self):
        """Initialize the Config class."""
        self._set_run_mode()
        self._load_dotenv()
        self._set_env_vars()

    def _set_run_mode(self) -> None:
        """
        Sets EDSL_RUN_MODE as a class attribute.
        """
        run_mode = os.getenv("EDSL_RUN_MODE")
        default = CONFIG_MAP.get("EDSL_RUN_MODE").get("default")
        if run_mode is None:
            run_mode = default
        if run_mode not in EDSL_RUN_MODES:
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
        """
        # for each env var in the CONFIG_MAP
        for env_var, config in CONFIG_MAP.items():
            # EDSL_RUN_MODE is already set by _set_run_mode
            if env_var == "EDSL_RUN_MODE":
                continue
            value = os.getenv(env_var)
            default_value = config.get("default")
            # if an env var exists, set it as a class attribute
            if value:
                setattr(self, env_var, value)
            # otherwise, if EDSL_RUN_MODE == "production" set it to its default value
            elif self.EDSL_RUN_MODE == "production":
                setattr(self, env_var, default_value)

    def get(self, env_var: str) -> str:
        """
        Returns the value of an environment variable.
        """
        if env_var not in CONFIG_MAP:
            raise InvalidEnvironmentVariableError(f"{env_var} is not a valid env var. ")
        elif env_var not in self.__dict__:
            info = CONFIG_MAP[env_var].get("info")
            raise MissingEnvironmentVariableError(f"{env_var} is not set. {info}")
        return self.__dict__.get(env_var)

    def show(self) -> str:
        """Print the currently set environment vars."""
        max_env_var_length = max(len(env_var) for env_var in self.__dict__)
        print("Here are the current configuration settings:")
        for env_var, value in self.__dict__.items():
            print(f"{env_var:<{max_env_var_length}} : {value}")


# Note: Python modules are singletons. As such, once this module is imported
# the same instance of it is reused across the application.
CONFIG = Config()
