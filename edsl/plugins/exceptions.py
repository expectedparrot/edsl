"""Exceptions for the plugins module."""

from ..base.base_exception import BaseException

class PluginException(BaseException):
    """Base exception for all plugin-related errors."""
    relevant_doc = "https://docs.expectedparrot.com/plugins.html"

class PluginNotFoundError(PluginException):
    """Raised when a requested plugin is not found."""
    pass

class PluginInstallationError(PluginException):
    """Raised when a plugin installation fails."""
    pass

class GitHubRepoError(PluginInstallationError):
    """Raised when there's an error with a GitHub repository."""
    pass

class InvalidPluginError(PluginException):
    """Raised when a plugin is invalid or does not implement required hooks."""
    pass

class PluginDependencyError(PluginInstallationError):
    """Raised when plugin dependencies cannot be satisfied."""
    pass

class PluginMethodError(PluginException):
    """Raised when there is an error with a plugin method."""
    pass