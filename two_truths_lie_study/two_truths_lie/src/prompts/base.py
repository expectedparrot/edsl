"""Base prompt class for all prompts."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BasePrompt(ABC):
    """Abstract base class for all prompts.

    All prompts should inherit from this class and implement
    the render() method to produce the final prompt text.
    """

    @abstractmethod
    def render(self) -> str:
        """Render the prompt to a string.

        Returns:
            The fully rendered prompt text.
        """
        pass

    def __str__(self) -> str:
        """String representation is the rendered prompt."""
        return self.render()

    def __repr__(self) -> str:
        """Repr shows class name and key attributes."""
        return f"{self.__class__.__name__}()"
