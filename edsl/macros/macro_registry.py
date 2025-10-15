from __future__ import annotations

from typing import Any, Dict, List, Optional
import importlib
import pkgutil
from types import ModuleType

from ..scenarios import Scenario, ScenarioList


class MacroRegistry:
    """In-memory registry for instantiated Macro objects.

    - Maps macro name (str) -> macro instance
    - Can list macros as an `EDSL ScenarioList` with fields: ``name``, ``description``
    - Provides free-text search over name and description
    - Allows retrieval of a macro by exact name
    """

    _macros_by_name: Dict[str, Any] = {}

    @classmethod
    def register(cls, macro: Any) -> None:
        """Register a macro instance by its `application_name`.

        Latest registration for the same name wins.
        """
        try:
            macro_name = macro.application_name
            # Extract name from TypedDict if necessary
            if isinstance(macro_name, dict):
                name = macro_name.get("name", "Unknown")
            else:
                name = str(macro_name)
        except Exception as exc:
            raise TypeError("Macro must have an 'application_name' attribute") from exc
        cls._macros_by_name[name] = macro

    @classmethod
    def get_macro(cls, name: str) -> Any:
        """Return the macro instance for the given name.

        Raises KeyError if not found.
        """
        return cls._macros_by_name[name]

    @classmethod
    def names(cls) -> List[str]:
        """Return a list of registered macro names."""
        return list(cls._macros_by_name.keys())

    @classmethod
    def as_scenario_list(cls) -> ScenarioList:
        """Return a ScenarioList of macros with fields `name`, `description`, `parameters`.

        - `parameters` is a ScenarioList with fields: question_name, question_type, question_text
        """
        scenarios = []
        for name, macro in cls._macros_by_name.items():
            description = getattr(macro, "description", None)
            # Macro.parameters returns a ScenarioList
            parameters = getattr(macro, "parameters", [])
            scenarios.append(
                Scenario({
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                })
            )
        return ScenarioList(scenarios)

    @classmethod
    def list(cls) -> ScenarioList:
        """Return registered macros as a ScenarioList (for nice notebook display)."""
        return cls.as_scenario_list()

    @classmethod
    def search(cls, query: Optional[str]) -> ScenarioList:
        """Free-text search across macro name and description.

        - Case-insensitive
        - Matches if all whitespace-separated tokens appear in (name + description)
        - Empty or None query returns all macros
        """
        if not query:
            return cls.as_scenario_list()

        tokens = [t for t in str(query).strip().lower().split() if t]
        if not tokens:
            return cls.as_scenario_list()

        scenarios = []
        for name, macro in cls._macros_by_name.items():
            description = getattr(macro, "description", "") or ""
            haystack = f"{name} {description}".lower()
            if all(token in haystack for token in tokens):
                scenarios.append(Scenario({"name": name, "description": description}))
        return ScenarioList(scenarios)

    @classmethod
    def from_package(cls, package: str | ModuleType) -> List[str]:
        """Import a module or package and register all module-level `macro` variables.

        Args:
            package: Dotted path to a module/package (e.g., "edsl.macros.examples")
                     or an already-imported module object.

        Returns:
            List of macro names that were registered from this load.

        Behavior:
            - If a module (not a package) is provided, it must define a `macro` in
              its globals. If missing, a ValueError is raised.
            - If a package is provided, all importable submodules/subpackages are
              imported. Each module must define a `macro`. If any module is missing
              `macro`, a ValueError is raised identifying the offending module.
        """
        # Resolve package to a module object
        mod: ModuleType
        if isinstance(package, str):
            mod = importlib.import_module(package)
        elif isinstance(package, ModuleType):
            mod = package
        else:
            raise TypeError("package must be a module object or dotted path string")

        loaded_names: List[str] = []

        def _load_module(module: ModuleType) -> None:
            if not hasattr(module, "__dict__"):
                raise ValueError(f"Invalid module: {module!r}")
            if not hasattr(module, "macro"):
                raise ValueError(
                    f"Module '{module.__name__}' does not define required 'macro' variable"
                )
            macro_obj = getattr(module, "macro")
            cls.register(macro_obj)
            # Extract name from TypedDict if necessary
            macro_name = getattr(macro_obj, "application_name", module.__name__)
            if isinstance(macro_name, dict):
                macro_name = macro_name.get("name", module.__name__)
            loaded_names.append(str(macro_name))

        # If it's a package, walk all submodules recursively; otherwise load the module itself
        if hasattr(mod, "__path__"):
            # Walk packages and modules under this package
            prefix = mod.__name__ + "."
            for finder, name, ispkg in pkgutil.walk_packages(getattr(mod, "__path__"), prefix=prefix):
                submodule = importlib.import_module(name)
                _load_module(submodule)
        else:
            _load_module(mod)

        #return loaded_names


