"""
There are two problems: 

1) Keys that are not unique across data types
2) Keys that have the same name as a data type
"""
from typing import Any


class QuestionFields:
    """Constants for question-related field names."""
    TEXT = "question_text"
    OPTIONS = "question_options"
    TYPE = "question_type"


# List of all question fields for iteration
QUESTION_FIELDS = [QuestionFields.TEXT, QuestionFields.OPTIONS, QuestionFields.TYPE]


class AgentNamer:
    """Maintains a registry of agent names to ensure unique naming."""

    def __init__(self):
        self._registry = {}

    def get_name(self, agent: "Agent") -> str:
        """Get or create a unique name for an agent."""
        agent_id = id(agent)
        if agent_id not in self._registry:
            self._registry[agent_id] = f"Agent_{len(self._registry)}"
        return self._registry[agent_id]


# Global instance for agent naming
agent_namer = AgentNamer().get_name


class ResultBuilder:
    """Builds a structured result object from raw survey data.
    
    This class takes raw survey data and indices, constructs organized sub-dictionaries
    for different data types (agent, model, answers, etc.), resolves any key naming
    conflicts, and merges everything into a single combined dictionary for easy access.
    
    The builder handles two main problems:
    1) Keys that are not unique across data types
    2) Keys that have the same name as a data type
    
    Key conflicts are resolved by renaming conflicting keys with their data type suffix,
    with 'answer' data type getting priority to avoid renaming survey responses when possible.
    """

    def __init__(self, data: dict, indices: dict):
        """Initialize the ResultBuilder with raw data and indices.
        
        Args:
            data: Raw survey data dictionary containing answers, questions, agents, etc.
            indices: Dictionary containing index information for agents, scenarios, models
        """
        self.data = data
        self.indices = indices
        self._build_result()

    def _build_result(self):
        """Main build process: construct, analyze conflicts, resolve, and merge."""
        sub_dicts = self._construct_sub_dicts()
        self.keys_to_data_types, conflicts = self._analyze_key_conflicts(sub_dicts)
        resolved_sub_dicts = self._resolve_conflicts(sub_dicts, conflicts)
        self.sub_dicts = resolved_sub_dicts
        self.combined_dict, self.problem_keys = self._merge_sub_dicts(resolved_sub_dicts)

    def _construct_sub_dicts(self) -> dict[str, dict]:
        """Construct all sub-dictionaries ready for merging."""
        sub_dicts = {}
        sub_dicts.update(self._build_core_components())
        sub_dicts.update(self._build_question_components())
        sub_dicts.update(self._build_cache_components())
        sub_dicts.update(self._build_metadata_components())
        self._add_indices_if_available(sub_dicts)
        return sub_dicts

    def _analyze_key_conflicts(self, sub_dicts: dict) -> tuple[dict, list]:
        """Analyze conflicts in key mappings with priority for 'answer' data type.
        
        This creates a mapping of attribute names to their container data types and
        identifies conflicts that need resolution. The 'answer' data type gets priority
        to ensure answer keys are not renamed when possible.
        
        Returns:
            Tuple of (key_to_data_type_mapping, list_of_conflicts)
        """
        key_mappings = {}
        conflicts = []
        
        # Process data types with 'answer' first to give it priority
        data_types = sorted(sub_dicts.keys())
        if "answer" in data_types:
            data_types.remove("answer")
            data_types = ["answer"] + data_types
        
        for data_type in data_types:
            for key in sub_dicts[data_type]:
                if key in key_mappings:
                    import warnings
                    warnings.warn(
                        f"Key '{key}' of data type '{data_type}' is already in use. "
                        f"Renaming to {key}_{data_type}.\n"
                        f"Conflicting data_type for this key at {key_mappings[key]}"
                    )
                    conflicts.append((key, data_type))
                else:
                    key_mappings[key] = data_type
                    
        return key_mappings, conflicts

    def _resolve_conflicts(self, sub_dicts: dict, conflicts: list) -> dict:
        """Resolve conflicts by renaming keys."""
        resolved_sub_dicts = {k: dict(v) for k, v in sub_dicts.items()}  # deep copy
        for key, data_type in conflicts:
            if key in resolved_sub_dicts[data_type]:
                new_key = f"{key}_{data_type}"
                resolved_sub_dicts[data_type][new_key] = resolved_sub_dicts[data_type].pop(key)
        return resolved_sub_dicts

    def _merge_sub_dicts(self, resolved_sub_dicts: dict) -> tuple[dict, list]:
        """Merge all sub-dictionaries into a single combined dictionary.
        
        This method merges all the individual sub-dictionaries into one combined
        dictionary, and also adds each sub-dictionary itself as a key for structured access.
        """
        combined = {}
        problem_keys = []
        
        for key, sub_dict in resolved_sub_dicts.items():
            # First update with the contents of the sub-dictionary
            combined.update(sub_dict)
            
            # Check if the sub-dict key conflicts with any of its contents
            if key in combined:
                problem_keys.append(key)
                
            # Add the entire sub-dictionary as a value under its key
            combined[key] = sub_dict
            
        return combined, problem_keys

    def _add_indices_if_available(self, sub_dicts: dict) -> None:
        """Add indices to sub-dictionaries if available."""
        if self.indices:
            sub_dicts["agent"]["agent_index"] = self.indices["agent"]
            sub_dicts["scenario"]["scenario_index"] = self.indices["scenario"]
            sub_dicts["model"]["model_index"] = self.indices["model"]

    def _build_core_components(self) -> dict:
        """Build core components (agent, model, iteration)."""
        core_components = {}
        core_components.update(self._create_agent_sub_dict(self.data["agent"]))
        core_components.update(self._create_model_sub_dict(self.data["model"]))
        core_components.update(self._iteration_sub_dict(self.data["iteration"]))
        return core_components

    def _build_question_components(self) -> dict:
        """Build question-related sub-dictionaries."""
        question_attribute_maps = {field: {} for field in QUESTION_FIELDS}

        for question_name in self.data["answer"]:
            if question_name in self.data['question_to_attributes']:
                for field_name in question_attribute_maps:
                    new_key = f"{question_name}_{field_name}"
                    question_attribute_maps[field_name][new_key] = (
                        self.data['question_to_attributes'][question_name][field_name]
                    )
        return question_attribute_maps

    def _build_cache_components(self) -> dict:
        """Build cache-related sub-dictionaries."""
        new_cache_dict = {
            f"{k}_cache_used": v for k, v in self.data["cache_used_dict"].items()
        }

        cache_keys = {f"{k}_cache_key": v for k, v in self.data["cache_keys"].items()}

        return {
            "cache_used": new_cache_dict,
            "cache_keys": cache_keys,
        }

    def _build_metadata_components(self) -> dict:
        """Build metadata sub-dictionaries."""
        return {
            "scenario": self.data["scenario"],
            "answer": self.data["answer"],
            "prompt": self.data["prompt"],
            "comment": self.data["comments_dict"],
            "reasoning_summary": self.data["reasoning_summaries_dict"],
            "generated_tokens": self.data["generated_tokens"],
            "raw_model_response": self.data["raw_model_response"],
            "validated": self.data["validated_dict"],
        }

    # Static factory methods for sub-dictionaries
    @staticmethod
    def _create_agent_sub_dict(agent) -> dict:
        """Create a dictionary of agent details."""
        if agent.name is None:
            agent_name = agent_namer(agent)
        else:
            agent_name = agent.name

        return {
            "agent": agent.traits
            | {"agent_name": agent_name}
            | {"agent_instruction": agent.instruction},
        }

    @staticmethod
    def _create_model_sub_dict(model) -> dict:
        """Create a dictionary of model details."""
        return {
            "model": model.parameters
            | {"model": model.model}
            | {"inference_service": model._inference_service_},
        }

    @staticmethod
    def _iteration_sub_dict(iteration) -> dict:
        """Create a dictionary of iteration details."""
        return {
            "iteration": {"iteration": iteration},
        }
    
    @classmethod
    def example(cls):
        """Create an example ResultBuilder instance for testing."""
        from edsl.results import Result
        data = Result.example()
        indices = Result.example().indices 
        return cls(data, indices)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
