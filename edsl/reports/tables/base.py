import pandas as pd
from abc import abstractmethod

from ..base import Output


class TableOutput(Output):
    """Base class for table outputs"""

    # Registry to store all table output types
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses"""
        super().__init_subclass__(**kwargs)
        cls._registry[cls.__name__] = cls

    @property
    def scenario_output(self):
        """Returns the table as HTML."""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")

        # Convert DataFrame to styled HTML
        styled_df = df.style.set_properties(
            **{"text-align": "left", "padding": "8px", "border": "1px solid #ddd"}
        ).set_table_styles(
            [
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", "#f5f5f5"),
                        ("font-weight", "bold"),
                        ("text-align", "left"),
                        ("padding", "8px"),
                        ("border", "1px solid #ddd"),
                    ],
                },
                {
                    "selector": "tbody tr:nth-of-type(odd)",
                    "props": [("background-color", "#f9f9f9")],
                },
                {
                    "selector": "table",
                    "props": [
                        ("border-collapse", "collapse"),
                        ("width", "100%"),
                        ("margin", "20px 0"),
                        ("font-family", "Arial, sans-serif"),
                        ("font-size", "14px"),
                    ],
                },
            ]
        )

        return styled_df.to_html()

    @property
    @abstractmethod
    def narrative(self):
        """Returns a description of what this table shows. Must be implemented by subclasses."""
        pass

    @property
    def html(self):
        """Returns the HTML representation of the table"""
        df = self.output()
        if not isinstance(df, pd.DataFrame):
            raise ValueError("output() must return a pandas DataFrame")

        # Convert DataFrame to styled HTML
        styled_df = df.style.set_properties(
            **{"text-align": "left", "padding": "8px", "border": "1px solid #ddd"}
        ).set_table_styles(
            [
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", "#f5f5f5"),
                        ("font-weight", "bold"),
                        ("text-align", "left"),
                        ("padding", "8px"),
                        ("border", "1px solid #ddd"),
                    ],
                },
                {
                    "selector": "tbody tr:nth-of-type(odd)",
                    "props": [("background-color", "#f9f9f9")],
                },
                {
                    "selector": "table",
                    "props": [
                        ("border-collapse", "collapse"),
                        ("width", "100%"),
                        ("margin", "20px 0"),
                        ("font-family", "Arial, sans-serif"),
                        ("font-size", "14px"),
                    ],
                },
            ]
        )

        return styled_df.to_html()

    @classmethod
    def get_available_tables(cls):
        """Returns a dictionary of all registered table types"""
        return cls._registry

    @classmethod
    def create(cls, table_type, *args, **kwargs):
        """Factory method to create a table by name"""
        if table_type not in cls._registry:
            raise ValueError(
                f"Unknown table type: {table_type}. Available types: {list(cls._registry.keys())}"
            )
        return cls._registry[table_type](*args, **kwargs)

    @classmethod
    @abstractmethod
    def can_handle(cls, *question_objs) -> bool:
        """
        Abstract method that determines if this table type can handle the given questions.
        Must be implemented by all child classes.

        Args:
            *question_objs: Variable number of question objects to check

        Returns:
            bool: True if this table type can handle these questions, False otherwise
        """
        pass

    def output(self):
        """Must return a pandas DataFrame"""
        pass
