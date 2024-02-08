import pandas as pd
import sqlite3


class ResultsDBMixin:
    def rows(self):
        for index, result in enumerate(self):
            yield from result.rows(index)

    def export_sql_dump(self, filename):
        conn = self.db()

        # Open file to write SQL dump
        with open(filename, "w") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")

        # Close the connection
        conn.close()

    def backup_db_to_file(self, filename):
        # Source database connection (in-memory)
        source_conn = self.db()

        # Destination database connection (file)
        dest_conn = sqlite3.connect(filename)

        # Backup in-memory database to file
        with source_conn:
            source_conn.backup(dest_conn)

        # Close both connections
        source_conn.close()
        dest_conn.close()

    def db(self):
        import sqlite3

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

    def sql(self, query, transpose=False, csv=False):
        import pandas as pd

        conn = self.db()
        df = pd.read_sql_query(query, conn)

        # Transpose the DataFrame if transpose is True
        if transpose:
            df = df.transpose()

        # Return as CSV if output is "csv"
        if csv:
            return df.to_csv(index=False)
        else:
            return df

    def show_schema(self):
        conn = self.db()

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

        return schema_info
