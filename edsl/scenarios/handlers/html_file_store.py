import tempfile
from ..file_methods import FileMethods

class HtmlMethods(FileMethods):
    suffix = "html"

    def view_system(self, width: int = None, height: int = None):
        import webbrowser

        # with open(self.path, "r") as f:
        #     html_string = f.read()

        # html_path = self.to_tempfile()
        # webbrowser.open("file://" + html_path)
        webbrowser.open("file://" + self.path)

    def view_notebook(self, width: int = None, height: int = None):
        from IPython.display import IFrame, display

        _width = width if width is not None else 800
        _height = height if height is not None else 800
        display(IFrame(self.path, width=_width, height=_height))

    def example(self):
        html_string = b"""
            <html>
            <head>
                <title>Test</title>
            </head>
            <body>
                <h1>Hello, World!</h1>
            </body>
            </html>
            """

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(html_string)
        return f.name
