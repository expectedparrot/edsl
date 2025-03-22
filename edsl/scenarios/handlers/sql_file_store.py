import tempfile
import re
from typing import List
import textwrap


from ..file_methods import FileMethods

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
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            formatter = HtmlFormatter(style="monokai")
            highlighted_sql = pygments.highlight(content, SqlLexer(), formatter)
            css = formatter.get_style_defs(".highlight")
            display(HTML(f"<style>{css}</style>{highlighted_sql}"))
            display(FileLink(self.path))
        except Exception as e:
            print(f"Error displaying SQL: {e}")

    def _format_keywords(self, sql: str) -> str:
        """Capitalize SQL keywords."""
        keywords = {
            "select",
            "from",
            "where",
            "and",
            "or",
            "insert",
            "update",
            "delete",
            "create",
            "drop",
            "alter",
            "table",
            "into",
            "values",
            "group",
            "by",
            "having",
            "order",
            "limit",
            "join",
            "left",
            "right",
            "inner",
            "outer",
            "on",
            "as",
            "distinct",
            "count",
            "sum",
            "avg",
            "max",
            "min",
            "between",
            "like",
            "in",
            "is",
            "null",
            "not",
            "case",
            "when",
            "then",
            "else",
            "end",
        }

        words = sql.split()
        formatted_words = []
        for word in words:
            lower_word = word.lower()
            if lower_word in keywords:
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.lower())
        return " ".join(formatted_words)

    def _indent_sql(self, sql: str) -> str:
        """Add basic indentation to SQL statement."""
        lines = sql.split("\n")
        indented_lines = []
        indent_level = 0

        for line in lines:
            line = line.strip()

            # Decrease indent for closing parentheses
            if line.startswith(")"):
                indent_level = max(0, indent_level - 1)

            # Add indentation
            if line:
                indented_lines.append("    " * indent_level + line)
            else:
                indented_lines.append("")

            # Increase indent after opening parentheses
            if line.endswith("("):
                indent_level += 1

            # Special cases for common SQL clauses
            lower_line = line.lower()
            if any(
                clause in lower_line
                for clause in [
                    "select",
                    "from",
                    "where",
                    "group by",
                    "having",
                    "order by",
                ]
            ):
                indent_level = 1

        return "\n".join(indented_lines)

    def format_sql(self) -> bool:
        """Format the SQL file with proper indentation and keyword capitalization."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Remove extra whitespace and format
            content = " ".join(content.split())
            content = self._format_keywords(content)
            content = self._indent_sql(content)

            # Wrap long lines
            wrapped_content = []
            for line in content.split("\n"):
                if len(line) > 80:
                    wrapped_line = textwrap.fill(
                        line, width=80, subsequent_indent="    "
                    )
                    wrapped_content.append(wrapped_line)
                else:
                    wrapped_content.append(line)

            formatted_sql = "\n".join(wrapped_content)

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

            # Handle both semicolon and GO statement terminators
            statements = []
            current_stmt = []

            for line in content.split("\n"):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("--"):
                    continue

                if line.endswith(";"):
                    current_stmt.append(line[:-1])  # Remove semicolon
                    statements.append(" ".join(current_stmt))
                    current_stmt = []
                elif line.upper() == "GO":
                    if current_stmt:
                        statements.append(" ".join(current_stmt))
                        current_stmt = []
                else:
                    current_stmt.append(line)

            # Add any remaining statement
            if current_stmt:
                statements.append(" ".join(current_stmt))

            return [stmt.strip() for stmt in statements if stmt.strip()]
        except Exception as e:
            print(f"Error splitting SQL statements: {e}")
            return []

    def validate_basic_syntax(self) -> bool:
        """
        Perform basic SQL syntax validation.
        This is a simple check and doesn't replace proper SQL parsing.
        """
        try:
            statements = self.split_statements()
            for stmt in statements:
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

                # Check for basic parentheses matching
                if stmt.count("(") != stmt.count(")"):
                    print(f"Error: Unmatched parentheses in statement: {stmt}")
                    return False

                # Check for basic quote matching
                if stmt.count("'") % 2 != 0:
                    print(f"Error: Unmatched quotes in statement: {stmt}")
                    return False

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
