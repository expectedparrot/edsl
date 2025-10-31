# Import all classes directly to maintain the original API
from .conjure import Conjure
from .utilities import setup_warning_filter

# Set up rich warning formatting when the package is imported
setup_warning_filter()

# Also import any other classes that might be needed
# (You may need to expand this based on what users of your package require)

__all__ = ["Conjure"]
