import os
import tempfile
import sqlite3
from edsl.scenarios import FileStore

from ..file_methods import FileMethods

class SQLiteMethods(FileMethods):
    suffix = "db"  # or "sqlite", depending on your preference

    def extract_text(self):
        """
        Extracts a text representation of the database schema and table contents.
        """
        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()

            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            full_text = []

            # For each table, get schema and contents
            for (table_name,) in tables:
                # Get table schema
                cursor.execute(
                    f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';"
                )
                schema = cursor.fetchone()[0]
                full_text.append(f"Table: {table_name}")
                full_text.append(f"Schema: {schema}")

                # Get table contents
                cursor.execute(f"SELECT * FROM {table_name};")
                rows = cursor.fetchall()

                # Get column names
                column_names = [description[0] for description in cursor.description]
                full_text.append(f"Columns: {', '.join(column_names)}")

                # Add row data
                for row in rows:
                    full_text.append(str(row))
                full_text.append("\n")

        return "\n".join(full_text)

    def view_system(self):
        """
        Opens the database with the system's default SQLite viewer if available.
        """
        import subprocess

        if os.path.exists(self.path):
            try:
                if (os_name := os.name) == "posix":
                    # Try DB Browser for SQLite on macOS
                    subprocess.run(
                        ["open", "-a", "DB Browser for SQLite", self.path], check=True
                    )
                elif os_name == "nt":
                    # Try DB Browser for SQLite on Windows
                    subprocess.run(["DB Browser for SQLite.exe", self.path], check=True)
                else:
                    # Try sqlitebrowser on Linux
                    subprocess.run(["sqlitebrowser", self.path], check=True)
            except Exception as e:
                print(f"Error opening SQLite database: {e}")
        else:
            print("SQLite database file was not found.")

    def view_notebook(self):
        """
        Displays database contents in a Jupyter notebook.
        """
        import pandas as pd
        from IPython.display import HTML, display

        with sqlite3.connect(self.path) as conn:
            # Get all table names
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            html_parts = []
            for (table_name,) in tables:
                # Read table into pandas DataFrame
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

                # Convert to HTML with styling
                table_html = f"""
                <div style="margin-bottom: 20px;">
                    <h3>{table_name}</h3>
                    {df.to_html(index=False)}
                </div>
                """
                html_parts.append(table_html)

            # Combine all tables into one scrollable div
            html = f"""
            <div style="width: 800px; height: 800px; padding: 20px; 
                       border: 1px solid #ccc; overflow-y: auto;">
                {''.join(html_parts)}
            </div>
            """
            display(HTML(html))

    def example(self):
        """
        Creates an example SQLite database for testing.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()

            # Create a sample table
            cursor.execute(
                """
                CREATE TABLE survey_responses (
                    id INTEGER PRIMARY KEY,
                    question TEXT,
                    response TEXT
                )
            """
            )

            # Insert some sample data
            sample_data = [
                (1, "First Survey Question", "Response 1"),
                (2, "Second Survey Question", "Response 2"),
            ]
            cursor.executemany(
                "INSERT INTO survey_responses (id, question, response) VALUES (?, ?, ?)",
                sample_data,
            )

            conn.commit()
            conn.close()
            tmp.close()

            return tmp.name


if __name__ == "__main__":
    sqlite_temp = SQLiteMethods.example()
    fs = FileStore(sqlite_temp)
