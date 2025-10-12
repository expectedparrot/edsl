from __future__ import annotations

from typing import Any, Dict, List, Optional
import importlib
import pkgutil
from types import ModuleType

from ..scenarios import Scenario, ScenarioList


class AppRegistry:
    """In-memory registry for instantiated App objects.

    - Maps application name (str) -> app instance
    - Can list apps as an `EDSL ScenarioList` with fields: ``name``, ``description``
    - Provides free-text search over name and description
    - Allows retrieval of an app by exact name
    """

    _apps_by_name: Dict[str, Any] = {}

    @classmethod
    def register(cls, app: Any) -> None:
        """Register an app instance by its `application_name`.

        Latest registration for the same name wins.
        """
        try:
            app_name = app.application_name
            # Extract name from TypedDict if necessary
            if isinstance(app_name, dict):
                name = app_name.get("name", "Unknown")
            else:
                name = str(app_name)
        except Exception as exc:
            raise TypeError("App must have an 'application_name' attribute") from exc
        cls._apps_by_name[name] = app

    @classmethod
    def get_app(cls, name: str) -> Any:
        """Return the app instance for the given name.

        Raises KeyError if not found.
        """
        return cls._apps_by_name[name]

    @classmethod
    def names(cls) -> List[str]:
        """Return a list of registered application names."""
        return list(cls._apps_by_name.keys())

    @classmethod
    def as_scenario_list(cls) -> ScenarioList:
        """Return a ScenarioList of apps with fields `name`, `description`, `parameters`.

        - `parameters` is a ScenarioList with fields: question_name, question_type, question_text
        """
        scenarios = []
        for name, app in cls._apps_by_name.items():
            description = getattr(app, "description", None)
            # App.parameters returns a ScenarioList
            parameters = getattr(app, "parameters", [])
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
        """Return registered apps as a ScenarioList (for nice notebook display)."""
        return cls.as_scenario_list()

    @classmethod
    def search(cls, query: Optional[str]) -> ScenarioList:
        """Free-text search across app name and description.

        - Case-insensitive
        - Matches if all whitespace-separated tokens appear in (name + description)
        - Empty or None query returns all apps
        """
        if not query:
            return cls.as_scenario_list()

        tokens = [t for t in str(query).strip().lower().split() if t]
        if not tokens:
            return cls.as_scenario_list()

        scenarios = []
        for name, app in cls._apps_by_name.items():
            description = getattr(app, "description", "") or ""
            haystack = f"{name} {description}".lower()
            if all(token in haystack for token in tokens):
                scenarios.append(Scenario({"name": name, "description": description}))
        return ScenarioList(scenarios)

    @classmethod
    def from_package(cls, package: str | ModuleType) -> List[str]:
        """Import a module or package and register all module-level `app` variables.

        Args:
            package: Dotted path to a module/package (e.g., "edsl.app.examples")
                     or an already-imported module object.

        Returns:
            List of application names that were registered from this load.

        Behavior:
            - If a module (not a package) is provided, it must define an `app` in
              its globals. If missing, a ValueError is raised.
            - If a package is provided, all importable submodules/subpackages are
              imported. Each module must define an `app`. If any module is missing
              `app`, a ValueError is raised identifying the offending module.
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
            if not hasattr(module, "app"):
                raise ValueError(
                    f"Module '{module.__name__}' does not define required 'app' variable"
                )
            app_obj = getattr(module, "app")
            cls.register(app_obj)
            # Extract name from TypedDict if necessary
            app_name = getattr(app_obj, "application_name", module.__name__)
            if isinstance(app_name, dict):
                app_name = app_name.get("name", module.__name__)
            loaded_names.append(str(app_name))

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


