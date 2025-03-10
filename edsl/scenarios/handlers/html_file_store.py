import tempfile
from ..file_methods import FileMethods

class HtmlMethods(FileMethods):
    suffix = "html"

    def view_system(self):
        import webbrowser

        # with open(self.path, "r") as f:
        #     html_string = f.read()

        # html_path = self.to_tempfile()
        # webbrowser.open("file://" + html_path)
        webbrowser.open("file://" + self.path)

    def view_notebook(self):
        from IPython.display import IFrame, display

        display(IFrame(self.path, width=800, height=800))

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
