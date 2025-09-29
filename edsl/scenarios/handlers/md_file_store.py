import tempfile
from ..file_methods import FileMethods


class MarkdownMethods(FileMethods):
    suffix = "md"

    def view_system(self):
        import os
        from rich.console import Console
        from rich.markdown import Markdown

        if os.path.exists(self.path):
            try:
                console = Console()
                with open(self.path, "r", encoding="utf-8") as f:
                    content = f.read()
                    md = Markdown(content)
                    console.print(md)
            except Exception as e:
                print(f"Error rendering Markdown: {e}")
        else:
            print("Markdown file was not found.")

    def view_notebook(self):
        from IPython.display import FileLink, Markdown, display

        # First display the content of the markdown file
        with open(self.path, "r", encoding="utf-8") as f:
            content = f.read()
            display(Markdown(content))

        # Then provide a download link
        display(FileLink(self.path))

    def example(self):
        markdown_content = """# Sample Markdown
        
## Features
- **Bold text** demonstration
- *Italic text* demonstration
- Code block example:
```python
print("Hello, World!")
```
"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".md", mode="w", encoding="utf-8"
        ) as f:
            f.write(markdown_content)
        return f.name
