class ConfigurationError(Exception):
    """Base exception for errors."""

    pass


class InvalidEnvironmentVariableError(ConfigurationError):
    """Raised when an environment variable is invalid."""

    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when an expected environment variable is missing."""

    pass
