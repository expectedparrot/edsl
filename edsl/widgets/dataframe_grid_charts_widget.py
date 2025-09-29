"""
DataFrameGridChartsWidget - Combined AG-Grid and AG-Charts widget for pandas DataFrame

Provides an interactive data grid using AG-Grid Community Edition combined with 
AG-Charts Community Edition for displaying and analyzing pandas DataFrames.
Features include:
- Interactive data grid with sorting, filtering, selection, and pagination
- Multiple chart types (bar, line, scatter, pie, etc.)
- Dynamic chart configuration based on selected data
- Row selection synchronization between grid and charts
- Professional Alpine theme for consistent styling
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


class DataFrameGridChartsWidget(EDSLBaseWidget):
    """Combined interactive data grid and charts widget for pandas DataFrames."""
    
    widget_short_name = "dataframe_grid_charts"
    
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
    
    # Chart configuration
    chart_type = traitlets.Unicode("bar").tag(sync=True)  # bar, line, scatter, pie, area
    chart_x_column = traitlets.Unicode("").tag(sync=True)
    chart_y_column = traitlets.Unicode("").tag(sync=True)
    chart_group_column = traitlets.Unicode("").tag(sync=True)
    chart_title = traitlets.Unicode("Data Visualization").tag(sync=True)
    show_charts = traitlets.Bool(True).tag(sync=True)
    chart_height = traitlets.Int(400).tag(sync=True)
    
    # Chart options for frontend
    chart_options = traitlets.Dict().tag(sync=True)
    
    # Available columns for charting
    numeric_columns = traitlets.List().tag(sync=True)
    categorical_columns = traitlets.List().tag(sync=True)
    datetime_columns = traitlets.List().tag(sync=True)
    
    # Status and error handling  
    status = traitlets.Unicode("ready").tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)
    
    # Selected rows (sent back from frontend)
    selected_rows = traitlets.List().tag(sync=True)
    selected_indices = traitlets.List().tag(sync=True)
    
    # Layout configuration
    layout_mode = traitlets.Unicode("tabs").tag(sync=True)  # tabs, split, grid-only, charts-only

    def __init__(self, dataframe: Optional[pd.DataFrame] = None, **kwargs):
        """
        Initialize the DataFrameGridChartsWidget.
        
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

    @traitlets.observe("chart_type", "chart_x_column", "chart_y_column", "chart_group_column", "chart_title")
    def _on_chart_config_change(self, change):
        """Update chart options when configuration changes."""
        self._update_chart_options()

    def _process_dataframe(self):
        """Process the pandas DataFrame for display in AG-Grid and prepare for charting."""
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
            
            # Analyze columns for charting
            self._analyze_columns(self.dataframe)
            
            # Update traitlets
            self.data = processed_data
            self.columns = column_defs
            
            # Set default chart columns if not set
            self._set_default_chart_columns()
            
            # Update chart options
            self._update_chart_options()
            
            self.status = "ready"
            logger.info(f"Processed DataFrame with {len(self.dataframe)} rows and {len(self.dataframe.columns)} columns")
            
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
            if df_clean[col].dtype == 'object':
                # Convert object columns to strings, handling None/NaN
                df_clean[col] = df_clean[col].astype(str)
                df_clean[col] = df_clean[col].replace(['nan', 'None'], '')
            elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                # Convert datetime to string
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                df_clean[col] = df_clean[col].fillna('')
            elif pd.api.types.is_numeric_dtype(df_clean[col]):
                # Handle numeric NaN values
                df_clean[col] = df_clean[col].fillna(0)  # Use 0 instead of empty string for charts
        
        # Add row index for selection tracking
        df_clean.reset_index(inplace=True)
        if 'index' in df_clean.columns:
            df_clean.rename(columns={'index': '_row_index'}, inplace=True)
        
        # Convert to records
        return df_clean.to_dict('records')

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
        column_defs.append({
            "field": "_row_index",
            "headerName": "Index",
            "hide": True,
            "suppressMenu": True,
            "suppressSorting": True
        })
        
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
                col_def["filter"] = "agNumberColumnFilter" if self.enable_filtering else False
            elif pd.api.types.is_float_dtype(dtype):
                col_def["type"] = "numericColumn"
                col_def["filter"] = "agNumberColumnFilter" if self.enable_filtering else False
                col_def["cellRenderer"] = "agAnimateShowChangeCellRenderer"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                col_def["filter"] = "agDateColumnFilter" if self.enable_filtering else False
            elif pd.api.types.is_bool_dtype(dtype):
                col_def["cellRenderer"] = "agCheckboxCellRenderer"
                col_def["cellEditor"] = "agCheckboxCellEditor"
            else:
                col_def["filter"] = "agTextColumnFilter" if self.enable_filtering else False
            
            column_defs.append(col_def)
        
        return column_defs

    def _analyze_columns(self, df: pd.DataFrame):
        """
        Analyze DataFrame columns to categorize them for charting.
        
        Args:
            df: pandas DataFrame
        """
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []
        
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(str(col))
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                datetime_cols.append(str(col))
            else:
                # Consider categorical if not too many unique values
                if df[col].nunique() <= min(50, len(df) // 2):
                    categorical_cols.append(str(col))
        
        self.numeric_columns = numeric_cols
        self.categorical_columns = categorical_cols
        self.datetime_columns = datetime_cols

    def _set_default_chart_columns(self):
        """Set default chart columns based on available data."""
        if not self.chart_x_column and (self.categorical_columns or self.datetime_columns):
            # Prefer categorical for x-axis, fall back to datetime
            if self.categorical_columns:
                self.chart_x_column = self.categorical_columns[0]
            elif self.datetime_columns:
                self.chart_x_column = self.datetime_columns[0]
        
        if not self.chart_y_column and self.numeric_columns:
            self.chart_y_column = self.numeric_columns[0]

    def _update_chart_options(self):
        """Update chart options for the frontend."""
        if not self.data or not self.chart_x_column or not self.chart_y_column:
            self.chart_options = {}
            return
        
        # Prepare data for charting (use selected data if available, otherwise all data)
        chart_data = self.data if not self.selected_rows else self.selected_rows
        
        if not chart_data:
            self.chart_options = {}
            return
        
        # Basic chart options
        options = {
            "data": chart_data,
            "title": {"text": self.chart_title},
            "series": [],
        }
        
        if self.chart_type == "bar":
            options["series"] = [{
                "type": "bar",
                "xKey": self.chart_x_column,
                "yKey": self.chart_y_column,
            }]
            if self.chart_group_column:
                options["series"][0]["yName"] = self.chart_y_column
                options["series"][0]["stacked"] = False
        
        elif self.chart_type == "line":
            options["series"] = [{
                "type": "line",
                "xKey": self.chart_x_column,
                "yKey": self.chart_y_column,
                "marker": {"enabled": True}
            }]
        
        elif self.chart_type == "scatter":
            options["series"] = [{
                "type": "scatter",
                "xKey": self.chart_x_column,
                "yKey": self.chart_y_column,
            }]
        
        elif self.chart_type == "pie":
            options["series"] = [{
                "type": "pie",
                "angleKey": self.chart_y_column,
                "labelKey": self.chart_x_column,
            }]
        
        elif self.chart_type == "area":
            options["series"] = [{
                "type": "area",
                "xKey": self.chart_x_column,
                "yKey": self.chart_y_column,
            }]
        
        # Add axis configurations
        if self.chart_type not in ["pie"]:
            options["axes"] = [
                {
                    "type": "category" if self.chart_x_column in self.categorical_columns else "number",
                    "position": "bottom",
                    "title": {"text": self.chart_x_column}
                },
                {
                    "type": "number",
                    "position": "left", 
                    "title": {"text": self.chart_y_column}
                }
            ]
        
        self.chart_options = options

    def _clear_data(self):
        """Clear all data from the widget."""
        self.data = []
        self.columns = []
        self.selected_rows = []
        self.selected_indices = []
        self.chart_options = {}
        self.numeric_columns = []
        self.categorical_columns = []
        self.datetime_columns = []

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
        self._update_chart_options()  # Update charts to use all data

    def configure_grid(self, 
                      page_size: Optional[int] = None,
                      enable_sorting: Optional[bool] = None,
                      enable_filtering: Optional[bool] = None, 
                      enable_selection: Optional[bool] = None,
                      selection_mode: Optional[str] = None):
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

    def configure_chart(self,
                       chart_type: Optional[str] = None,
                       x_column: Optional[str] = None,
                       y_column: Optional[str] = None,
                       group_column: Optional[str] = None,
                       title: Optional[str] = None,
                       height: Optional[int] = None):
        """
        Configure chart display options.
        
        Args:
            chart_type: Type of chart ('bar', 'line', 'scatter', 'pie', 'area')
            x_column: Column for x-axis
            y_column: Column for y-axis  
            group_column: Column for grouping/coloring
            title: Chart title
            height: Chart height in pixels
        """
        if chart_type is not None:
            self.chart_type = chart_type
        if x_column is not None:
            self.chart_x_column = x_column
        if y_column is not None:
            self.chart_y_column = y_column
        if group_column is not None:
            self.chart_group_column = group_column
        if title is not None:
            self.chart_title = title
        if height is not None:
            self.chart_height = height

    def set_layout_mode(self, mode: str):
        """
        Set the layout mode for the widget.
        
        Args:
            mode: Layout mode ('tabs', 'split', 'grid-only', 'charts-only')
        """
        if mode in ['tabs', 'split', 'grid-only', 'charts-only']:
            self.layout_mode = mode
        else:
            raise ValueError(f"Invalid layout mode: {mode}")