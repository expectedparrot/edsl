"""
Vibes Method Handler Registrations

This package contains handler classes that register vibes methods with the
vibes registry system. Each handler class inherits from VibesHandlerBase
and is automatically registered via the RegisterVibesMethodsMeta metaclass.

Available Handlers:
- FromVibesHandler: Registers Survey.from_vibes() method
- VibeEditHandler: Registers Survey.vibe_edit() method
- VibeAddHandler: Registers Survey.vibe_add() method
- VibeDescribeHandler: Registers Survey.vibe_describe() method

All handlers are automatically imported and registered when this package
is imported, ensuring they are available for dispatch.
"""

# Import all handlers to trigger registration
try:
    from .from_vibes_handler import FromVibesHandler
    from .vibe_edit_handler import VibeEditHandler
    from .vibe_add_handler import VibeAddHandler
    from .vibe_describe_handler import VibeDescribeHandler
except ImportError:
    from from_vibes_handler import FromVibesHandler
    from vibe_edit_handler import VibeEditHandler
    from vibe_add_handler import VibeAddHandler
    from vibe_describe_handler import VibeDescribeHandler

__all__ = [
    "FromVibesHandler",
    "VibeEditHandler",
    "VibeAddHandler",
    "VibeDescribeHandler",
]