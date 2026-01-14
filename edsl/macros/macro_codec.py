"""
Codec for Macro serialization.

Macro is a "manifest" that tracks references to independently-versioned components.
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
    from edsl.jobs import Jobs
    from edsl.macros import Macro


class MacroCodec:
    """Codec for Macro objects.

    Macro stores references (commit_hashes) to its components (Survey, Jobs)
    rather than the components themselves. This codec handles the conversion
    between live component objects and their refs.
    """

    def get_ref(self, component: Any) -> Optional[str]:
        """Get the commit_hash ref from a component.

        All event-sourced components (Survey, Jobs) have a commit_hash
        property from GitMixin.

        Args:
            component: A component object with a commit_hash property.

        Returns:
            The component's commit_hash string, or None if component is None.
        """
        if component is None:
            return None
        if hasattr(component, "commit_hash"):
            return component.commit_hash
        return None

    def encode_components(
        self,
        initial_survey: "Survey",
        jobs_object: "Jobs",
    ) -> Dict[str, Optional[str]]:
        """Encode component objects to their refs.

        Args:
            initial_survey: The Survey object.
            jobs_object: The Jobs object.

        Returns:
            Dict with component refs.
        """
        return {
            "initial_survey_ref": self.get_ref(initial_survey),
            "jobs_object_ref": self.get_ref(jobs_object),
        }

    def decode_component(
        self,
        component_type: str,
        ref: Optional[str],
        live_components: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Decode a ref back to a component object.

        Resolution strategy:
        1. Check if a live component with matching ref is provided
        2. If not, pull from Coop by ref

        Args:
            component_type: One of "initial_survey", "jobs_object"
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
        """Get the default empty component for a given type.

        Args:
            component_type: One of "initial_survey", "jobs_object"

        Returns:
            None for optional components.

        Raises:
            ValueError: If initial_survey is requested (it's required).
        """
        if component_type == "initial_survey":
            raise ValueError("initial_survey is required and cannot be None")

        if component_type == "jobs_object":
            # Jobs object is optional, return None
            return None

        raise ValueError(f"Unknown component type: {component_type}")

    def _pull_component(self, component_type: str, ref: str) -> Any:
        """Pull a component from Coop by its commit_hash.

        Args:
            component_type: One of "initial_survey", "jobs_object"
            ref: The commit_hash to pull.

        Returns:
            The pulled component object.

        Raises:
            ValueError: If the component cannot be pulled.
        """
        type_to_class = {
            "initial_survey": ("edsl.surveys", "Survey"),
            "jobs_object": ("edsl.jobs", "Jobs"),
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
            raise ValueError(
                f"Failed to pull {class_name} with ref {ref}: {e}"
            ) from e

    def decode_all_components(
        self,
        refs: Dict[str, Optional[str]],
        live_components: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Decode all component refs to objects.

        Args:
            refs: Dict with initial_survey_ref, jobs_object_ref
            live_components: Optional dict of live component objects.

        Returns:
            Dict with initial_survey, jobs_object as component objects.
        """
        return {
            "initial_survey": self.decode_component(
                "initial_survey",
                refs.get("initial_survey_ref"),
                live_components,
            ),
            "jobs_object": self.decode_component(
                "jobs_object",
                refs.get("jobs_object_ref"),
                live_components,
            ),
        }
