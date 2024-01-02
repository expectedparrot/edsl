import csv
from io import StringIO
import io
import pandas as pd


class ResultsStates:
    SELECTED = "selected"
    ORIGINAL = "original"


class ResultsExportMixin:
    def _make_tabular(self, remove_prefix):
        "Helper function that turns the results into a tabular format."
        d = {}
        full_header = list(self.relevant_columns())
        for entry in self:
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
        # return header, rows
        return header, rows

    def to_csv(self, filename: str = None, remove_prefix=False, download_link=False):
        """
        >>> r = create_example_results()
        >>> r.select('how_feeling').to_csv()
        'result.how_feeling\\r\\nBad\\r\\nBad\\r\\nGreat\\r\\nGreat\\r\\n'
        """
        if self.state == ResultsStates.SELECTED:
            header, rows = self._make_tabular(remove_prefix)

            if filename is not None:
                with open(filename, "w") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(rows)
            else:
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(header)
                writer.writerows(rows)

            if download_link:
                import base64
                from IPython.display import HTML, display

                csv_file = output.getvalue()
                b64 = base64.b64encode(csv_file.encode()).decode()
                download_link = f'<a href="data:file/csv;base64,{b64}" download="my_data.csv">Download CSV file</a>'
                display(HTML(download_link))
            else:
                return output.getvalue()
        else:
            return self.select().to_csv(
                filename, remove_prefix=remove_prefix, download_link=download_link
            )

    def to_pandas(self, remove_prefix=False):
        csv_string = self.to_csv(remove_prefix=remove_prefix)
        csv_buffer = io.StringIO(csv_string)
        df = pd.read_csv(csv_buffer)
        return df

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

    def tolist(self):
        print("Switch to using to_list() instead of tolist()")
        self.to_list()

    def to_list(self):
        # new_data = list(self[0].values())[0]
        if len(self) == 1:
            return list(self[0].values())[0]
        else:
            return tuple([list(x.values())[0] for x in self])

    def to_pivot(self):
        from pivottablejs import pivot_ui

        df = self.to_pandas()
        return pivot_ui(df)
