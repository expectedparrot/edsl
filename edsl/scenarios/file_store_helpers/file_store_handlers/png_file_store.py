import tempfile
from ..file_methods import FileMethods


class PngMethods(FileMethods):
    suffix = "png"

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
                print(f"Error opening PNG: {e}")
        else:
            print("PNG file was not found.")

    def view_notebook(self):
        from IPython.display import Image, display

        display(Image(filename=self.path))

    def _repr_html_(self, base64_string: str = None) -> str:
        """Return inline image HTML for Jupyter notebooks."""
        if base64_string:
            return f'<img src="data:image/png;base64,{base64_string}" />'
        return None

    def example(self):
        """Create a simple example PNG using PIL."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise ImportError(
                "PIL (Pillow) is required to create PNG examples. "
                "Install it with: pip install pillow"
            )

        # Create a simple gradient image
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        for i in range(200):
            color = (i, 100, 255 - i)
            draw.line([(0, i), (200, i)], fill=color)
        draw.text((50, 90), "EDSL", fill="black")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            img.save(f.name)
        return f.name
