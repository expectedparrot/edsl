import tempfile
import json
from typing import Optional, Dict, Any

from ..file_methods import FileMethods

class JsonMethods(FileMethods):
    suffix = "json"

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
                print(f"Error opening JSON: {e}")
        else:
            print("JSON file was not found.")

    def view_notebook(self):
        from IPython.display import FileLink, JSON, display
        import json

        # Read and parse the JSON file
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = json.load(f)

            # Display formatted JSON
            display(JSON(content))

            # Provide download link
            display(FileLink(self.path))
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
        except Exception as e:
            print(f"Error reading file: {e}")

    def validate_json(self, schema: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate the JSON file against a schema if provided,
        or check if it's valid JSON if no schema is provided.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = json.load(f)

            if schema is not None:
                from jsonschema import validate

                validate(instance=content, schema=schema)

            return True
        except json.JSONDecodeError as e:
            print(f"Invalid JSON format: {e}")
            return False
        except Exception as e:
            print(f"Validation error: {e}")
            return False

    def pretty_print(self):
        """Pretty print the JSON content with proper indentation."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = json.load(f)

            pretty_json = json.dumps(content, indent=2, sort_keys=True)
            print(pretty_json)
        except Exception as e:
            print(f"Error pretty printing JSON: {e}")

    def example(self):
        sample_json = {
            "person": {
                "name": "John Doe",
                "age": 30,
                "contact": {"email": "john@example.com", "phone": "+1-555-555-5555"},
                "interests": ["programming", "data science", "machine learning"],
                "active": True,
                "metadata": {"last_updated": "2024-01-01", "version": 1.0},
            }
        }

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", mode="w", encoding="utf-8"
        ) as f:
            json.dump(sample_json, f, indent=2)
        return f.name

    def format_file(self):
        """Read, format, and write back the JSON with consistent formatting."""
        try:
            # Read the current content
            with open(self.path, "r", encoding="utf-8") as f:
                content = json.load(f)

            # Write back with consistent formatting
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, sort_keys=True)

            return True
        except Exception as e:
            print(f"Error formatting JSON file: {e}")
            return False
