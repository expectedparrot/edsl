import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from enum import Enum


class SQLDataShape(Enum):
    WIDE = "wide"
    LONG = "long"


class ResultsDBMixin:
    def rows(self):
        for index, result in enumerate(self):
            yield from result.rows(index)

    def export_sql_dump(self, shape, filename):
        shape_enum = self._get_shape_enum(shape)
        conn = self.db(shape=shape_enum)

        # Open file to write SQL dump
        with open(filename, "w") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")

        # Close the connection
        conn.close()

    def backup_db_to_file(self, shape, filename):
        shape_enum = self._get_shape_enum(shape)
        # Source database connection (in-memory)
        source_conn = self.db(shape=shape_enum)

        # Destination database connection (file)
        dest_conn = sqlite3.connect(filename)

        # Backup in-memory database to file
        with source_conn:
            source_conn.backup(dest_conn)

        # Close both connections
        source_conn.close()
        dest_conn.close()

    def db(self, shape: SQLDataShape, remove_prefix=False):
        if shape == SQLDataShape.LONG:
            # Step 2: Create a SQLite Database in Memory
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

            # # Step 3: Insert the tuples into the table
            list_of_tuples = list(self.rows())
            insert_query = (
                "INSERT INTO self (id, data_type, key, value) VALUES (?, ?, ?, ?)"
            )
            conn.executemany(insert_query, list_of_tuples)
            conn.commit()
            return conn
        elif shape == SQLDataShape.WIDE:
            db_uri = "sqlite:///:memory:"

            # Create SQLAlchemy engine with the in-memory database connection string
            engine = create_engine(db_uri)

            # Convert DataFrame to SQLite in-memory database
            df = self.to_pandas(remove_prefix=remove_prefix)
            df.to_sql("self", engine, index=False, if_exists="replace")

            # Create a connection to the SQLite database
            conn = engine.connect()
            return conn
        else:
            raise Exception("Invalid SQLDataShape")

    def _get_shape_enum(self, shape: str):
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
        shape: str,
        remove_prefix: bool = False,
        transpose: bool = None,
        transpose_by: str = None,
        csv: bool = False,
    ):
        """Execute a SQL query and return the results as a DataFrame.
        :param query: The SQL query to execute
        :param transpose: Transpose the DataFrame if True
        :param transpose_by: Column to use as the index when transposing, otherwise the first column
        :param csv: Return the DataFrame as a CSV string if True
        """
        shape_enum = self._get_shape_enum(shape)

        conn = self.db(shape=shape_enum, remove_prefix=remove_prefix)
        df = pd.read_sql_query(query, conn)

        # Transpose the DataFrame if transpose is True
        if transpose or transpose_by:
            df = pd.DataFrame(df)
            if transpose_by:
                df = df.set_index(transpose_by)
            else:
                df = df.set_index(df.columns[0])
            df = df.transpose()

        # Return as CSV if output is "csv"
        if csv:
            return df.to_csv(index=False)
        else:
            return df

    def show_schema(self, shape: str, remove_prefix: bool = False):
        shape_enum = self._get_shape_enum(shape)
        conn = self.db(shape=shape_enum, remove_prefix=remove_prefix)

        if shape_enum == SQLDataShape.LONG:
            # Query to get the schema of all tables
            query = "SELECT type, name, sql FROM sqlite_master WHERE type='table'"

            # Execute the query
            cursor = conn.execute(query)
            schema = cursor.fetchall()

            # Close the connection
            conn.close()

            # Format and return the schema information
            schema_info = ""
            for row in schema:
                schema_info += f"Type: {row[0]}, Name: {row[1]}, SQL: {row[2]}\n"

            print(schema_info)
        elif shape_enum == SQLDataShape.WIDE:
            query = f"PRAGMA table_info(self)"
            schema = pd.read_sql(query, conn)
            print(schema)


if __name__ == "__main__":
    from edsl.results import Results

    r = Results.example()

    df = r.sql(
        "select data_type, key, value from self where data_type = 'answer'",
        shape="long",
    )
    print(df)

    df = r.sql(
        "select * from self",
        shape="wide",
    )

    df = r.sql(
        "select * from self",
        shape="wide",
    )

    r.show_schema(shape="long")

    df = r.sql(
        "select * from self",
        shape="wide",
    )

    print(df)
