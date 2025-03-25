"""Mixin class for ggplot2 plotting."""

import subprocess
import tempfile
from typing import Optional


class GGPlot:
    """A class to handle ggplot2 plot display and saving."""
    
    def __init__(self, r_code: str, width: float = 6, height: float = 4):
        """Initialize with R code and dimensions."""
        self.r_code = r_code
        self.width = width
        self.height = height
        self._svg_data = None
        self._saved = False  # Track if the plot was saved
        
    def _execute_r_code(self, save_command: str = ""):
        """Execute R code with optional save command."""
        full_r_code = self.r_code + save_command
        
        result = subprocess.run(
            ["Rscript", "-"],
            input=full_r_code,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            if result.returncode == 127:
                from ..exceptions import DatasetRuntimeError
                raise DatasetRuntimeError(
                    "Rscript is probably not installed. Please install R from https://cran.r-project.org/"
                )
            else:
                from ..exceptions import DatasetRuntimeError
                raise DatasetRuntimeError(
                    f"An error occurred while running Rscript: {result.stderr}"
                )

        if result.stderr:
            print("Error in R script:", result.stderr)
            
        return result
        
    def save(self, filename: str):
        """Save the plot to a file."""
        format = filename.split('.')[-1].lower()
        if format not in ['svg', 'png']:
            from ..exceptions import DatasetValueError
            raise DatasetValueError("Only 'svg' and 'png' formats are supported")
            
        save_command = f'\nggsave("{filename}", plot = last_plot(), width = {self.width}, height = {self.height}, device = "{format}")'
        self._execute_r_code(save_command)
        
        self._saved = True
        print(f"File saved to: {filename}")
        return None  # Return None instead of self
        
    def _repr_html_(self):
        """Display the plot in a Jupyter notebook."""
        # Don't display if the plot was saved
        if self._saved:
            return None
            
        
        # Generate SVG if we haven't already
        if self._svg_data is None:
            # Create temporary SVG file
            with tempfile.NamedTemporaryFile(suffix='.svg') as tmp:
                save_command = f'\nggsave("{tmp.name}", plot = last_plot(), width = {self.width}, height = {self.height}, device = "svg")'
                self._execute_r_code(save_command)
                with open(tmp.name, 'r') as f:
                    self._svg_data = f.read()
                    
        return self._svg_data

class GGPlotMethod:

    def __init__(self, results):
        """Initialize the GGPlotMethod with results.
        
        Args:
            results: A Results or Dataset object.
        """
        self.results = results
    
    """Mixin class for ggplot2 plotting."""

    def ggplot2(
        self,
        ggplot_code: str,
        shape="wide",
        sql: str = None,
        remove_prefix: bool = True,
        debug: bool = False,
        height=4,
        width=6,
        factor_orders: Optional[dict] = None,
    ):
        """Create a ggplot2 plot from a DataFrame.

        Returns a GGPlot object that can be displayed in a notebook or saved to a file.

        :param ggplot_code: The ggplot2 code to execute.
        :param shape: The shape of the data in the DataFrame (wide or long).
        :param sql: The SQL query to execute beforehand to manipulate the data.
        :param remove_prefix: Whether to remove the prefix from the column names.
        :param debug: Whether to print the R code instead of executing it.
        :param height: The height of the plot in inches.
        :param width: The width of the plot in inches.
        :param factor_orders: A dictionary of factor columns and their order.
        """
        if sql is None:
            sql = "select * from self"

        if shape == "long":
            df = self.results.sql(sql, shape="long")
        elif shape == "wide":
            df = self.results.sql(sql, remove_prefix=remove_prefix)

        # Convert DataFrame to CSV format
        csv_data = df.to_csv().text

        # Embed the CSV data within the R script
        csv_data_escaped = csv_data.replace("\n", "\\n").replace("'", "\\'")
        read_csv_code = f"self <- read.csv(text = '{csv_data_escaped}', sep = ',')\n"

        if factor_orders is not None:
            for factor, order in factor_orders.items():
                level_string = ", ".join([f'"{x}"' for x in order])
                read_csv_code += (
                    f"self${factor} <- factor(self${factor}, levels=c({level_string}))"
                )
                read_csv_code += "\n"

        # Load ggplot2 library and combine all R script parts
        full_r_code = "library(ggplot2)\n" + read_csv_code + ggplot_code

        if debug:
            print(full_r_code)
            return

        return GGPlot(full_r_code, width=width, height=height)

    def _display_plot(self, filename: str, width: float, height: float):
        """Display the plot in the notebook or open in system viewer if running from terminal."""
        try:
            # Try to import IPython-related modules
            import matplotlib.pyplot as plt
            import matplotlib.image as mpimg
            from IPython import get_ipython

            # Check if we're in a notebook environment
            if get_ipython() is not None:
                if filename.endswith(".png"):
                    img = mpimg.imread(filename)
                    plt.figure(figsize=(width, height))
                    plt.imshow(img)
                    plt.axis("off")
                    plt.show()
                elif filename.endswith(".svg"):
                    from IPython.display import SVG, display
                    display(SVG(filename=filename))
                else:
                    print("Unsupported file format. Please provide a PNG or SVG file.")
                return

        except ImportError:
            pass

        # If we're not in a notebook or imports failed, open with system viewer
        import platform
        import os
        
        system = platform.system()
        if system == 'Darwin':       # macOS
            if filename.endswith('.svg'):
                subprocess.run(['open', '-a', 'Preview', filename])
            else:
                subprocess.run(['open', filename])
        elif system == 'Linux':
            subprocess.run(['xdg-open', filename])
        elif system == 'Windows':
            os.startfile(filename)
        else:
            print(f"File saved to: {filename}")
