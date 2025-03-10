import tempfile
from ..file_methods import FileMethods

class CsvMethods(FileMethods):
    suffix = "csv"

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
        import pandas as pd
        from IPython.display import display

        df = pd.read_csv(self.path)
        display(df)

    def example(self):
        import pandas as pd

        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            df.to_csv(f.name, index=False)
        return f.name

    def to_pandas(self):
        """
        Convert the CSV file to a pandas DataFrame.

        Returns:
            pandas.DataFrame: The data from the CSV as a DataFrame
        """
        import pandas as pd

        return pd.read_csv(self.path)
