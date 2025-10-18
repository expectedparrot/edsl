"""
DataFrameGridWidget - AG-Grid widget for pandas DataFrame display

Provides an interactive data grid using AG-Grid Community Edition for displaying
and manipulating pandas DataFrames with sorting, filtering, selection, and pagination.
Features include:
- Column sorting and filtering
- Row selection (single or multiple)
- Pagination with configurable page size
- Resizable columns
- Professional grid appearance with Alpine theme
"""

import traitlets
import pandas as pd
from typing import Dict, List, Any, Optional
import logging

try:
    from .base_widget import EDSLBaseWidget
except ImportError:
    from base_widget import EDSLBaseWidget

logger = logging.getLogger(__name__)


class DataFrameGridWidget(EDSLBaseWidget):
    """Interactive data grid widget for pandas DataFrames using AG-Grid."""

    widget_short_name = "dataframe_grid"

    # Core traitlets for data
    dataframe = traitlets.Any(allow_none=True).tag(sync=False)
    data = traitlets.List().tag(sync=True)
    columns = traitlets.List().tag(sync=True)

    # Grid configuration
    page_size = traitlets.Int(50).tag(sync=True)
    enable_sorting = traitlets.Bool(True).tag(sync=True)
    enable_filtering = traitlets.Bool(True).tag(sync=True)
    enable_selection = traitlets.Bool(True).tag(sync=True)
    selection_mode = traitlets.Unicode("multiple").tag(sync=True)  # single, multiple

    # Status and error handling
    status = traitlets.Unicode("ready").tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)

    # Selected rows (sent back from frontend)
    selected_rows = traitlets.List().tag(sync=True)
    selected_indices = traitlets.List().tag(sync=True)

    def __init__(self, dataframe: Optional[pd.DataFrame] = None, **kwargs):
        """
        Initialize the DataFrameGridWidget.

        Args:
            dataframe: pandas DataFrame to display
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        if dataframe is not None:
            self.dataframe = dataframe

    @traitlets.observe("dataframe")
    def _on_dataframe_change(self, change):
        """Update widget data when dataframe changes."""
        if change["new"] is not None:
            self._process_dataframe()

    def _process_dataframe(self):
        """Process the pandas DataFrame for display in AG-Grid."""
        if self.dataframe is None:
            self._clear_data()
            return

        try:
            self.status = "processing"
            self.error_message = ""

            if not isinstance(self.dataframe, pd.DataFrame):
                raise ValueError("Input must be a pandas DataFrame")

            if self.dataframe.empty:
                self._clear_data()
                self.error_message = "DataFrame is empty"
                self.status = "error"
                return

            # Prepare data for AG-Grid
            processed_data = self._prepare_data(self.dataframe)
            column_defs = self._prepare_columns(self.dataframe)

            # Update traitlets
            self.data = processed_data
            self.columns = column_defs

            self.status = "ready"
            logger.info(
                f"Processed DataFrame with {len(self.dataframe)} rows and {len(self.dataframe.columns)} columns"
            )

        except Exception as e:
            logger.error(f"Error processing DataFrame: {e}")
            self.error_message = str(e)
            self.status = "error"
            self._clear_data()

    def _prepare_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Prepare DataFrame data for AG-Grid.

        Args:
            df: pandas DataFrame

        Returns:
            List of dictionaries representing rows
        """
        # Handle missing values
        df_clean = df.copy()

        # Convert various data types to JSON-serializable formats
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":
                # Convert object columns to strings, handling None/NaN
                df_clean[col] = df_clean[col].astype(str)
                df_clean[col] = df_clean[col].replace(["nan", "None"], "")
            elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                # Convert datetime to string
                df_clean[col] = df_clean[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                df_clean[col] = df_clean[col].fillna("")
            elif pd.api.types.is_numeric_dtype(df_clean[col]):
                # Handle numeric NaN values
                df_clean[col] = df_clean[col].fillna("")

        # Add row index for selection tracking
        df_clean.reset_index(inplace=True)
        if "index" in df_clean.columns:
            df_clean.rename(columns={"index": "_row_index"}, inplace=True)

        # Convert to records
        return df_clean.to_dict("records")

    def _prepare_columns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Prepare column definitions for AG-Grid.

        Args:
            df: pandas DataFrame

        Returns:
            List of AG-Grid column definitions
        """
        column_defs = []

        # Add row index column (hidden by default, used for selection)
        column_defs.append(
            {
                "field": "_row_index",
                "headerName": "Index",
                "hide": True,
                "suppressMenu": True,
                "suppressSorting": True,
            }
        )

        for col in df.columns:
            col_def = {
                "field": str(col),
                "headerName": str(col),
                "sortable": self.enable_sorting,
                "filter": self.enable_filtering,
                "resizable": True,
            }

            # Set column type and formatting based on pandas dtype
            dtype = df[col].dtype

            if pd.api.types.is_integer_dtype(dtype):
                col_def["type"] = "numericColumn"
                col_def["filter"] = (
                    "agNumberColumnFilter" if self.enable_filtering else False
                )
            elif pd.api.types.is_float_dtype(dtype):
                col_def["type"] = "numericColumn"
                col_def["filter"] = (
                    "agNumberColumnFilter" if self.enable_filtering else False
                )
                col_def["cellRenderer"] = "agAnimateShowChangeCellRenderer"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                col_def["filter"] = (
                    "agDateColumnFilter" if self.enable_filtering else False
                )
            elif pd.api.types.is_bool_dtype(dtype):
                col_def["cellRenderer"] = "agCheckboxCellRenderer"
                col_def["cellEditor"] = "agCheckboxCellEditor"
            else:
                col_def["filter"] = (
                    "agTextColumnFilter" if self.enable_filtering else False
                )

            column_defs.append(col_def)

        return column_defs

    def _clear_data(self):
        """Clear all data from the widget."""
        self.data = []
        self.columns = []
        self.selected_rows = []
        self.selected_indices = []

    def set_dataframe(self, dataframe: pd.DataFrame):
        """
        Set a new DataFrame to display.

        Args:
            dataframe: pandas DataFrame to display
        """
        self.dataframe = dataframe

    def get_selected_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Get a DataFrame containing only the selected rows.

        Returns:
            pandas DataFrame with selected rows, or None if no selection
        """
        if not self.selected_indices or self.dataframe is None:
            return None

        try:
            return self.dataframe.iloc[self.selected_indices]
        except IndexError:
            logger.warning("Selected indices are out of range")
            return None

    def clear_selection(self):
        """Clear the current selection."""
        self.selected_rows = []
        self.selected_indices = []

    def configure_grid(
        self,
        page_size: Optional[int] = None,
        enable_sorting: Optional[bool] = None,
        enable_filtering: Optional[bool] = None,
        enable_selection: Optional[bool] = None,
        selection_mode: Optional[str] = None,
    ):
        """
        Configure grid display options.

        Args:
            page_size: Number of rows per page
            enable_sorting: Enable column sorting
            enable_filtering: Enable column filtering
            enable_selection: Enable row selection
            selection_mode: Selection mode ('single' or 'multiple')
        """
        if page_size is not None:
            self.page_size = page_size
        if enable_sorting is not None:
            self.enable_sorting = enable_sorting
        if enable_filtering is not None:
            self.enable_filtering = enable_filtering
        if enable_selection is not None:
            self.enable_selection = enable_selection
        if selection_mode is not None:
            self.selection_mode = selection_mode

        # Reprocess data to apply new configuration
        if self.dataframe is not None:
            self._process_dataframe()
