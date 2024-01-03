import os
from dotenv import load_dotenv
from typing import Any
from edsl import BASE_DIR, ROOT_DIR
from edsl.exceptions import (
    InvalidEnvironmentVariableError,
    MissingEnvironmentVariableError,
)

DOTENV_PATH = os.path.join(ROOT_DIR, ".env")
CONFIG_MAP = {
    "EDSL_RUN_MODE": {
        "optional": True,
        "default": "production",
        "allowed": ["development", "production"],
        "user_message": None,
    },
    "EDSL_DATABASE_PATH": {
        "optional": True,
        "default": f"sqlite:///{os.path.join(BASE_DIR, 'data/database.db')}",
        "allowed": None,
        "user_message": None,
    },
    "EMERITUS_API_KEY": {
        "optional": True,
        "default": "local",
        "allowed": None,
        "user_message": "Please provide your Emeritus API key (https://emeritus.org/).",
    },
    "OPENAI_API_KEY": {
        "optional": False,
        "default": None,
        "allowed": None,
        "user_message": "Please provide your OpenAI API key (https://platform.openai.com/api-keys).",
    },
}


class Config:
    def __init__(self):
        self._load_env_vars_from_dotenv()
        self._set_env_vars()
        self._validate_attributes()
        self._cleanup_dotenv()

    def _load_env_vars_from_dotenv(self) -> None:
        """
        Loads environment variables from the .env file
        - Creates a .env file if it does not exist
        - .env variables override existing environment variables
        """
        if not os.path.exists(DOTENV_PATH):
            with open(DOTENV_PATH, "w") as f:
                f.write("")
        load_dotenv(dotenv_path=DOTENV_PATH, override=True)

    def _set_env_vars(self) -> None:
        """
        Sets env vars as Config class attributes.
        - optional env vars: set to default value if it exists, otherwise do not set
        - mandatory env vars: prompt the user to set it if it does not exist
        """
        for env_var, config in CONFIG_MAP.items():
            if value := os.getenv(env_var):
                setattr(self, env_var, value)
            elif default_value := config.get("default"):
                setattr(self, env_var, default_value)
                os.environ[env_var] = default_value
            elif not config.get("optional"):
                self._set_env_var(env_var, config)

    def _set_env_var(self, env_var: str, config: dict[str, Any]) -> None:
        """Attempts to set an environment variable."""
        if self.EDSL_RUN_MODE == "development":
            raise MissingEnvironmentVariableError(
                f"Missing environment variable {env_var}. Please set it:"
                f"- by adding a line `{env_var}=...` in the .env file (found at {DOTENV_PATH})"
                f"- or as a regular environment variable before running this script"
            )
        else:
            print(config.get("user_message"))
            print(f"There are three ways you can do this:")
            print(f"1. Set it as a regular environment variable")
            print(f"2. Close this program and add a line")
            print(f"{env_var}=... ")
            print(f"in the .env file (found at {DOTENV_PATH})")
            print(f"3. Enter the value below and press enter: ")
            value = input()
            value = value.strip()
            setattr(self, env_var, value)
            os.environ[env_var] = value
            with open(DOTENV_PATH, "a") as f:
                f.write(f"{env_var}={value}\n")
            print(f"Environment variable {env_var} set successfully to {value}.")
            print(f"Also saved the value in the .env file for future use.")

    def _validate_attributes(self):
        """Validates that all attributes are allowed values."""
        for attr, value in self.__dict__.items():
            config = CONFIG_MAP.get(attr)
            if config.get("allowed") and value not in config.get("allowed"):
                raise InvalidEnvironmentVariableError(
                    f"Variable {attr} has value {value}, which is not allowed.\n"
                    f"Allowed values are: {config.get('allowed')}. "
                )

    def _cleanup_dotenv(self) -> str:  # pragma: no cover
        """Prints warnings for unused and duplicate environment variables in the .env file."""
        valid_vars = set(CONFIG_MAP.keys())
        seen_vars = set()
        unused_vars = set()
        duplicate_vars = set()
        with open(DOTENV_PATH, "r") as file:
            for line in file:
                if not line.startswith("#"):
                    var = line.split("=")[0].strip()
                    if var in seen_vars:
                        duplicate_vars.add(var)
                    if var not in valid_vars:
                        unused_vars.add(var)
                    seen_vars.add(var)

        if unused_vars:
            print(f"Environment variables {unused_vars} are no longer in use.")
            print(f"- Please delete them from your .env file (found at {DOTENV_PATH}).")
            print(f"- Valid environment variables are: {valid_vars}.\n")
        if duplicate_vars:
            print(f"Environment variables {duplicate_vars} are duplicated.")
            print(
                f"- Please delete duplicates from your .env file (found at {DOTENV_PATH})."
            )

    def get(self, env_var: str) -> str:
        """Returns the value of an environment variable. If the environment variable is valid but not set, attempts to set it."""
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
