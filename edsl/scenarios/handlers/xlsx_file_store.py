import tempfile
from ..file_methods import FileMethods
import os


def _require_pandas():
    """Helper to check pandas availability with helpful error message."""
    try:
        import pandas as pd

        return pd
    except ImportError:
        raise ImportError(
            "pandas is required for Excel file operations. "
            "Install with: pip install edsl[pandas] or pip install pandas openpyxl"
        )


class XlsxMethods(FileMethods):
    suffix = "xlsx"

    def to_scenario_list(self):
        from ..scenario_list import ScenarioList

        pandas_df = self.to_pandas()
        return ScenarioList.from_source("pandas", pandas_df)

    def extract_text(self):
        """Extract text content from Excel file."""
        pd = _require_pandas()

        # Read all sheets from the Excel file
        excel_file = pd.read_excel(self.path, sheet_name=None)

        text_content = []
        for sheet_name, df in excel_file.items():
            text_content.append(f"Sheet: {sheet_name}")
            # Convert DataFrame to string representation
            text_content.append(df.to_string())
            text_content.append("")  # Empty line between sheets

        return "\n".join(text_content)

    def view_system(self):
        import subprocess

        if os.path.exists(self.path):
            try:
                if (os_name := os.name) == "posix":
                    subprocess.run(["open", self.path], check=True)  # macOS
                elif os_name == "nt":
                    os.startfile(self.path)  # Windows
                else:
                    subprocess.run(["xdg-open", self.path], check=True)  # Linux
            except Exception as e:
                print(f"Error opening Excel file: {e}")
        else:
            print("Excel file was not found.")

    def view_notebook(self):
        pd = _require_pandas()
        from IPython.display import display, HTML

        # Read all sheets from the Excel file
        excel_file = pd.read_excel(self.path, sheet_name=None)

        # Display each sheet
        for sheet_name, df in excel_file.items():
            display(HTML(f"<h3>Sheet: {sheet_name}</h3>"))
            display(df)

    def example(self):
        pd = _require_pandas()

        # Create sample data
        data = {
            "Name": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "City": ["New York", "London", "Tokyo"],
        }
        df = pd.DataFrame(data)

        # Create a temporary Excel file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False)

        return tmp.name

    def to_pandas(self):
        """
        Convert the Excel file to a pandas DataFrame.

        Returns:
            dict: Dictionary of sheet names to DataFrames, or single DataFrame if only one sheet

        Raises:
            ImportError: If pandas is not installed
        """
        pd = _require_pandas()

        excel_file = pd.read_excel(self.path, sheet_name=None)

        # If only one sheet, return the DataFrame directly
        if len(excel_file) == 1:
            return next(iter(excel_file.values()))

        # Otherwise return the dictionary of sheets
        return excel_file


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    from ..file_store import FileStore

    example_fs = FileStore(path=XlsxMethods().example())
    pd = example_fs.to_pandas()

    sl = example_fs.to_scenario_list()
    print(sl)
