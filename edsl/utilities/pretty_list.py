"""PrettyList module for enhanced list display."""

from collections import UserList
from .display_utils import Markdown


class PrettyList(UserList):
    """Enhanced list class with better display options for notebooks."""
    
    def __init__(self, data=None, columns=None):
        super().__init__(data)
        self.columns = columns

    def to_markdown(self):
        """Convert the list to markdown."""
        text = "".join([str(row) for row in self])
        return Markdown(text)

    def _repr_html_(self):
        """HTML representation for Jupyter notebooks."""
        # Import here to avoid circular imports
        from ..dataset import Dataset
        
        if not self:
            return "<pre><table><tr><td>Empty list</td></tr></table></pre>"
            
        if isinstance(self[0], list) or isinstance(self[0], tuple):
            num_cols = len(self[0])
        else:
            num_cols = 1

        if self.columns:
            columns = self.columns
        else:
            columns = list(range(num_cols))

        d = {}
        for column in columns:
            d[column] = []

        for row in self:
            for index, column in enumerate(columns):
                if isinstance(row, list) or isinstance(row, tuple):
                    d[column].append(row[index])
                else:
                    d[column].append(row)
                    
        return Dataset([{key: entry} for key, entry in d.items()])._repr_html_()