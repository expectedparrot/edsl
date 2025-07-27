"""
EDSL Widgets Package

This package contains interactive widgets for visualizing and working with EDSL objects.
"""

from .base_widget import EDSLBaseWidget
from .results_viewer import ResultsViewerWidget

__all__ = [
    'EDSLBaseWidget',
    'ResultsViewerWidget',
] 