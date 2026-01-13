import tempfile
from ..file_methods import FileMethods


class SvgMethods(FileMethods):
    suffix = "svg"

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
                print(f"Error opening SVG: {e}")
        else:
            print("SVG file was not found.")

    def view_notebook(self):
        from IPython.display import SVG, display

        display(SVG(filename=self.path))

    def example(self):
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />
</svg>"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".svg", mode="w") as f:
            f.write(svg_content)
        return f.name
