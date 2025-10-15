"""
Reports module for EDSL visualization and reporting.

This module requires optional dependencies. Install with:
    pip install edsl[viz]
"""

# Check for required dependencies
_missing_deps = []
try:
    import altair
except ImportError:
    _missing_deps.append("altair")

try:
    import nbformat
except ImportError:
    _missing_deps.append("nbformat")

try:
    import nbclient
except ImportError:
    _missing_deps.append("nbclient")

try:
    import yaml
except ImportError:
    _missing_deps.append("pyyaml")

if _missing_deps:
    raise ImportError(
        f"The edsl.reports module requires optional dependencies that are not installed: {', '.join(_missing_deps)}\n"
        f"Please install them with: pip install edsl[viz]"
    )

from .themes import ThemeFinder, cached_property
from .utilities import semantic_columns, create_magazine_quote_layout
from .analyzer import (
    AnalyzeQuestion,
    AnalyzeQuestionMultipleChoice,
    AnalyzeQuestionFreeText,
    create_survey_bar_chart,
    create_analyzer
)
from .report import Report
from .charts import (
    ChartOutput,
    BarChartOutput,
    ScatterPlotOutput,
    HistogramOutput,
    FacetedBarChartOutput,
    FacetedHistogramOutput,
    HeatmapChartOutput,
    BoxPlotOutput,
    WeightedCheckboxBarChart,
    ThemeFinderOutput,
    PNGLocation
)
from .tables import (
    TableOutput,
    SummaryStatisticsTable,
    FacetedSummaryStatsTable,
    CrossTabulationTable,
    AllResponsesTable,
    RegressionTable,
    ChiSquareTable,
    ResponsesWithThemesTable
)
from .research import Research
from .warning_utils import print_warning, print_info, print_error, print_success, setup_warning_capture

# Setup warning capture when the package is imported
setup_warning_capture()

__all__ = [
    "ThemeFinder",
    "cached_property",
    "semantic_columns",
    "create_magazine_quote_layout",
    "AnalyzeQuestion",
    "AnalyzeQuestionMultipleChoice",
    "AnalyzeQuestionFreeText",
    "create_survey_bar_chart",
    "create_analyzer",
    "Report",
    "PNGLocation",
    "ChartOutput", 
    "BarChartOutput", 
    "ScatterPlotOutput", 
    "HistogramOutput", 
    "FacetedBarChartOutput", 
    "FacetedHistogramOutput", 
    "HeatmapChartOutput", 
    "BoxPlotOutput",
    "WeightedCheckboxBarChart",
    "ThemeFinderOutput",
    "TableOutput", 
    "SummaryStatisticsTable", 
    "FacetedSummaryStatsTable", 
    "CrossTabulationTable", 
    "AllResponsesTable", 
    "RegressionTable", 
    "ChiSquareTable",
    "ResponsesWithThemesTable",
    "Research",
    "print_warning",
    "print_info", 
    "print_error",
    "print_success",
    "setup_warning_capture"
]
