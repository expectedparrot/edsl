import tempfile

from ..file_methods import FileMethods

class TxtMethods(FileMethods):
    suffix = "txt"

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
                print(f"Error opening TXT: {e}")
        else:
            print("TXT file was not found.")

    def view_notebook(self):
        from ...display import FileLink, display

        display(FileLink(self.path))

    def example(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Hello, World!")
        return f.name
