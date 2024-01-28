import os
import sys
from dotenv import load_dotenv, find_dotenv
from getpass import getpass
from typing import Any
from edsl.exceptions import (
    InvalidEnvironmentVariableError,
    MissingEnvironmentVariableError,
)

CONFIG_MAP = {
    "EDSL_RUN_MODE": {
        "default": "production",
        "allowed": ["development", "production"],
        "user_message": None,
    },
    "EDSL_PASTEBIN_URL": {
        "default": "http://127.0.0.1:5000",
        "allowed": None,
        "user_message": None,
    },
    "EDSL_DATABASE_PATH": {
        "default": f"sqlite:///{os.path.join(os.getcwd(), 'edsl_cache.db')}",
        "allowed": None,
        "user_message": None,
    },
    "EMERITUS_API_KEY": {
        "default": "local",
        "allowed": None,
        "user_message": "Please provide your Emeritus API key (https://emeritus.org/).",
    },
    "OPENAI_API_KEY": {
        "default": None,
        "allowed": None,
        "user_message": "Please provide your OpenAI API key (https://platform.openai.com/api-keys).",
    },
    "DEEP_INFRA_API_KEY": {
        "default": None,
        "allowed": None,
        "user_message": "Please provide your DeepInfra API key (https://deepinfra.com/).",
    },
    "GOOGLE_API_KEY": {
        "default": None,
        "allowed": None,
        "user_message": "Please provide your Google API key (https://console.cloud.google.com/apis/credentials).",
    },
    "API_CALL_TIMEOUT_SEC": {
        "default": "60",
        "allowed": None,
        "user_message": "What is the maximum number of seconds to wait for an API call to return?",
    },
}


class Config:
    def __init__(self):
        self._load_dotenv()
        self._set_env_vars()
        self._validate_attributes()

    def _load_dotenv(self) -> None:
        """
        Loads environment variables from the .env file.
        Overrides existing env vars, unless the env var EDSL_TESTING="True".
        """
        override = True
        if os.getenv("EDSL_TESTING") == "True":
            override = False
        _ = load_dotenv(dotenv_path=find_dotenv(usecwd=True), override=override)

    def _set_env_vars(self) -> None:
        """Sets env vars as Config class attributes. If an env var is not set and has a default value in the CONFIG_MAP, sets it to the default value."""
        for env_var, config in CONFIG_MAP.items():
            # if the env var is set, set it as a CONFIG attribute as well
            if value := os.getenv(env_var):
                setattr(self, env_var, value)
            # if the env var is not set and has a default value, set it as an CONFIG attribute and as an env var
            elif default_value := config.get("default"):
                setattr(self, env_var, default_value)
                os.environ[env_var] = default_value

    def _set_env_var(self, env_var: str, config: dict[str, Any]) -> None:
        """Attempts to set an environment variable."""
        if self.EDSL_RUN_MODE == "development":
            raise MissingEnvironmentVariableError(f"Missing env var {env_var}.")
        else:
            print("=" * 50)
            print(config.get("user_message"))
            print(f"If you would like to skip this step, press enter.")
            print(f"If you would like to provide your key, do one of the following:")
            print(f"1. Set it as a regular environment variable")
            print(f"2. Create a .env file and add `{env_var}=...` to it")
            print(f"3. Enter the value below and press enter: ")
            # if the script is running in a terminal
            if sys.stdout.isatty():
                # try to use get_pass to mask the input
                try:
                    value = getpass()
                # if you fail, use input instead
                except Exception as e:
                    value = input()
            # otherwise use input
            else:
                value = input()
            value = value.strip()
            setattr(self, env_var, value)
            os.environ[env_var] = value
            if value:
                if len(value) <= 4:
                    masked_value = value
                else:
                    masked_value = value[:2] + "*" * (len(value) - 4) + value[-2:]
                print(
                    f"Environment variable {env_var} set successfully to {masked_value}."
                )
            else:
                print(f"Skipping setting environment variable {env_var}.")
            print("=" * 50)
            print("\n")

    def _validate_attributes(self):
        """Validates that all attributes are allowed values."""
        for attr, value in self.__dict__.items():
            config = CONFIG_MAP.get(attr)
            if config.get("allowed") and value not in config.get("allowed"):
                raise InvalidEnvironmentVariableError(
                    f"Variable {attr} has value {value}, which is not allowed.\n"
                    f"Allowed values are: {config.get('allowed')}. "
                )

    def get(self, env_var: str) -> str:
        """
        Returns the value of an environment variable.
        - If the environment variable is valid but not set, attempts to set it.
        """
        if env_var not in CONFIG_MAP:
            raise InvalidEnvironmentVariableError(
                f"Variable {env_var} is not a valid environment variable. "
                f"Valid environment variables are: {set(CONFIG_MAP.keys())}."
            )
        elif env_var not in self.__dict__:
            self._set_env_var(env_var, CONFIG_MAP.get(env_var))
        return self.__dict__.get(env_var)

    def show(self) -> str:
        """Prints the currently set environment vars."""
        max_env_var_length = max(len(env_var) for env_var in self.__dict__)
        print("Here are the current configuration settings:")
        for env_var, value in self.__dict__.items():
            print(f"{env_var:<{max_env_var_length}} : {value}")


# Note: Python modules are singletons. As such, once this module is imported
# the same instance of it is reused across the application.
CONFIG = Config()
