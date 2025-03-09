from typing import Optional


class SmartInt(int):
    pass


class SmartFloat(float):
    pass


class SmartStr(str):
    def clipboard(self) -> None:
        try:
            import pyperclip
        except ImportError:
            print(
                "pyperclip is not installed. Run `pip install pyperclip` to install it."
            )
            return None

        pyperclip.copy(self)
        print("Text copied to clipboard.")

    def write(self, filename: str):
        with open(filename, "w") as f:
            f.write(str(self))
        return None

    def _repr_html_(self):
        pass

    def markdown(self):
        return SmartMarkdown(self)

    def pdf(self, filename: Optional[str] = None):  # Markdown will have this as well
        # renders the markdown as a pdf that can be downloaded
        from edsl.results.MarkdownToPDF import MarkdownToPDF

        return MarkdownToPDF(self, filename).preview()

    def docx(self, filename: Optional[str] = None):
        # renders the markdown as a docx that can be downloaded
        from edsl.results.MarkdownToDocx import MarkdownToDocx

        return MarkdownToDocx(self, filename).preview()

    def edit(self):
        from edsl.results.TextEditor import TextEditor

        editor = TextEditor(self)
        self = self.__class__(editor.edit_gui())
        # print(f"Updated text: {self}")


class SmartMarkdown(SmartStr):
    def _repr_markdown_(self):
        return self

    def _repr_html_(self):
        from IPython.display import Markdown, display

        display(Markdown(self))


class SmartLaTeX(SmartStr):
    def _repr_html_(self):
        print(self)

    def pdf(self, filename: Optional[str] = None):
        from edsl.results.LaTeXToPDF import LaTeXToPDF

        return LaTeXToPDF(self, filename).preview()

    def docx(self, filename: Optional[str] = None):
        from edsl.results.LaTeXToDocx import LaTeXToDocx

        return LaTeXToDocx(self, filename).preview()

    def edit(self):
        from edsl.results.TextEditor import TextEditor

        editor = TextEditor(self)
        self = self.__class__(editor.edit_gui())
        # print(f"Updated LaTeX: {self}")


class FirstObject:
    def __new__(self, value):
        if isinstance(value, int):
            return SmartInt(value)
        if isinstance(value, float):
            return SmartFloat(value)
        if isinstance(value, str):
            return SmartStr(value)
        return value
