"""Mixin class for ggplot2 plotting."""

import subprocess
import tempfile
from typing import Optional


class ResultsGGMixin:
    """Mixin class for ggplot2 plotting."""

    def ggplot2(
        self,
        ggplot_code: str,
        filename: str = None,
        shape="wide",
        sql: str = None,
        remove_prefix: bool = True,
        debug: bool = False,
        height=4,
        width=6,
        format="svg",
        factor_orders: Optional[dict] = None,
    ):
        """Create a ggplot2 plot from a DataFrame.

        :param ggplot_code: The ggplot2 code to execute.
        :param filename: The filename to save the plot to.
        :param shape: The shape of the data in the DataFrame (wide or long).
        :param sql: The SQL query to execute beforehand to manipulate the data.
        :param remove_prefix: Whether to remove the prefix from the column names.
        :param debug: Whether to print the R code instead of executing it.
        :param height: The height of the plot in inches.
        :param width: The width of the plot in inches.
        :param format: The format to save the plot in (png or svg).
        :param factor_orders: A dictionary of factor columns and their order.
        """

        if sql == None:
            sql = "select * from self"

        if shape == "long":
            df = self.sql(sql, shape="long")
        elif shape == "wide":
            df = self.sql(sql, shape="wide", remove_prefix=remove_prefix)

        # Convert DataFrame to CSV format
        csv_data = df.to_csv(index=False)

        # Embed the CSV data within the R script
        csv_data_escaped = csv_data.replace("\n", "\\n").replace("'", "\\'")
        read_csv_code = f"self <- read.csv(text = '{csv_data_escaped}', sep = ',')\n"

        if factor_orders is not None:
            for factor, order in factor_orders.items():
                # read_csv_code += f"""self${{{factor}}} <- factor(self${{{factor}}}, levels=c({','.join(['"{}"'.format(x) for x in order])}))"""

                level_string = ", ".join([f'"{x}"' for x in order])
                read_csv_code += (
                    f"self${factor} <- factor(self${factor}, levels=c({level_string}))"
                )
                read_csv_code += "\n"

        # Load ggplot2 library
        load_ggplot2 = "library(ggplot2)\n"

        # Check if a filename is provided for the plot, if not create a temporary one
        if not filename:
            filename = tempfile.mktemp(suffix=f".{format}")

        # Combine all R script parts
        full_r_code = load_ggplot2 + read_csv_code + ggplot_code

        # Add command to save the plot to a file
        full_r_code += f'\nggsave("{filename}", plot = last_plot(), width = {width}, height = {height}, device = "{format}")'

        if debug:
            print(full_r_code)
            return

        result = subprocess.run(
            ["Rscript", "-"],
            input=full_r_code,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            if result.returncode == 127:  # 'command not found'
                raise RuntimeError(
                    "Rscript is probably not installed. Please install R from https://cran.r-project.org/"
                )
            else:
                raise RuntimeError(
                    f"An error occurred while running Rscript: {result.stderr}"
                )

        if result.stderr:
            print("Error in R script:", result.stderr)
        else:
            self._display_plot(filename, width, height)

    def _display_plot(self, filename: str, width: float, height: float):
        """Display the plot in the notebook."""
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg

        if filename.endswith(".png"):
            img = mpimg.imread(filename)
            plt.figure(
                figsize=(width, height)
            )  # Set the figure size (width, height) in inches
            plt.imshow(img)
            plt.axis("off")
            plt.show()
        elif filename.endswith(".svg"):
            from IPython.display import SVG, display

            display(SVG(filename=filename))
        else:
            print("Unsupported file format. Please provide a PNG or SVG file.")
