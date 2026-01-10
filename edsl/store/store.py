"""
Store class for event-sourced data storage.

The Store holds entries (list of dicts) and metadata, providing methods
for all operations that events can trigger.

Created: 2026-01-08
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, List


@dataclass
class Store:
    """Event-sourced data store holding entries and metadata.
    
    The Store is the central data structure that events operate on.
    Each method corresponds to an event type and mutates the store in-place.
    
    Attributes:
        entries: List of dictionaries, each representing a row/record.
        meta: Dictionary of metadata (e.g., codebook, pagination info).
    """
    entries: List[dict[str, Any]]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the store to a dictionary."""
        return asdict(self)

    # =========================================================================
    # Row/Entry Operations
    # =========================================================================

    def append(self, item: dict[str, Any]) -> "Store":
        """Append an entry to the store."""
        self.entries.append(item)
        return self

    def update_row(self, index: int, row: dict[str, Any]) -> "Store":
        """Replace an entry at the specified index."""
        self.entries[index] = row
        return self

    def remove_rows(self, indices: tuple[int, ...]) -> "Store":
        """Remove entries at specified indices."""
        indices_to_remove = set(indices)
        self.entries = [
            row for i, row in enumerate(self.entries) 
            if i not in indices_to_remove
        ]
        return self

    def insert_row(self, index: int, row: dict[str, Any]) -> "Store":
        """Insert an entry at a specified index."""
        self.entries.insert(index, row)
        return self

    def update_entry_field(self, index: int, field: str, value: Any) -> "Store":
        """Update a specific field in an entry at a given index."""
        self.entries[index][field] = value
        return self

    def clear_entries(self) -> "Store":
        """Remove all entries."""
        self.entries.clear()
        return self

    def replace_all_entries(self, entries: tuple[dict[str, Any], ...]) -> "Store":
        """Replace all entries with new ones."""
        self.entries = list(entries)
        return self

    def reorder_entries(self, new_order: tuple[int, ...]) -> "Store":
        """Reorder entries by new index positions."""
        self.entries = [self.entries[i] for i in new_order]
        return self

    def keep_rows_by_indices(self, indices: tuple[int, ...]) -> "Store":
        """Keep only entries at specified indices (inverse of remove_rows)."""
        indices_set = set(indices)
        self.entries = [
            row for i, row in enumerate(self.entries)
            if i in indices_set
        ]
        return self

    # =========================================================================
    # Field Operations
    # =========================================================================

    def add_field_to_all(self, field: str, value: Any) -> "Store":
        """Add a field with the same value to all entries."""
        for entry in self.entries:
            entry[field] = value
        return self

    def add_field_by_index(self, field: str, values: tuple[Any, ...]) -> "Store":
        """Add a field with values corresponding to each entry by index."""
        for i, entry in enumerate(self.entries):
            entry[field] = values[i]
        return self

    def drop_fields(self, fields: tuple[str, ...]) -> "Store":
        """Drop specified fields from all entries."""
        fields_set = set(fields)
        for entry in self.entries:
            for field in fields_set:
                entry.pop(field, None)
        return self

    def keep_fields(self, fields: tuple[str, ...]) -> "Store":
        """Keep only specified fields in all entries."""
        fields_set = set(fields)
        for i, entry in enumerate(self.entries):
            self.entries[i] = {k: v for k, v in entry.items() if k in fields_set}
        return self

    def rename_fields(self, rename_map: tuple[tuple[str, str], ...]) -> "Store":
        """Rename fields in all entries."""
        for entry in self.entries:
            for old_name, new_name in rename_map:
                if old_name in entry:
                    entry[new_name] = entry.pop(old_name)
        return self

    def reorder_keys(self, new_order: tuple[str, ...]) -> "Store":
        """Reorder keys in all entries according to the specified order."""
        self.entries = [
            {key: entry[key] for key in new_order if key in entry}
            for entry in self.entries
        ]
        return self

    def transform_field(self, field: str, new_field: str, new_values: tuple[Any, ...]) -> "Store":
        """Update field with pre-computed transformed values."""
        for i, entry in enumerate(self.entries):
            entry[new_field] = new_values[i]
        return self

    def uniquify_field(self, field: str, new_values: tuple[Any, ...]) -> "Store":
        """Update field values with pre-computed unique values."""
        for i, entry in enumerate(self.entries):
            if field in entry:
                entry[field] = new_values[i]
        return self

    # =========================================================================
    # Nested Field Operations
    # =========================================================================

    def drop_nested_fields(self, parent_field: str, fields: tuple[str, ...]) -> "Store":
        """Drop fields from a nested dict field in all entries."""
        fields_set = set(fields)
        for entry in self.entries:
            if parent_field in entry and isinstance(entry[parent_field], dict):
                for field in fields_set:
                    entry[parent_field].pop(field, None)
        return self

    def keep_nested_fields(self, parent_field: str, fields: tuple[str, ...]) -> "Store":
        """Keep only specified fields in a nested dict field."""
        fields_set = set(fields)
        for entry in self.entries:
            if parent_field in entry and isinstance(entry[parent_field], dict):
                entry[parent_field] = {
                    k: v for k, v in entry[parent_field].items()
                    if k in fields_set
                }
        return self

    def rename_nested_field(self, parent_field: str, old_name: str, new_name: str) -> "Store":
        """Rename a field within a nested dict field."""
        for entry in self.entries:
            if parent_field in entry and isinstance(entry[parent_field], dict):
                nested = entry[parent_field]
                if old_name in nested:
                    nested[new_name] = nested.pop(old_name)
        return self

    def add_nested_field_by_index(
        self, parent_field: str, field: str, values: tuple[Any, ...]
    ) -> "Store":
        """Add a field to a nested dict with per-entry values."""
        for i, entry in enumerate(self.entries):
            if parent_field not in entry:
                entry[parent_field] = {}
            entry[parent_field][field] = values[i]
        return self

    def translate_nested_values(
        self, parent_field: str, value_map: tuple[tuple[str, tuple[tuple[Any, Any], ...]], ...]
    ) -> "Store":
        """Translate values in nested fields based on a mapping."""
        # Convert to more usable format: {field: {old: new, ...}}
        translations = {
            field: dict(mappings)
            for field, mappings in value_map
        }
        for entry in self.entries:
            if parent_field in entry and isinstance(entry[parent_field], dict):
                nested = entry[parent_field]
                for field, mapping in translations.items():
                    if field in nested and nested[field] in mapping:
                        nested[field] = mapping[nested[field]]
        return self

    def numberify_nested_fields(
        self, parent_field: str, conversions: tuple[tuple[int, str, Any], ...]
    ) -> "Store":
        """Apply pre-computed numeric conversions to nested fields."""
        for entry_idx, field, new_value in conversions:
            if parent_field in self.entries[entry_idx]:
                self.entries[entry_idx][parent_field][field] = new_value
        return self

    def set_field_by_index(self, field: str, values: tuple[Any, ...]) -> "Store":
        """Set a top-level field with per-entry values."""
        for i, entry in enumerate(self.entries):
            entry[field] = values[i]
        return self

    def collapse_by_field(
        self, group_field: str, merge_field: str, result_entries: tuple[dict[str, Any], ...]
    ) -> "Store":
        """Replace entries with pre-computed collapsed entries."""
        # The collapsing logic is done by the caller; we just apply the result
        self.entries = list(result_entries)
        return self

    # =========================================================================
    # Value Operations
    # =========================================================================

    def fill_na(self, fill_value: Any) -> "Store":
        """Fill NA/None values with a specified value."""
        import math
        
        def is_null(val):
            if val is None:
                return True
            if isinstance(val, float):
                try:
                    if math.isnan(val):
                        return True
                except (TypeError, ValueError):
                    pass
            if hasattr(val, "__str__"):
                str_val = str(val).lower()
                if str_val in ["nan", "none", "null", ""]:
                    return True
            return False
        
        for entry in self.entries:
            for key in entry:
                if is_null(entry[key]):
                    entry[key] = fill_value
        return self

    def string_cat_field(self, field: str, addend: str, position: str) -> "Store":
        """Concatenate a string to a field in all entries."""
        for entry in self.entries:
            if field in entry:
                current = entry[field]
                if isinstance(current, str):
                    if position == "prefix":
                        entry[field] = addend + current
                    else:  # suffix
                        entry[field] = current + addend
        return self

    def replace_values(self, replacements: tuple[tuple[str, Any], ...]) -> "Store":
        """Replace values in all entries based on a mapping."""
        replacements_dict = dict(replacements)
        for entry in self.entries:
            for key in entry:
                str_val = str(entry[key])
                if str_val in replacements_dict:
                    entry[key] = replacements_dict[str_val]
        return self

    def numberify(self, conversions: tuple[tuple[int, str, Any], ...]) -> "Store":
        """Apply pre-computed numeric conversions."""
        for entry_idx, field, new_value in conversions:
            self.entries[entry_idx][field] = new_value
        return self

    # =========================================================================
    # Meta Operations
    # =========================================================================

    def set_meta(self, key: str, value: Any) -> "Store":
        """Set a single key-value pair in meta."""
        self.meta[key] = value
        return self

    def update_meta(self, updates: dict[str, Any]) -> "Store":
        """Merge multiple key-value pairs into meta."""
        self.meta.update(updates)
        return self

    def remove_meta_key(self, key: str) -> "Store":
        """Remove a key from meta."""
        self.meta.pop(key, None)
        return self

    # =========================================================================
    # Composite Operations
    # =========================================================================

    def replace_entries_and_meta(
        self, entries: tuple[dict[str, Any], ...], meta_updates: tuple[tuple[str, Any], ...]
    ) -> "Store":
        """Replace all entries and update meta in one operation."""
        self.entries = list(entries)
        for key, value in meta_updates:
            self.meta[key] = value
        return self

    # =========================================================================
    # Survey-Specific Operations
    # =========================================================================

    def _ensure_rule_collection(self) -> None:
        """Ensure rule_collection structure exists in meta."""
        if "rule_collection" not in self.meta:
            self.meta["rule_collection"] = {"rules": [], "num_questions": None}
        elif "rules" not in self.meta["rule_collection"]:
            self.meta["rule_collection"]["rules"] = []

    def add_rule(self, rule_dict: dict[str, Any]) -> "Store":
        """Add a rule to the rule_collection in meta."""
        self._ensure_rule_collection()
        self.meta["rule_collection"]["rules"].append(rule_dict)
        # Update num_questions based on current_q
        current_q = rule_dict.get("current_q", 0)
        if self.meta["rule_collection"]["num_questions"] is None:
            self.meta["rule_collection"]["num_questions"] = current_q + 1
        else:
            self.meta["rule_collection"]["num_questions"] = max(
                self.meta["rule_collection"]["num_questions"], 
                current_q + 1
            )
        return self

    def remove_rules_for_question(self, question_index: int) -> "Store":
        """Remove all rules associated with a specific question index."""
        self._ensure_rule_collection()
        self.meta["rule_collection"]["rules"] = [
            rule for rule in self.meta["rule_collection"]["rules"]
            if rule.get("current_q") != question_index
        ]
        return self

    def update_rule_indices(self, index_offset: int, from_index: int) -> "Store":
        """Update rule indices after question insertion/deletion."""
        self._ensure_rule_collection()
        for rule in self.meta["rule_collection"]["rules"]:
            if rule.get("current_q", 0) >= from_index:
                rule["current_q"] = rule.get("current_q", 0) + index_offset
            if isinstance(rule.get("next_q"), int) and rule.get("next_q", 0) >= from_index:
                rule["next_q"] = rule.get("next_q", 0) + index_offset
        # Update num_questions
        if self.meta["rule_collection"]["num_questions"] is not None:
            self.meta["rule_collection"]["num_questions"] += index_offset
        return self

    def set_memory_plan(self, memory_plan_dict: dict[str, Any]) -> "Store":
        """Set the memory plan in meta."""
        self.meta["memory_plan"] = memory_plan_dict
        return self

    def add_memory_for_question(self, focal_question: str, prior_questions: tuple[str, ...]) -> "Store":
        """Add memory entries for a specific question.
        
        Stores in the format expected by MemoryPlan.from_dict:
        {"data": {"focal_q": {"prior_questions": ["q1", "q2"]}}}
        """
        if "memory_plan" not in self.meta:
            self.meta["memory_plan"] = {"data": {}}
        if "data" not in self.meta["memory_plan"]:
            self.meta["memory_plan"]["data"] = {}
        # Store in Memory dict format
        self.meta["memory_plan"]["data"][focal_question] = {"prior_questions": list(prior_questions)}
        return self

    def add_question_group(self, group_name: str, start_index: int, end_index: int) -> "Store":
        """Add a question group to meta."""
        if "question_groups" not in self.meta:
            self.meta["question_groups"] = {}
        self.meta["question_groups"][group_name] = (start_index, end_index)
        return self

    def add_pseudo_index(self, name: str, pseudo_index: float) -> "Store":
        """Add a pseudo index for an instruction."""
        if "pseudo_indices" not in self.meta:
            self.meta["pseudo_indices"] = {}
        self.meta["pseudo_indices"][name] = pseudo_index
        return self

    def remove_pseudo_index(self, name: str) -> "Store":
        """Remove a pseudo index."""
        if "pseudo_indices" in self.meta:
            self.meta["pseudo_indices"].pop(name, None)
        return self

    def update_pseudo_indices(self, index_offset: int, from_index: float) -> "Store":
        """Update pseudo indices after insertion/deletion."""
        if "pseudo_indices" in self.meta:
            for name, idx in list(self.meta["pseudo_indices"].items()):
                if idx >= from_index:
                    self.meta["pseudo_indices"][name] = idx + index_offset
        return self

    # =========================================================================
    # Survey Composite Operations
    # =========================================================================

    def add_survey_question(
        self,
        question_row: dict[str, Any],
        index: int,
        rule_dict: dict[str, Any],
        pseudo_index_name: str,
        pseudo_index_value: float,
        is_interior: bool
    ) -> "Store":
        """Add a question to a survey atomically.
        
        This method:
        1. Inserts/appends the question entry
        2. Updates existing rule indices if interior insertion
        3. Adds the default rule for the question
        4. Updates existing pseudo indices if interior insertion
        5. Adds the pseudo index for the question
        """
        # 1. Insert the question entry
        if index == -1 or index >= len(self.entries):
            self.entries.append(question_row)
        else:
            self.entries.insert(index, question_row)
        
        # 2. Update existing rule indices if interior insertion
        if is_interior:
            self.update_rule_indices(1, index)
            self.update_pseudo_indices(1, index)
        
        # 3. Add the default rule
        self.add_rule(rule_dict)
        
        # 4. Add the pseudo index
        self.add_pseudo_index(pseudo_index_name, pseudo_index_value)
        
        return self

    def delete_survey_question(
        self,
        index: int,
        question_name: str
    ) -> "Store":
        """Delete a question from a survey atomically.
        
        This method:
        1. Removes rules for the question
        2. Updates remaining rule indices
        3. Removes the question entry
        4. Removes the pseudo index
        5. Updates remaining pseudo indices
        6. Updates memory_plan to remove the question
        """
        # 1. Remove rules for this question
        self.remove_rules_for_question(index)
        
        # 2. Update remaining rule indices (shift down by 1 for indices > deleted)
        self.update_rule_indices(-1, index + 1)
        
        # 3. Remove the question entry
        if 0 <= index < len(self.entries):
            self.entries.pop(index)
        
        # 4. Remove the pseudo index
        self.remove_pseudo_index(question_name)
        
        # 5. Update remaining pseudo indices
        self.update_pseudo_indices(-1, index + 1)
        
        # 6. Update memory_plan to remove the deleted question
        memory_plan = self.meta.get("memory_plan", {})
        if memory_plan:
            # Remove from survey_question_names
            survey_names = memory_plan.get("survey_question_names", [])
            if question_name in survey_names:
                name_idx = survey_names.index(question_name)
                survey_names = list(survey_names)
                survey_names.pop(name_idx)
                memory_plan["survey_question_names"] = survey_names
                
                # Remove corresponding survey_question_text
                survey_texts = list(memory_plan.get("survey_question_texts", []))
                if name_idx < len(survey_texts):
                    survey_texts.pop(name_idx)
                    memory_plan["survey_question_texts"] = survey_texts
            
            # Remove from memory_plan data (both as focal and prior question)
            data = memory_plan.get("data", {})
            # Remove as focal question
            if question_name in data:
                del data[question_name]
            # Remove as prior question in other focal questions
            for focal_q, memory_entry in list(data.items()):
                if isinstance(memory_entry, dict) and "prior_questions" in memory_entry:
                    prior_qs = memory_entry["prior_questions"]
                    if question_name in prior_qs:
                        memory_entry["prior_questions"] = [
                            q for q in prior_qs if q != question_name
                        ]
            memory_plan["data"] = data
            self.meta["memory_plan"] = memory_plan
        
        return self

    def move_survey_question(
        self,
        from_index: int,
        to_index: int,
        question_name: str,
        question_row: dict[str, Any],
        new_rule_dict: dict[str, Any]
    ) -> "Store":
        """Move a question within a survey atomically.
        
        Implemented as delete + insert with appropriate rule/index updates.
        The to_index refers to the desired final position in the result.
        """
        # Delete from old position
        self.delete_survey_question(from_index, question_name)
        
        # No adjustment needed - to_index refers to the final position
        # After delete, inserting at to_index gives the correct final position
        
        # Add at new position
        is_interior = to_index < len(self.entries)
        self.add_survey_question(
            question_row,
            to_index,
            new_rule_dict,
            question_name,
            float(to_index),
            is_interior
        )
        
        return self

    # =========================================================================
    # Serialization
    # =========================================================================

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Store":
        """Create a Store from a dictionary."""
        return cls(**data)

