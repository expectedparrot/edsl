from tabulate import tabulate


class TableDisplay:
    max_height = 800

    html_template = """
    <div style="
        height: {height}px;
        max-width: 100%%;
        overflow: auto;
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 4px;
        margin-left: 0; 
    ">
        <style>
            .scroll-table {{
                border-collapse: collapse;
                width: auto;
                white-space: nowrap;
            }}
            .scroll-table th, .scroll-table td {{
                padding: 8px;
                text-align: left !important;
                border-bottom: 1px solid #ddd;
                min-width: 100px;  /* Minimum column width */
                max-width: 300px;  /* Maximum column width */
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .scroll-table th {{
                background-color: #f5f5f5;
                position: sticky;
                top: 0;
                z-index: 1;
            }}
            .scroll-table tr:hover {{
                background-color: #f5f5f5;
            }}
            /* Add horizontal scrollbar styles */
            .scroll-table-wrapper {{
                overflow-x: auto;
                margin-bottom: 10px;
            }}
            /* Optional: Style scrollbars for webkit browsers */
            .scroll-table-wrapper::-webkit-scrollbar {{
                height: 8px;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-track {{
                background: #f1f1f1;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-thumb {{
                background: #888;
                border-radius: 4px;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-thumb:hover {{
                background: #555;
            }}
        </style>
        <div class="scroll-table-wrapper">
            {table}
        </div>
    </div>
    """

    def __init__(self, headers, data, tablefmt=None, raw_data_set=None):
        self.headers = headers
        self.data = data
        self.tablefmt = tablefmt
        self.raw_data_set = raw_data_set

    def to_csv(self, filename: str):
        self.raw_data_set.to_csv(filename)

    def write(self, filename: str):
        # pass
        if self.tablefmt is None:
            table = tabulate(self.data, headers=self.headers, tablefmt="simple")
        else:
            table = tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

        with open(filename, "w") as file:
            print("Writing table to", filename)
            file.write(table)

    def to_pandas(self):
        return self.raw_data_set.to_pandas()

    def to_list(self):
        return self.raw_data_set.to_list()

    def __repr__(self):
        from tabulate import tabulate

        if self.tablefmt is None:
            return tabulate(self.data, headers=self.headers, tablefmt="simple")
        else:
            return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    def long(self):
        new_header = ["row", "key", "value"]
        new_data = []
        for index, row in enumerate(self.data):
            new_data.extend([[index, k, v] for k, v in zip(self.headers, row)])
        return TableDisplay(new_header, new_data)

    def _repr_html_(self):
        if self.tablefmt is not None:
            return (
                "<pre>"
                + tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)
                + "</pre>"
            )

        num_rows = len(self.data)
        height = min(
            num_rows * 30 + 50, self.max_height
        )  # Added extra space for header

        # Generate HTML table with the scroll-table class
        html_content = tabulate(self.data, headers=self.headers, tablefmt="html")
        html_content = html_content.replace("<table>", '<table class="scroll-table">')

        return self.html_template.format(table=html_content, height=height)
