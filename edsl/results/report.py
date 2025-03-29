import jinja2
import textwrap

class Report:
    """
    A flexible report generator for creating formatted output from EDSL datasets.
    
    The Report class provides a powerful yet simple way to create customized reports
    from your survey results. It uses Jinja2 templates to format the data with complete
    control over the presentation. This is particularly useful for:
    
    - Creating human-readable summaries of your results
    - Generating standardized reports for stakeholders
    - Formatting results for inclusion in papers or presentations
    - Creating custom visualizations of your data
    
    The Report class works with any object that supports the Dataset interface,
    including Results objects after using the select() method.
    
    Key features:
    
    - Flexible templating with full Jinja2 syntax
    - Support for filtering and sorting data
    - Customizable field selection and labeling
    - Simple integration with Results and Dataset objects
    
    Usage:
      report = Report(
          dataset=my_dataset,
          fields=["answer.how_feeling", "answer.how_feeling_yesterday"],
          template=textwrap.dedent(\"\"\"\
              # Observation {{ i }}
              How feeling: {{ row['answer.how_feeling'] }}
              How feeling yesterday: {{ row['answer.how_feeling_yesterday'] }}

              ---
          \"\"\")
      )
      print(report.generate())
    """
    def __init__(
        self,
        dataset,
        fields=None,
        template=None,
        top_n=None,
        pretty_labels=None,
        filter_func=None,
        sort_by=None
    ):
        """
        :param dataset: The Dataset instance (DatasetExportMixin-based) to report on.
        :param fields:  List of fields (column names) to include in the report. If None, use all.
        :param template: A Jinja2-compatible template string describing how each row should be rendered.
                         Within the template, you have access to:
                           - {{ i }}         (the 1-based index of the row)
                           - {{ row }}       (dictionary of field values for that row)
        :param top_n:   If provided, only report on the first N observations.
        :param pretty_labels: Dict mapping original field names to "pretty" labels used inside the template,
                              or you can manually handle that in the template yourself.
        :param filter_func: Optional callable(row_dict) -> bool. If given, only rows for which
                            filter_func(row_dict) is True will appear in the final report.
        :param sort_by: Optional single field name or list of field names to sort by.
        """
        self.dataset = dataset
        self.fields = fields
        self.template = template
        self.top_n = top_n
        self.pretty_labels = pretty_labels or {}
        self.filter_func = filter_func
        self.sort_by = sort_by

        # Provide a simple fallback template
        if not self.template:
            # A minimal default: print all fields line by line
            # with a heading "Observation #1" etc.
            self.template = textwrap.dedent("""\
                # Observation {{ i }}
                {% for key, value in row.items() %}
                **{{ key }}**: {{ value }}
                {% endfor %}
                ---
            """)

    def _prepare_data(self):
        """
        Convert dataset into a list of dictionaries (one per row),
        optionally filtering, sorting, and limiting to top_n rows.
        """
        # 1) Decide which fields to include
        if not self.fields:
            self.fields = self.dataset.relevant_columns()

        # 2) Convert to list of dictionaries
        #    removing prefix because we typically want "field" instead of "answer.field"
        data_dicts = self.dataset.to_dicts(remove_prefix=False)

        # 3) Filter out any rows if filter_func is given
        if self.filter_func:
            data_dicts = [row for row in data_dicts if self.filter_func(row)]

        # 4) If sort_by was specified, we’ll do a simple sort
        if self.sort_by:
            if isinstance(self.sort_by, str):
                sort_keys = [self.sort_by]
            else:
                sort_keys = self.sort_by

            # Python's sort can't directly do multi-key with fields from a dict
            # unless we do something like tuple(...) for each field
            # For simplicity, do a stable sort in reverse order for multiple keys
            # or do a single pass with a tuple:
            data_dicts.sort(key=lambda row: tuple(row.get(k) for k in sort_keys))

        # 5) If top_n is specified, slice
        if self.top_n is not None:
            data_dicts = data_dicts[: self.top_n]

        # 6) Optionally rename fields if pretty_labels is given
        #    (But typically you'd use it inside the template. This is just an example.)
        if self.pretty_labels:
            # We'll apply them in a copy so the original keys are still accessible
            data_for_report = []
            for row in data_dicts:
                # copy of the row, but with replaced keys
                new_row = {}
                for k, v in row.items():
                    display_key = self.pretty_labels.get(k, k)
                    new_row[display_key] = v
                data_for_report.append(new_row)
            data_dicts = data_for_report

        return data_dicts

    def generate(self) -> str:
        """
        Render the final report as a string.
        
        This method applies the Jinja2 template to each row of data and
        combines the results into a single string. The template has access
        to the row index (i) and the row data (row) for each observation.
        
        Returns:
            A formatted string containing the complete report.
        
        Examples:
            >>> from edsl import Results
            >>> ds = Results.example().select("how_feeling")
            >>> report = Report(dataset=ds)
            >>> lines = report.generate().split("\\n")
            >>> lines[0]
            '# Observation 1'
            
            >>> # Custom template
            >>> template = "Row {{ i }}: {{ row['answer.how_feeling'] }}\\n"
            >>> report = Report(dataset=ds, template=template)
            >>> report.generate().split("\\n")[0]
            'Row 1: OK'
        """
        # Prepare data
        data_dicts = self._prepare_data()

        # Build a single Jinja2 template
        template_obj = jinja2.Template(self.template)

        output = []
        for i, row in enumerate(data_dicts, start=1):
            rendered = template_obj.render(i=i, row=row)
            output.append(rendered.strip())

        return "\n\n".join(output)


if __name__ == "__main__":
    # Suppose you have an existing Dataset
    from .. import Results
    ds = Results.example().select("how_feeling", "how_feeling_yesterday")

    # Provide a custom template string
    my_template = textwrap.dedent("""\
        ## Row {{ i }}

        Feeling: {{ row['answer.how_feeling'] }}
        Yesterday: {{ row['answer.how_feeling_yesterday'] }}

        --------------------
    """)

    report = Report(
        dataset=ds,
        fields=["answer.how_feeling", "answer.how_feeling_yesterday"],
        template=my_template,
        top_n=3,  # only the first 3 observations
    )

    print(report.generate())
