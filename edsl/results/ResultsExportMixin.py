import base64
import csv
import io
from IPython.display import HTML, display
import pandas as pd
from edsl.utilities import (
    print_list_of_dicts_with_rich,
    print_list_of_dicts_as_html_table,
    print_dict_with_rich,
)


class ResultsExportMixin:
    def convert_decorator(func):
        def wrapper(self, *args, **kwargs):
            if self.__class__.__name__ == "Results":
                return func(self.select(), *args, **kwargs)
            elif self.__class__.__name__ == "Dataset":
                return func(self, *args, **kwargs)
            else:
                raise Exception(
                    f"Class {self.__class__.__name__} not recognized as a Results or Dataset object."
                )

        return wrapper

    @convert_decorator
    def _make_tabular(self, remove_prefix):
        "Helper function that turns the results into a tabular format."
        d = {}
        full_header = list(self.relevant_columns())
        for entry in self.data:
            key, list_of_values = list(entry.items())[0]
            d[key] = list_of_values
        if remove_prefix:
            header = [h.split(".")[-1] for h in full_header]
        else:
            header = full_header
        num_observations = len(list(self[0].values())[0])
        rows = []
        # rows.append(header)
        for i in range(num_observations):
            row = [d[h][i] for h in full_header]
            rows.append(row)
        return header, rows

    def print_long(self):
        """ """
        for result in self:
            if hasattr(result, "combined_dict"):
                d = result.combined_dict
            else:
                d = result
            print_dict_with_rich(d)

    @convert_decorator
    def print(
        self,
        pretty_labels=None,
        filename=None,
        html=False,
        interactive=False,
        split_at_dot=True,
    ):
        if pretty_labels is None:
            pretty_labels = {}

        new_data = []
        for entry in self:
            key, list_of_values = list(entry.items())[0]
            new_data.append({pretty_labels.get(key, key): list_of_values})
        else:
            if not html:
                print_list_of_dicts_with_rich(
                    new_data, filename=filename, split_at_dot=split_at_dot
                )
            else:
                print_list_of_dicts_as_html_table(
                    new_data, filename=None, interactive=interactive
                )

    @convert_decorator
    def to_csv(self, filename: str = None, remove_prefix=False, download_link=False):
        """
        >>> r = create_example_results()
        >>> r.select('how_feeling').to_csv()
        'result.how_feeling\\r\\nBad\\r\\nBad\\r\\nGreat\\r\\nGreat\\r\\n'
        """
        header, rows = self._make_tabular(remove_prefix)

        if filename is not None:
            with open(filename, "w") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(header)
            writer.writerows(rows)

            if download_link:
                csv_file = output.getvalue()
                b64 = base64.b64encode(csv_file.encode()).decode()
                download_link = f'<a href="data:file/csv;base64,{b64}" download="my_data.csv">Download CSV file</a>'
                display(HTML(download_link))
            else:
                return output.getvalue()

    @convert_decorator
    def to_pandas(self, remove_prefix=False):
        csv_string = self.to_csv(remove_prefix=remove_prefix)
        csv_buffer = io.StringIO(csv_string)
        df = pd.read_csv(csv_buffer)
        return df

    @convert_decorator
    def to_dicts(self, remove_prefix=False):
        df = self.to_pandas(remove_prefix=remove_prefix)
        df = df.convert_dtypes()
        list_of_dicts = df.to_dict(orient="records")
        # Convert any pd.NA values to None
        list_of_dicts = [
            {k: (None if pd.isna(v) else v) for k, v in record.items()}
            for record in list_of_dicts
        ]
        return list_of_dicts

    @convert_decorator
    def to_list(self):
        if len(self) == 1:
            return list(self[0].values())[0]
        else:
            return tuple([list(x.values())[0] for x in self])


if __name__ == "__main__":
    import doctest

    doctest.testmod()
