import tempfile
from typing import List, Optional, Dict
import ast
import black
import subprocess
import sys
from importlib import util

from ..file_methods import FileMethods

class PyMethods(FileMethods):
    suffix = "py"

    def view_system(self):
        """Open the Python file in the system's default editor."""
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
                print(f"Error opening Python file: {e}")
        else:
            print("Python file was not found.")

    def view_notebook(self):
        """Display the Python file with syntax highlighting in a notebook."""
        from IPython.display import FileLink, display, HTML
        import pygments
        from pygments.lexers import PythonLexer
        from pygments.formatters import HtmlFormatter

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Create custom CSS for better visibility in both light and dark themes
            custom_css = """
            .highlight {
                background: var(--jp-cell-editor-background, #f7f7f7);
                border: 1px solid var(--jp-border-color2, #ddd);
                border-radius: 3px;
                padding: 1em;
                margin: 1em 0;
            }
            .highlight pre {
                margin: 0;
                color: var(--jp-content-font-color0, #000);
                background: transparent;
            }
            .highlight .hll { background-color: var(--jp-cell-editor-active-background, #ffffcc) }
            .highlight .c { color: #408080; font-style: italic } /* Comment */
            .highlight .k { color: #008000; font-weight: bold } /* Keyword */
            .highlight .o { color: #666666 } /* Operator */
            .highlight .s { color: #BA2121 } /* String */
            .highlight .n { color: var(--jp-content-font-color0, #000) } /* Name */
            .highlight .p { color: var(--jp-content-font-color0, #000) } /* Punctuation */
            """

            formatter = HtmlFormatter(style="default")
            highlighted_python = pygments.highlight(content, PythonLexer(), formatter)

            # Combine the custom CSS with basic formatter CSS
            css = formatter.get_style_defs(".highlight") + custom_css

            display(HTML(f"<style>{css}</style>{highlighted_python}"))
            display(FileLink(self.path))
        except Exception as e:
            print(f"Error displaying Python: {e}")

    def format_python(self) -> bool:
        """Format the Python file using black."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            # Format using black
            formatted_content = black.format_str(content, mode=black.FileMode())

            with open(self.path, "w", encoding="utf-8") as f:
                f.write(formatted_content)

            return True
        except Exception as e:
            print(f"Error formatting Python: {e}")
            return False

    def validate_syntax(self) -> bool:
        """Validate Python syntax using ast.parse."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            ast.parse(content)
            return True
        except SyntaxError as e:
            print(f"Syntax error in Python file: {e}")
            return False
        except Exception as e:
            print(f"Error validating Python: {e}")
            return False

    def extract_imports(self) -> List[str]:
        """Extract all import statements from the Python file."""
        imports = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for name in node.names:
                        imports.append(f"{module}.{name.name}")

            return sorted(list(set(imports)))
        except Exception as e:
            print(f"Error extracting imports: {e}")
            return []

    def extract_functions(self) -> List[str]:
        """Extract all function names from the Python file."""
        functions = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)

            return sorted(functions)
        except Exception as e:
            print(f"Error extracting functions: {e}")
            return []

    def extract_classes(self) -> List[str]:
        """Extract all class names from the Python file."""
        classes = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)

            return sorted(classes)
        except Exception as e:
            print(f"Error extracting classes: {e}")
            return []

    def get_docstrings(self) -> Dict[str, str]:
        """Extract docstrings for all functions and classes."""
        docstrings = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstrings[node.name] = docstring

            return docstrings
        except Exception as e:
            print(f"Error extracting docstrings: {e}")
            return {}

    def run_file(self, args: List[str] = None) -> Optional[int]:
        """Run the Python file as a script with optional arguments."""
        try:
            cmd = [sys.executable, self.path]
            if args:
                cmd.extend(args)

            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print("Errors:", result.stderr, file=sys.stderr)
            return result.returncode
        except Exception as e:
            print(f"Error running Python file: {e}")
            return None

    def check_dependencies(self) -> List[str]:
        """Check if all imported modules are available."""
        missing_deps = []
        try:
            imports = self.extract_imports()
            for imp in imports:
                # Get the top-level module name
                top_module = imp.split(".")[0]
                if not util.find_spec(top_module):
                    missing_deps.append(top_module)
            return missing_deps
        except Exception as e:
            print(f"Error checking dependencies: {e}")
            return []

    def example(self):
        """Create a sample Python file with common patterns."""
        sample_python = '''#!/usr/bin/env python3
"""Example Python module demonstrating common patterns."""

import sys
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Employee:
    """Represents an employee in the system."""
    name: str
    department: str
    salary: float
    hire_date: str


class EmployeeManager:
    """Manages employee operations."""

    def __init__(self):
        self.employees: List[Employee] = []

    def add_employee(self, employee: Employee) -> None:
        """Add a new employee to the system."""
        self.employees.append(employee)

    def get_department_stats(self, department: str) -> Optional[dict]:
        """Calculate statistics for a department."""
        dept_employees = [e for e in self.employees if e.department == department]
        
        if not dept_employees:
            return None
            
        return {
            'count': len(dept_employees),
            'avg_salary': sum(e.salary for e in dept_employees) / len(dept_employees)
        }


def main(args: List[str]) -> int:
    """Main entry point for the script."""
    manager = EmployeeManager()
    
    # Add sample employees
    manager.add_employee(Employee(
        "John Doe",
        "Engineering",
        75000.00,
        "2023-01-15"
    ))
    
    manager.add_employee(Employee(
        "Jane Smith",
        "Marketing",
        65000.00,
        "2023-02-01"
    ))
    
    # Print department statistics
    stats = manager.get_department_stats("Engineering")
    if stats:
        print(f"Engineering department stats: {stats}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".py", mode="w", encoding="utf-8"
        ) as f:
            f.write(sample_python)
        return f.name
