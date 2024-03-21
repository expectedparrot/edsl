"""Mixin class for ggplot2 plotting."""
import subprocess
import pandas as pd
import tempfile
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


class ResultsGGMixin:
    """Mixin class for ggplot2 plotting."""

    def ggplot2(self, ggplot_code: str, filename=None, shape="wide"):
        """Create a ggplot2 plot from a DataFrame."""
        # Fetching DataFrame based on shape
        if shape == "long":
            df = self.sql("select * from self", shape="long")
        elif shape == "wide":
            df = self.sql("select * from self", shape="wide", remove_prefix=True)

        # Convert DataFrame to CSV format
        csv_data = df.to_csv(index=False)

        # Embed the CSV data within the R script
        csv_data_escaped = csv_data.replace("\n", "\\n").replace("'", "\\'")
        read_csv_code = f"self <- read.csv(text = '{csv_data_escaped}', sep = ',')\n"

        # Load ggplot2 library
        load_ggplot2 = "library(ggplot2)\n"

        # Check if a filename is provided for the plot, if not create a temporary one
        if not filename:
            filename = tempfile.mktemp(suffix=".png")

        # Combine all R script parts
        full_r_code = load_ggplot2 + read_csv_code + ggplot_code

        # Add command to save the plot to a file
        full_r_code += f'\nggsave("{filename}", plot = last_plot(), width = 6, height = 4, device = "png")'

        result = subprocess.run(
            ["Rscript", "-"],
            input=full_r_code,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.stderr:
            print("Error in R script:", result.stderr)
        else:
            self._display_plot(filename)

    def _display_plot(self, filename):
        """Display the plot in the notebook."""
        img = mpimg.imread(filename)
        plt.imshow(img)
        plt.axis("off")
        plt.show()
