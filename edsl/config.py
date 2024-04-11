"""This module provides a Config class that loads environment variables from a .env file and sets them as class attributes."""

import os
from dotenv import load_dotenv, find_dotenv
from edsl.exceptions import (
    InvalidEnvironmentVariableError,
    MissingEnvironmentVariableError,
)

# valid values for EDSL_RUN_MODE
EDSL_RUN_MODES = ["development", "development-testrun", "production"]

# `default` is used to impute values only in "production" mode
# `info` gives a brief description of the env var
CONFIG_MAP = {
    "EDSL_RUN_MODE": {
        "default": "production",
        "info": "This env var determines the run mode of the application.",
    },
    "EDSL_DATABASE_PATH": {
        "default": f"sqlite:///{os.path.join(os.getcwd(), '.edsl_cache/data.db')}",
        "info": "This env var determines the path to the cache file.",
    },
    "EDSL_LOGGING_PATH": {
        "default": f"{os.path.join(os.getcwd(), 'interview.log')}",
        "info": "This env var determines the path to the log file.",
    },
    "EDSL_API_TIMEOUT": {
        "default": "60",
        "info": "This env var determines the maximum number of seconds to wait for an API call to return.",
    },
    "EDSL_BACKOFF_START_SEC": {
        "default": "1",
        "info": "This env var determines the number of seconds to wait before retrying a failed API call.",
    },
    "EDSL_MAX_BACKOFF_SEC": {
        "default": "60",
        "info": "This env var determines the maximum number of seconds to wait before retrying a failed API call.",
    },
    "EDSL_MAX_ATTEMPTS": {
        "default": "5",
        "info": "This env var determines the maximum number of times to retry a failed API call.",
    },
    "EXPECTED_PARROT_URL": {
        "default": "https://www.expectedparrot.com",
        "info": "This env var holds the URL of the Expected Parrot API.",
    },
    # "EXPECTED_PARROT_API_KEY": {
    #     "default": None,
    #     "info": "This env var holds your Expected Parrot API key (https://www.expectedparrot.com/).",
    # },
    # "OPENAI_API_KEY": {
    #     "default": None,
    #     "info": "This env var holds your OpenAI API key (https://platform.openai.com/api-keys).",
    # },
    # "DEEP_INFRA_API_KEY": {
    #     "default": None,
    #     "info": "This env var holds your DeepInfra API key (https://deepinfra.com/).",
    # },
    # "GOOGLE_API_KEY": {
    #     "default": None,
    #     "info": "This env var holds your Google API key (https://console.cloud.google.com/apis/credentials).",
    # },
    # "ANTHROPIC_API_KEY": {
    #     "default": None,
    #     "info": "This env var holds your Anthropic API key (https://www.anthropic.com/).",
    # },
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
        Checks the validity and sets EDSL_RUN_MODE.
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
        - Overrides existing env vars unless EDSL_RUN_MODE=="development-testrun"
        """
        override = True
        if self.EDSL_RUN_MODE == "development-testrun":
            override = False
        _ = load_dotenv(dotenv_path=find_dotenv(usecwd=True), override=override)

    def _set_env_vars(self) -> None:
        """
        Sets env vars as Config class attributes.
        - If an env var is not set and has a default value in the CONFIG_MAP, sets it to the default value.
        """
        # for each env var in the CONFIG_MAP
        for env_var, config in CONFIG_MAP.items():
            if env_var == "EDSL_RUN_MODE":
                continue  # we've set it already in _set_run_mode
            value = os.getenv(env_var)
            default_value = config.get("default")
            # if the env var is set, set it as a CONFIG attribute
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
