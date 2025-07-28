# edsl/conjure/__init__.py

import warnings
import sys

# First try to import from the submodule location
try:
    from .src.conjure import Conjure
    from .src.conjure.utilities import setup_warning_filter
    
    # Set up rich warning formatting when the package is imported
    setup_warning_filter()
    
    _CONJURE_AVAILABLE = True
    _CONJURE_SOURCE = "submodule"
    
except ImportError:
    # Submodule not found, try importing as standalone package
    try:
        from conjure import Conjure
        from conjure.utilities import setup_warning_filter
        
        # Set up rich warning formatting when the package is imported
        setup_warning_filter()
        
        _CONJURE_AVAILABLE = True
        _CONJURE_SOURCE = "standalone"
        
    except ImportError:
        # Neither method worked - provide helpful warning
        _CONJURE_AVAILABLE = False
        _CONJURE_SOURCE = None
        
        warnings.warn(
            "The 'edsl-conjure' functionality is not available. "
            "You have two options:\n"
            "1. If you cloned the edsl repository, initialize the submodule:\n"
            "   git submodule update --init --recursive\n"
            "2. Or install it as a standalone package:\n"
            "   pip install git+https://github.com/expectedparrot/edsl-conjure.git\n"
            "   Note: If installed standalone, import directly as 'from conjure import Conjure'",
            ImportWarning,
            stacklevel=2
        )
        
        # Create placeholder classes that raise helpful errors
        class Conjure:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Conjure is not available. Please either:\n"
                    "1. Initialize the submodule: git submodule update --init --recursive\n"
                    "2. Install standalone: pip install git+https://github.com/expectedparrot/edsl-conjure.git\n"
                    "   (Note: standalone installation requires 'from conjure import Conjure')"
                )
        
        def setup_warning_filter():
            pass  # No-op when not available

# Export the same interface regardless
__all__ = ["Conjure", "setup_warning_filter", "_CONJURE_AVAILABLE", "_CONJURE_SOURCE"]
