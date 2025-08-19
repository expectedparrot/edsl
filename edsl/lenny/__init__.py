# edsl/lenny/__init__.py

import warnings
import sys

# First try to import from the submodule location
try:
    from .src.lenny import (
        ThemeFinder,
        cached_property,
        semantic_columns,
        create_magazine_quote_layout,
        AnalyzeQuestion,
        AnalyzeQuestionMultipleChoice,
        AnalyzeQuestionFreeText,
        create_survey_bar_chart,
        create_analyzer,
        Report,
        PNGLocation,
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
        TableOutput,
        SummaryStatisticsTable,
        FacetedSummaryStatsTable,
        CrossTabulationTable,
        AllResponsesTable,
        RegressionTable,
        ChiSquareTable,
        ResponsesWithThemesTable,
        Research,
        print_warning,
        print_info,
        print_error,
        print_success,
        setup_warning_capture,
    )

    # Set up warning capture when the package is imported
    setup_warning_capture()

    _LENNY_AVAILABLE = True
    _LENNY_SOURCE = "submodule"

except ImportError:
    # Submodule not found, try importing as standalone package
    try:
        from lenny import (
            ThemeFinder,
            cached_property,
            semantic_columns,
            create_magazine_quote_layout,
            AnalyzeQuestion,
            AnalyzeQuestionMultipleChoice,
            AnalyzeQuestionFreeText,
            create_survey_bar_chart,
            create_analyzer,
            Report,
            PNGLocation,
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
            TableOutput,
            SummaryStatisticsTable,
            FacetedSummaryStatsTable,
            CrossTabulationTable,
            AllResponsesTable,
            RegressionTable,
            ChiSquareTable,
            ResponsesWithThemesTable,
            Research,
            print_warning,
            print_info,
            print_error,
            print_success,
            setup_warning_capture,
        )

        # Set up warning capture when the package is imported
        setup_warning_capture()

        _LENNY_AVAILABLE = True
        _LENNY_SOURCE = "standalone"

    except ImportError:
        # Neither method worked - provide helpful warning
        _LENNY_AVAILABLE = False
        _LENNY_SOURCE = None

        warnings.warn(
            "The 'edsl-lenny' functionality is not available. "
            "You have two options:\n"
            "1. If you cloned the edsl repository, initialize the submodule:\n"
            "   git submodule update --init --recursive\n"
            "2. Or install it as a standalone package:\n"
            "   pip install git+https://github.com/expectedparrot/edsl-lenny.git\n"
            "   Note: If installed standalone, import directly as 'from lenny import ...'",
            ImportWarning,
            stacklevel=2,
        )

        # Create placeholder classes that raise helpful errors
        class ThemeFinder:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Lenny is not available. Please either:\n"
                    "1. Initialize the submodule: git submodule update --init --recursive\n"
                    "2. Install standalone: pip install git+https://github.com/expectedparrot/edsl-lenny.git\n"
                    "   (Note: standalone installation requires 'from lenny import ...')"
                )

        class AnalyzeQuestion:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Lenny is not available. Please either:\n"
                    "1. Initialize the submodule: git submodule update --init --recursive\n"
                    "2. Install standalone: pip install git+https://github.com/expectedparrot/edsl-lenny.git\n"
                    "   (Note: standalone installation requires 'from lenny import ...')"
                )

        class Report:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Lenny is not available. Please either:\n"
                    "1. Initialize the submodule: git submodule update --init --recursive\n"
                    "2. Install standalone: pip install git+https://github.com/expectedparrot/edsl-lenny.git\n"
                    "   (Note: standalone installation requires 'from lenny import ...')"
                )

        # Create placeholder functions
        def setup_warning_capture():
            pass  # No-op when not available

        def print_warning(*args, **kwargs):
            pass  # No-op when not available

        def print_info(*args, **kwargs):
            pass  # No-op when not available

        def print_error(*args, **kwargs):
            pass  # No-op when not available

        def print_success(*args, **kwargs):
            pass  # No-op when not available

        # Create other placeholder items
        cached_property = None
        semantic_columns = None
        create_magazine_quote_layout = None
        AnalyzeQuestionMultipleChoice = AnalyzeQuestion
        AnalyzeQuestionFreeText = AnalyzeQuestion
        create_survey_bar_chart = None
        create_analyzer = None
        PNGLocation = None
        ChartOutput = None
        BarChartOutput = None
        ScatterPlotOutput = None
        HistogramOutput = None
        FacetedBarChartOutput = None
        FacetedHistogramOutput = None
        HeatmapChartOutput = None
        BoxPlotOutput = None
        WeightedCheckboxBarChart = None
        ThemeFinderOutput = None
        TableOutput = None
        SummaryStatisticsTable = None
        FacetedSummaryStatsTable = None
        CrossTabulationTable = None
        AllResponsesTable = None
        RegressionTable = None
        ChiSquareTable = None
        ResponsesWithThemesTable = None
        Research = None

# Export the same interface regardless
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
    "setup_warning_capture",
    "_LENNY_AVAILABLE",
    "_LENNY_SOURCE",
]
