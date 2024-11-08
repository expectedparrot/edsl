"""Mixin for working with SQLite respresentation of a 'Results' object."""

import sqlite3
from enum import Enum
from typing import Literal, Union, Optional


class SQLDataShape(Enum):
    """Enum for the shape of the data in the SQL database."""

    WIDE = "wide"
    LONG = "long"


class ResultsDBMixin:
    """Mixin for interacting with a Results object as if it were a SQL database."""

    def _rows(self):
        """Return the rows of the `Results` object as a list of tuples."""
        for index, result in enumerate(self):
            yield from result.rows(index)

    def export_sql_dump(self, shape: Literal["wide", "long"], filename: str):
        """Export the SQL database to a file.

        :param shape: The shape of the data in the database (wide or long)
        :param filename: The filename to save the database to
        """
        shape_enum = self._get_shape_enum(shape)
        conn = self._db(shape=shape_enum)

        with open(filename, "w") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")

        conn.close()

    def backup_db_to_file(self, shape: Literal["wide", "long"], filename: str):
        """Backup the in-memory database to a file.


        :param shape: The shape of the data in the database (wide or long)
        :param filename: The filename to save the database to

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.backup_db_to_file(filename="backup.db", shape="long")

        """
        shape_enum = self._get_shape_enum(shape)
        # Source database connection (in-memory)
        source_conn = self._db(shape=shape_enum)

        # Destination database connection (file)
        dest_conn = sqlite3.connect(filename)

        # Backup in-memory database to file
        with source_conn:
            source_conn.backup(dest_conn)

        # Close both connections
        source_conn.close()
        dest_conn.close()

    def _db(self, shape: SQLDataShape, remove_prefix=False):
        """Create a SQLite database in memory and return the connection.

        :param shape: The shape of the data in the database (wide or long)
        :param remove_prefix: Whether to remove the prefix from the column names

        """
        if shape == SQLDataShape.LONG:
            conn = sqlite3.connect(":memory:")

            create_table_query = """
            CREATE TABLE self (
                id INTEGER,
                data_type TEXT,
                key TEXT, 
                value TEXT
            )
            """
            conn.execute(create_table_query)

            list_of_tuples = list(self._rows())
            insert_query = (
                "INSERT INTO self (id, data_type, key, value) VALUES (?, ?, ?, ?)"
            )
            conn.executemany(insert_query, list_of_tuples)
            conn.commit()
            return conn
        elif shape == SQLDataShape.WIDE:
            from sqlalchemy import create_engine

            engine = create_engine("sqlite:///:memory:")
            df = self.to_pandas(remove_prefix=remove_prefix, lists_as_strings=True)
            df.to_sql("self", engine, index=False, if_exists="replace")
            return engine.connect()
        else:
            raise Exception("Invalid SQLDataShape")

    def _get_shape_enum(self, shape: Literal["wide", "long"]):
        """Convert the shape string to a SQLDataShape enum."""
        if shape is None:
            raise Exception("Must select either 'wide' or 'long' format")
        elif shape == "wide":
            return SQLDataShape.WIDE
        elif shape == "long":
            return SQLDataShape.LONG
        else:
            raise Exception("Invalid shape: must be either 'long' or 'wide'")

    def sql(
        self,
        query: str,
        shape: Literal["wide", "long"] = "wide",
        remove_prefix: bool = True,
        transpose: bool = None,
        transpose_by: str = None,
        csv: bool = False,
        to_list=False,
        to_latex=False,
        filename: Optional[str] = None,
    ) -> Union["pd.DataFrame", str]:
        """Execute a SQL query and return the results as a DataFrame.

        :param query: The SQL query to execute
        :param shape: The shape of the data in the database (wide or long)
        :param remove_prefix: Whether to remove the prefix from the column names
        :param transpose: Whether to transpose the DataFrame
        :param transpose_by: The column to use as the index when transposing
        :param csv: Whether to return the DataFrame as a CSV string


        Example usage:

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> d = r.sql("select data_type, key, value from self where data_type = 'answer' order by value limit 3", shape="long")
        >>> sorted(list(d['value']))
        ['Good', 'Great', 'Great']

        We can also return the data in wide format.
        Note the use of single quotes to escape the column names, as required by sql.

        >>> from edsl.results import Results
        >>> Results.example().sql("select how_feeling from self", shape = 'wide', remove_prefix=True)
          how_feeling
        0          OK
        1       Great
        2    Terrible
        3          OK
        """
        import pandas as pd

        shape_enum = self._get_shape_enum(shape)

        conn = self._db(shape=shape_enum, remove_prefix=remove_prefix)
        df = pd.read_sql_query(query, conn)

        # Transpose the DataFrame if transpose is True
        if transpose or transpose_by:
            df = pd.DataFrame(df)
            if transpose_by:
                df = df.set_index(transpose_by)
            else:
                df = df.set_index(df.columns[0])
            df = df.transpose()

        if csv and to_list:
            raise Exception("Cannot return both CSV and list")

        if to_list:
            return df.values.tolist()

        if to_latex:
            df.columns = [col.replace("_", " ") for col in df.columns]

            latex_output = df.to_latex(index=False)
            if filename:
                with open(filename, "w") as f:
                    f.write(latex_output)
                return None
            return latex_output

        if csv:
            if filename:
                df.to_csv(filename, index=False)
                return None

            return df.to_csv(index=False)

        return df

    def show_schema(
        self, shape: Literal["wide", "long"], remove_prefix: bool = False
    ) -> None:
        """Show the schema of the Results database.

        :param shape: The shape of the data in the database (wide or long)
        :param remove_prefix: Whether to remove the prefix from the column names

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.show_schema(shape="long")
        Type: table, Name: self, SQL: CREATE TABLE self (
        ...
        <BLANKLINE>
        """
        import pandas as pd

        shape_enum = self._get_shape_enum(shape)
        conn = self._db(shape=shape_enum, remove_prefix=remove_prefix)

        if shape_enum == SQLDataShape.LONG:
            # Query to get the schema of all tables
            query = "SELECT type, name, sql FROM sqlite_master WHERE type='table'"
            cursor = conn.execute(query)
            schema = cursor.fetchall()
            conn.close()

            # Format and return the schema information
            schema_info = ""
            for row in schema:
                schema_info += f"Type: {row[0]}, Name: {row[1]}, SQL: {row[2]}\n"

            print(schema_info)
        elif shape_enum == SQLDataShape.WIDE:
            query = f"PRAGMA table_info(self)"
            schema = pd.read_sql(query, conn)
            # print(schema)
            return schema


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
