"""
Codec for Jobs serialization.

Jobs is a "manifest" that tracks references to independently-versioned components.
The codec handles:
- Extracting commit_hashes from live component objects (encoding)
- Resolving commit_hashes back to component objects (decoding)

Component resolution requires either:
- Live objects in memory (passed to decode)
- Pulling from Coop by commit_hash

Created: 2026-01-14
"""

from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.surveys import Survey
    from edsl.agents import AgentList
    from edsl.language_models import ModelList
    from edsl.scenarios import ScenarioList


class JobsCodec:
    """Codec for Jobs objects.

    Jobs stores references (commit_hashes) to its four components rather than
    the components themselves. This codec handles the conversion between
    live component objects and their refs.
    """

    def get_ref(self, component: Any) -> str:
        """Get the commit_hash ref from a component.

        All event-sourced components (Survey, AgentList, ModelList, ScenarioList)
        have a commit_hash property from GitMixin.

        Args:
            component: A component object with a commit_hash property.

        Returns:
            The component's commit_hash string.

        Raises:
            AttributeError: If the component doesn't have a commit_hash.
        """
        if component is None:
            return None
        return component.commit_hash

    def encode_components(
        self,
        survey: "Survey",
        agents: "AgentList",
        models: "ModelList",
        scenarios: "ScenarioList",
    ) -> Dict[str, str]:
        """Encode component objects to their refs.

        Args:
            survey: The Survey object.
            agents: The AgentList object.
            models: The ModelList object.
            scenarios: The ScenarioList object.

        Returns:
            Dict with component refs.
        """
        return {
            "survey_ref": self.get_ref(survey),
            "agents_ref": self.get_ref(agents),
            "models_ref": self.get_ref(models),
            "scenarios_ref": self.get_ref(scenarios),
        }

    def decode_component(
        self,
        component_type: str,
        ref: str,
        live_components: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Decode a ref back to a component object.

        Resolution strategy:
        1. Check if a live component with matching ref is provided
        2. If not, pull from Coop by ref

        Args:
            component_type: One of "survey", "agents", "models", "scenarios"
            ref: The commit_hash to resolve.
            live_components: Optional dict of live component objects keyed by type.

        Returns:
            The resolved component object.

        Raises:
            ValueError: If the ref cannot be resolved.
        """
        if ref is None:
            return self._get_default_component(component_type)

        # Check live components first
        if live_components and component_type in live_components:
            live = live_components[component_type]
            if live is not None and self.get_ref(live) == ref:
                return live

        # Pull from Coop
        return self._pull_component(component_type, ref)

    def _get_default_component(self, component_type: str) -> Any:
        """Get the default empty component for a given type."""
        if component_type == "survey":
            raise ValueError("Survey is required and cannot be None")

        if component_type == "agents":
            from edsl.agents import AgentList

            return AgentList([])

        if component_type == "models":
            from edsl.language_models import ModelList

            return ModelList([])

        if component_type == "scenarios":
            from edsl.scenarios import ScenarioList

            return ScenarioList([])

        raise ValueError(f"Unknown component type: {component_type}")

    def _pull_component(self, component_type: str, ref: str) -> Any:
        """Pull a component from Coop by its commit_hash.

        Args:
            component_type: One of "survey", "agents", "models", "scenarios"
            ref: The commit_hash to pull.

        Returns:
            The pulled component object.

        Raises:
            ValueError: If the component cannot be pulled.
        """
        type_to_class = {
            "survey": ("edsl.surveys", "Survey"),
            "agents": ("edsl.agents", "AgentList"),
            "models": ("edsl.language_models", "ModelList"),
            "scenarios": ("edsl.scenarios", "ScenarioList"),
        }

        if component_type not in type_to_class:
            raise ValueError(f"Unknown component type: {component_type}")

        module_name, class_name = type_to_class[component_type]
        from importlib import import_module

        module = import_module(module_name)
        cls = getattr(module, class_name)

        # Pull by commit_hash
        # GitMixin provides pull() classmethod that can accept a ref
        try:
            return cls.pull(ref)
        except Exception as e:
            raise ValueError(f"Failed to pull {class_name} with ref {ref}: {e}") from e

    def decode_all_components(
        self,
        refs: Dict[str, str],
        live_components: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Decode all component refs to objects.

        Args:
            refs: Dict with survey_ref, agents_ref, models_ref, scenarios_ref
            live_components: Optional dict of live component objects.

        Returns:
            Dict with survey, agents, models, scenarios as component objects.
        """
        return {
            "survey": self.decode_component(
                "survey",
                refs.get("survey_ref"),
                live_components,
            ),
            "agents": self.decode_component(
                "agents",
                refs.get("agents_ref"),
                live_components,
            ),
            "models": self.decode_component(
                "models",
                refs.get("models_ref"),
                live_components,
            ),
            "scenarios": self.decode_component(
                "scenarios",
                refs.get("scenarios_ref"),
                live_components,
            ),
        }
