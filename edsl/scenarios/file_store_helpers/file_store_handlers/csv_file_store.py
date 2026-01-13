import csv
import tempfile
from ..file_methods import FileMethods


class CsvMethods(FileMethods):
    suffix = "csv"

    def to_scenario_list(self):
        """Create a ScenarioList from the CSV file using pure Python."""
        from ...scenario_list import ScenarioList
        from ...scenario import Scenario

        with open(self.path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            scenarios = [Scenario(dict(row)) for row in reader]
        return ScenarioList(scenarios)

    def view_system(self):
        import os
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
                print(f"Error opening CSV: {e}")
        else:
            print("CSV file was not found.")

    def view_notebook(self):
        """Display CSV in notebook. Uses pandas if available, falls back to HTML table."""
        from IPython.display import display, HTML

        try:
            import pandas as pd

            df = pd.read_csv(self.path)
            display(df)
        except ImportError:
            # Fallback to pure Python HTML table
            with open(self.path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                display(HTML("<p>Empty CSV file</p>"))
                return

            # Build HTML table
            html = ['<table border="1" style="border-collapse: collapse;">']
            # Header row
            html.append("<tr>")
            for cell in rows[0]:
                html.append(
                    f'<th style="padding: 5px; background: #f0f0f0;">{cell}</th>'
                )
            html.append("</tr>")
            # Data rows
            for row in rows[1:]:
                html.append("<tr>")
                for cell in row:
                    html.append(f'<td style="padding: 5px;">{cell}</td>')
                html.append("</tr>")
            html.append("</table>")

            display(HTML("".join(html)))

    def example(self):
        """Create an example CSV file using pure Python."""
        data = [
            {"A": "1", "B": "4"},
            {"A": "2", "B": "5"},
            {"A": "3", "B": "6"},
        ]
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["A", "B"])
            writer.writeheader()
            writer.writerows(data)
            return f.name

    def to_pandas(self):
        """
        Convert the CSV file to a pandas DataFrame.

        Returns:
            pandas.DataFrame: The data from the CSV as a DataFrame

        Raises:
            ImportError: If pandas is not installed
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_pandas(). "
                "Install with: pip install edsl[pandas] or pip install pandas"
            )

        return pd.read_csv(self.path)
