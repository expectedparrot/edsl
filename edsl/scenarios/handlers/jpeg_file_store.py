import tempfile
from ..file_methods import FileMethods


class JpegMethods(FileMethods):
    suffix = "jpeg"

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
                print(f"Error opening JPEG: {e}")
        else:
            print("JPEG file was not found.")

    def view_notebook(self):
        from IPython.display import Image, display

        display(Image(filename=self.path))

    def example(self):
        import matplotlib.pyplot as plt
        import numpy as np

        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        plt.plot(x, y)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as f:
            plt.savefig(f.name)
        return f.name