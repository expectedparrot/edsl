from edsl.scenarios.file_methods import FileMethods
import tempfile
import re
from typing import List, Optional
import sqlparse


class SqlMethods(FileMethods):

    suffix = "sql"

    def view_system(self):
        import os
        import subprocess

        if os.path.exists(self.path):
            try:
                if (os_name := os.name) == "posix":
                    subprocess.run(["open", self.path], check=True)  # macOS
                elif os_name == "nt":
                    os.startfile(self.path)  # Windows
                else:
                    subprocess.run(["xdg-open", self.path], check=True)  # Linux
            except Exception as e:
                print(f"Error opening SQL file: {e}")
        else:
            print("SQL file was not found.")

    def view_notebook(self):
        from IPython.display import FileLink, display, HTML
        import pygments
        from pygments.lexers import SqlLexer
        from pygments.formatters import HtmlFormatter

        try:
            # Read the SQL file
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Format SQL with syntax highlighting
            formatter = HtmlFormatter(style="monokai")
            highlighted_sql = pygments.highlight(content, SqlLexer(), formatter)

            # Add CSS for syntax highlighting
            css = formatter.get_style_defs(".highlight")

            # Display formatted SQL
            display(HTML(f"<style>{css}</style>{highlighted_sql}"))

            # Provide download link
            display(FileLink(self.path))
        except Exception as e:
            print(f"Error displaying SQL: {e}")

    def format_sql(self) -> bool:
        """Format the SQL file with proper indentation and keyword capitalization."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Format each statement in the file
            formatted_sql = sqlparse.format(
                content,
                reindent=True,
                keyword_case="upper",
                identifier_case="lower",
                comma_first=False,
                wrap_after=80,
            )

            with open(self.path, "w", encoding="utf-8") as f:
                f.write(formatted_sql)

            return True
        except Exception as e:
            print(f"Error formatting SQL: {e}")
            return False

    def split_statements(self) -> List[str]:
        """Split the SQL file into individual statements."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            return sqlparse.split(content)
        except Exception as e:
            print(f"Error splitting SQL statements: {e}")
            return []

    def validate_basic_syntax(self) -> bool:
        """
        Perform basic SQL syntax validation.
        Note: This is a simple check and doesn't replace proper SQL parsing.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            statements = sqlparse.split(content)
            for stmt in statements:
                parsed = sqlparse.parse(stmt)
                if not parsed:
                    print(f"Invalid SQL syntax: {stmt}")
                    return False

                # Check for basic SQL keywords
                stmt_upper = stmt.upper()
                if not any(
                    keyword in stmt_upper
                    for keyword in [
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "CREATE",
                        "DROP",
                        "ALTER",
                    ]
                ):
                    print(f"Warning: Statement might be incomplete: {stmt}")

            return True
        except Exception as e:
            print(f"Error validating SQL: {e}")
            return False

    def extract_table_names(self) -> List[str]:
        """Extract table names from the SQL file."""
        tables = set()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Simple regex pattern for table names
            # Note: This is a basic implementation and might miss some edge cases
            patterns = [
                r"FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                r"JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                r"UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                r"CREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            ]

            for pattern in patterns:
                tables.update(re.findall(pattern, content, re.IGNORECASE))

            return sorted(list(tables))
        except Exception as e:
            print(f"Error extracting table names: {e}")
            return []

    def example(self):
        sample_sql = """-- Sample SQL file with common operations
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    salary DECIMAL(10,2),
    hire_date DATE
);

INSERT INTO employees (name, department, salary, hire_date)
VALUES 
    ('John Doe', 'Engineering', 75000.00, '2023-01-15'),
    ('Jane Smith', 'Marketing', 65000.00, '2023-02-01');

-- Query to analyze employee data
SELECT 
    department,
    COUNT(*) as employee_count,
    AVG(salary) as avg_salary
FROM employees
GROUP BY department
HAVING COUNT(*) > 0
ORDER BY avg_salary DESC;

-- Update salary with conditions
UPDATE employees
SET salary = salary * 1.1
WHERE department = 'Engineering'
    AND hire_date < '2024-01-01';
"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".sql", mode="w", encoding="utf-8"
        ) as f:
            f.write(sample_sql)
        return f.name
