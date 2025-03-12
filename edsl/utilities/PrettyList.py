from collections import UserList
from ..dataset import Dataset

class Markkdown:

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text
    
    def _repr_markdown_(self):
        return self.text

class PrettyList(UserList):
    def __init__(self, data=None, columns=None):
        super().__init__(data)
        self.columns = columns

    def to_markdown(self):
        text = "".join([str(row) for row in self])
        return Markkdown(text)

    def _repr_html_(self):
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
        # raise ValueError(d)
        return Dataset([{key: entry} for key, entry in d.items()])._repr_html_()

        if num_cols > 1:
            return (
                "<pre><table>"
                + "".join(["<th>" + str(column) + "</th>" for column in columns])
                + "".join(
                    [
                        "<tr>"
                        + "".join(["<td>" + str(x) + "</td>" for x in row])
                        + "</tr>"
                        for row in self
                    ]
                )
                + "</table></pre>"
            )
        else:
            return (
                "<pre><table>"
                + "".join(["<th>" + str(index) + "</th>" for index in columns])
                + "".join(
                    ["<tr>" + "<td>" + str(row) + "</td>" + "</tr>" for row in self]
                )
                + "</table></pre>"
            )
