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

    def _repr_html_(self, base64_string: str = None) -> str:
        """Return inline image HTML for Jupyter notebooks."""
        if base64_string:
            return f'<img src="data:image/jpeg;base64,{base64_string}" />'
        return None

    def example(self):
        """Create a simple example JPEG using PIL."""
        from PIL import Image, ImageDraw

        # Create a simple gradient image
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        for i in range(200):
            color = (255 - i, 100, i)
            draw.line([(0, i), (200, i)], fill=color)
        draw.text((50, 90), "Example", fill="black")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as f:
            img.save(f.name, "JPEG")
        return f.name
