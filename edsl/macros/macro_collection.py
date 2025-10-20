"""MacroCollection class for managing collections of EDSL macros."""

import importlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from edsl.macros.macro import Macro
from edsl.macros.composite_macro import CompositeMacro


class MacroCollection:
    """A collection of EDSL macros that can be loaded from various sources.

    This class provides methods to load macros from directories, filter them,
    and manage collections of related macros.
    """

    def __init__(
        self, macros: Optional[List[Macro]] = None, name: Optional[str] = None
    ):
        """Initialize a MacroCollection.

        Args:
            macros: List of Macro instances to include in the collection
            name: Optional name for the collection
        """
        self.macros = macros or []
        self.name = name or "Unnamed Collection"
        self._macro_index = {macro.application_name: macro for macro in self.macros}

    def __len__(self) -> int:
        """Return the number of macros in the collection."""
        return len(self.macros)

    def __getitem__(self, key: str) -> Macro:
        """Get a macro by application_name."""
        return self._macro_index[key]

    def __contains__(self, key: str) -> bool:
        """Check if a macro with the given application_name exists."""
        return key in self._macro_index

    def __iter__(self):
        """Iterate over macros in the collection."""
        return iter(self.macros)

    def __repr__(self) -> str:
        """String representation of the collection."""
        return f"MacroCollection(name='{self.name}', macros={len(self.macros)})"

    def add_macro(self, macro: Macro) -> None:
        """Add a macro to the collection.

        Args:
            macro: The Macro instance to add
        """
        self.macros.append(macro)
        self._macro_index[macro.application_name] = macro

    def remove_macro(self, application_name: str) -> bool:
        """Remove a macro from the collection by application_name.

        Args:
            application_name: The application_name of the macro to remove

        Returns:
            True if the macro was found and removed, False otherwise
        """
        if application_name in self._macro_index:
            macro_to_remove = self._macro_index[application_name]
            self.macros.remove(macro_to_remove)
            del self._macro_index[application_name]
            return True
        return False

    def get_macro(self, application_name: str) -> Optional[Macro]:
        """Get a macro by application_name.

        Args:
            application_name: The application_name of the macro to retrieve

        Returns:
            The Macro instance if found, None otherwise
        """
        return self._macro_index.get(application_name)

    def list_macros(self) -> List[Dict[str, Any]]:
        """Get a list of macro metadata.

        Returns:
            List of dictionaries containing macro metadata
        """
        return [
            {
                "application_name": macro.application_name,
                "display_name": macro.display_name,
                "short_description": macro.short_description,
                "long_description": macro.long_description,
                "application_type": getattr(macro, "application_type", "base"),
            }
            for macro in self.macros
        ]

    def filter_by_type(self, application_type: str) -> "MacroCollection":
        """Filter macros by application type.

        Args:
            application_type: The application type to filter by

        Returns:
            A new MacroCollection containing only macros of the specified type
        """
        filtered_macros = [
            macro
            for macro in self.macros
            if getattr(macro, "application_type", "base") == application_type
        ]
        return MacroCollection(
            macros=filtered_macros,
            name=f"{self.name} (filtered by type: {application_type})",
        )

    def filter_by_name_pattern(self, pattern: str) -> "MacroCollection":
        """Filter macros by name pattern.

        Args:
            pattern: Pattern to match against application_name or display_name

        Returns:
            A new MacroCollection containing only macros matching the pattern
        """
        filtered_macros = [
            macro
            for macro in self.macros
            if (
                pattern.lower() in macro.application_name.lower()
                or pattern.lower() in macro.display_name.lower()
            )
        ]
        return MacroCollection(
            macros=filtered_macros, name=f"{self.name} (filtered by pattern: {pattern})"
        )

    # def deploy(
    #     self, owner: str, server_url: str = "http://localhost:8000", force: bool = True
    # ) -> Dict[str, Any]:
    #     """Deploy all macros in the collection to a server.

    #     Args:
    #         owner: The owner for the deployed macros
    #         server_url: The server URL to deploy to
    #         force: Whether to force deployment if macros already exist

    #     Returns:
    #         Dictionary with deployment results
    #     """
    #     results = {"successful": [], "failed": [], "skipped": []}

    #     for macro in self.macros:
    #         try:
    #             result = macro.deploy(owner=owner, server_url=server_url, force=force)
    #             results["successful"].append(
    #                 {
    #                     "application_name": macro.application_name,
    #                     "display_name": macro.display_name,
    #                     "result": result,
    #                 }
    #             )
    #         except Exception as e:
    #             if "already exists" in str(e):
    #                 results["skipped"].append(
    #                     {
    #                         "application_name": macro.application_name,
    #                         "display_name": macro.display_name,
    #                         "reason": "Already exists",
    #                     }
    #                 )
    #             else:
    #                 results["failed"].append(
    #                     {
    #                         "application_name": macro.application_name,
    #                         "display_name": macro.display_name,
    #                         "error": str(e),
    #                     }
    #                 )

    #     return results

    @classmethod
    def from_examples_directory(
        cls, examples_dir: Optional[str] = None, recursive: bool = True
    ) -> "MacroCollection":
        """Load all macros from the edsl/macros/examples directory.

        Args:
            examples_dir: Path to the examples directory. If None, uses the default edsl/macros/examples
            recursive: Whether to search subdirectories recursively

        Returns:
            MacroCollection containing all found macros
        """
        if examples_dir is None:
            # Get the path to the examples directory relative to this file
            current_dir = Path(__file__).parent
            examples_dir = current_dir / "examples"

        examples_path = Path(examples_dir)
        if not examples_path.exists():
            raise ValueError(f"Examples directory not found: {examples_path}")

        macros = []
        loaded_modules = []

        # Find all Python files
        if recursive:
            python_files = list(examples_path.rglob("*.py"))
        else:
            python_files = list(examples_path.glob("*.py"))

        # Filter out utility files and __pycache__
        python_files = [
            f
            for f in python_files
            if not f.name.startswith("__")
            and f.name not in ["load_all_apps.py", "load_apps_simple.py"]
            and "__pycache__" not in str(f)
        ]

        for py_file in python_files:
            try:
                # Convert file path to module name
                relative_path = py_file.relative_to(examples_path)
                module_parts = list(relative_path.parts)
                module_parts[-1] = module_parts[-1][:-3]  # Remove .py extension

                module_name = f"edsl.macros.examples.{'.'.join(module_parts)}"

                # Import the module
                try:
                    module = importlib.import_module(module_name)
                    loaded_modules.append(module_name)
                except ImportError as e:
                    print(f"Warning: Could not import {module_name}: {e}")
                    continue

                # Look for an 'app' variable in the module (kept for backward compatibility)
                if hasattr(module, "app"):
                    macro = getattr(module, "app")
                    if isinstance(macro, (Macro, CompositeMacro)):
                        macros.append(macro)
                        print(
                            f"✓ Loaded macro: {macro.application_name} from {module_name}"
                        )
                    else:
                        print(
                            f"Warning: 'app' in {module_name} is not a Macro instance"
                        )
                else:
                    # Some modules might have multiple macros or different variable names
                    # Look for any variable that is a Macro instance
                    macro_candidates = []
                    for attr_name in dir(module):
                        if not attr_name.startswith("_"):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, (Macro, CompositeMacro)):
                                macro_candidates.append((attr_name, attr))

                    if macro_candidates:
                        for attr_name, macro in macro_candidates:
                            macros.append(macro)
                            print(
                                f"✓ Loaded macro: {macro.application_name} (as {attr_name}) from {module_name}"
                            )
                    else:
                        print(f"Info: No Macro instances found in {module_name}")

            except Exception as e:
                print(f"Error processing {py_file}: {e}")
                continue

        print(f"\nLoaded {len(macros)} macros from {len(loaded_modules)} modules")
        return cls(macros=macros, name="EDSL Examples Collection")

    @classmethod
    def from_list(
        cls, macro_identifiers: List[str], server_url: str = "http://localhost:8000"
    ) -> "MacroCollection":
        """Load specific macros by their identifiers (qualified names or macro IDs).

        Args:
            macro_identifiers: List of macro identifiers (qualified names or macro IDs)
            server_url: The server URL to load macros from

        Returns:
            MacroCollection containing the specified macros
        """
        from edsl.macros import Macro

        macros = []
        for identifier in macro_identifiers:
            try:
                macro = Macro(identifier, server_url=server_url)
                macros.append(macro)
                print(f"✓ Loaded macro: {macro.application_name}")
            except Exception as e:
                print(f"Warning: Could not load macro {identifier}: {e}")

        return cls(macros=macros, name="Custom Macros Collection")


# Convenience function for loading examples
def load_examples_collection() -> MacroCollection:
    """Load all macros from the examples directory.

    Returns:
        MacroCollection containing all example macros
    """
    return MacroCollection.from_examples_directory()


if __name__ == "__main__":
    collection = load_examples_collection()
    for macro in collection:
        # macro.push(visibility="public", description=macro.short_description, alias=macro.alias())
        macro.deploy(overwrite=True)
    # collection.deploy(owner="johnhorton", force=True)
