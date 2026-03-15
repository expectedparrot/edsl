"""Extra/optional functionality for Results objects.

This package contains standalone classes that operate on Results objects
but are not part of the core Results API.
"""

from .results_splitter import ResultsSplitter, AgentListSplit
from .results_scorer import ResultsScorer
from .results_augmenter import ResultsAugmenter
