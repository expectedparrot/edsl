#!/usr/bin/env python3
"""
Generate test fixtures for TypeScript parity testing.

This script creates JSON fixtures containing:
- Initial store state
- Event to apply
- Expected store state after applying the event

These fixtures are used by TypeScript tests to verify that the
TypeScript implementation produces identical results to Python.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import store modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from edsl.store.store import Store
from edsl.store.events import (
    # Row/Entry Events
    AppendRowEvent,
    UpdateRowEvent,
    RemoveRowsEvent,
    InsertRowEvent,
    UpdateEntryFieldEvent,
    ClearEntriesEvent,
    ReplaceAllEntriesEvent,
    ReorderEntriesEvent,
    KeepRowsByIndicesEvent,
    # Field Events
    AddFieldToAllEntriesEvent,
    AddFieldByIndexEvent,
    DropFieldsEvent,
    KeepFieldsEvent,
    RenameFieldsEvent,
    ReorderKeysEvent,
    TransformFieldEvent,
    UniquifyFieldEvent,
    # Value Events
    FillNaEvent,
    StringCatFieldEvent,
    ReplaceValuesEvent,
    NumberifyEvent,
    # Meta Events
    SetMetaEvent,
    UpdateMetaEvent,
    RemoveMetaKeyEvent,
    # Composite Events
    ReplaceEntriesAndMetaEvent,
    # Nested Field Events
    DropNestedFieldsEvent,
    KeepNestedFieldsEvent,
    RenameNestedFieldEvent,
    AddNestedFieldByIndexEvent,
    TranslateNestedValuesEvent,
    NumberifyNestedFieldsEvent,
    # Agent-Specific Events
    SetAgentNamesEvent,
    CollapseByFieldEvent,
    # Survey-Specific Events
    AddRuleEvent,
    RemoveRulesForQuestionEvent,
    UpdateRuleIndicesEvent,
    SetMemoryPlanEvent,
    AddMemoryForQuestionEvent,
    AddQuestionGroupEvent,
    AddPseudoIndexEvent,
    RemovePseudoIndexEvent,
    UpdatePseudoIndicesEvent,
    # Survey Composite Events
    AddSurveyQuestionEvent,
    DeleteSurveyQuestionEvent,
    MoveSurveyQuestionEvent,
    # Dispatcher
    apply_event,
)


def create_fixture(
    name: str, initial_store: Store, event, description: str = ""
) -> dict:
    """Create a test fixture from an initial store and event."""
    import copy

    # Deep copy the initial store to preserve it (must be true deep copy)
    initial_dict = copy.deepcopy(initial_store.to_dict())

    # Apply the event to another deep copy
    store_copy = Store.from_dict(copy.deepcopy(initial_dict))
    apply_event(event, store_copy)
    result_dict = store_copy.to_dict()

    return {
        "name": name,
        "description": description,
        "initial_store": initial_dict,
        "event": {"name": event.name, "payload": event.payload},
        "expected_store": result_dict,
    }


def generate_fixtures() -> list[dict]:
    """Generate all test fixtures."""
    fixtures = []

    # ==========================================================================
    # Row/Entry Events
    # ==========================================================================

    # AppendRowEvent
    fixtures.append(
        create_fixture(
            "append_row_to_empty",
            Store(entries=[], meta={}),
            AppendRowEvent(row={"id": 1, "name": "Alice"}),
            "Append a row to an empty store",
        )
    )

    fixtures.append(
        create_fixture(
            "append_row_to_existing",
            Store(entries=[{"id": 1, "name": "Alice"}], meta={}),
            AppendRowEvent(row={"id": 2, "name": "Bob"}),
            "Append a row to a store with existing entries",
        )
    )

    # UpdateRowEvent
    fixtures.append(
        create_fixture(
            "update_row",
            Store(entries=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}], meta={}),
            UpdateRowEvent(index=0, row={"id": 1, "name": "Alicia"}),
            "Update a row at a specific index",
        )
    )

    # RemoveRowsEvent
    fixtures.append(
        create_fixture(
            "remove_single_row",
            Store(
                entries=[
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                    {"id": 3, "name": "Charlie"},
                ],
                meta={},
            ),
            RemoveRowsEvent(indices=(1,)),
            "Remove a single row",
        )
    )

    fixtures.append(
        create_fixture(
            "remove_multiple_rows",
            Store(
                entries=[
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                    {"id": 3, "name": "Charlie"},
                    {"id": 4, "name": "Diana"},
                ],
                meta={},
            ),
            RemoveRowsEvent(indices=(0, 2)),
            "Remove multiple rows",
        )
    )

    # InsertRowEvent
    fixtures.append(
        create_fixture(
            "insert_row_at_beginning",
            Store(entries=[{"id": 2, "name": "Bob"}], meta={}),
            InsertRowEvent(index=0, row={"id": 1, "name": "Alice"}),
            "Insert a row at the beginning",
        )
    )

    fixtures.append(
        create_fixture(
            "insert_row_in_middle",
            Store(entries=[{"id": 1, "name": "Alice"}, {"id": 3, "name": "Charlie"}], meta={}),
            InsertRowEvent(index=1, row={"id": 2, "name": "Bob"}),
            "Insert a row in the middle",
        )
    )

    # UpdateEntryFieldEvent
    fixtures.append(
        create_fixture(
            "update_entry_field",
            Store(entries=[{"id": 1, "name": "Alice", "age": 25}], meta={}),
            UpdateEntryFieldEvent(index=0, field="age", value=26),
            "Update a specific field in an entry",
        )
    )

    # ClearEntriesEvent
    fixtures.append(
        create_fixture(
            "clear_entries",
            Store(entries=[{"id": 1}, {"id": 2}, {"id": 3}], meta={"key": "value"}),
            ClearEntriesEvent(),
            "Clear all entries",
        )
    )

    # ReplaceAllEntriesEvent
    fixtures.append(
        create_fixture(
            "replace_all_entries",
            Store(entries=[{"id": 1}, {"id": 2}], meta={}),
            ReplaceAllEntriesEvent(entries=({"id": 3}, {"id": 4}, {"id": 5})),
            "Replace all entries with new ones",
        )
    )

    # ReorderEntriesEvent
    fixtures.append(
        create_fixture(
            "reorder_entries",
            Store(
                entries=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}],
                meta={},
            ),
            ReorderEntriesEvent(new_order=(2, 0, 1)),
            "Reorder entries by new index positions",
        )
    )

    # KeepRowsByIndicesEvent
    fixtures.append(
        create_fixture(
            "keep_rows_by_indices",
            Store(
                entries=[
                    {"id": 1},
                    {"id": 2},
                    {"id": 3},
                    {"id": 4},
                    {"id": 5},
                ],
                meta={},
            ),
            KeepRowsByIndicesEvent(indices=(1, 3)),
            "Keep only rows at specified indices",
        )
    )

    # ==========================================================================
    # Field Events
    # ==========================================================================

    # AddFieldToAllEntriesEvent
    fixtures.append(
        create_fixture(
            "add_field_to_all",
            Store(entries=[{"id": 1}, {"id": 2}], meta={}),
            AddFieldToAllEntriesEvent(field="status", value="active"),
            "Add a field with the same value to all entries",
        )
    )

    # AddFieldByIndexEvent
    fixtures.append(
        create_fixture(
            "add_field_by_index",
            Store(entries=[{"id": 1}, {"id": 2}, {"id": 3}], meta={}),
            AddFieldByIndexEvent(field="score", values=(100, 200, 300)),
            "Add a field with per-entry values",
        )
    )

    # DropFieldsEvent
    fixtures.append(
        create_fixture(
            "drop_fields",
            Store(
                entries=[
                    {"id": 1, "name": "Alice", "age": 25, "city": "NYC"},
                    {"id": 2, "name": "Bob", "age": 30, "city": "LA"},
                ],
                meta={},
            ),
            DropFieldsEvent(fields=("age", "city")),
            "Drop specified fields from all entries",
        )
    )

    # KeepFieldsEvent
    fixtures.append(
        create_fixture(
            "keep_fields",
            Store(
                entries=[
                    {"id": 1, "name": "Alice", "age": 25, "city": "NYC"},
                    {"id": 2, "name": "Bob", "age": 30, "city": "LA"},
                ],
                meta={},
            ),
            KeepFieldsEvent(fields=("id", "name")),
            "Keep only specified fields in all entries",
        )
    )

    # RenameFieldsEvent
    fixtures.append(
        create_fixture(
            "rename_fields",
            Store(entries=[{"old_name": "value1", "other": "value2"}], meta={}),
            RenameFieldsEvent(rename_map=(("old_name", "new_name"),)),
            "Rename fields in all entries",
        )
    )

    # ReorderKeysEvent
    fixtures.append(
        create_fixture(
            "reorder_keys",
            Store(entries=[{"c": 3, "a": 1, "b": 2}], meta={}),
            ReorderKeysEvent(new_order=("a", "b", "c")),
            "Reorder keys in all entries",
        )
    )

    # TransformFieldEvent
    fixtures.append(
        create_fixture(
            "transform_field",
            Store(entries=[{"x": 1}, {"x": 2}, {"x": 3}], meta={}),
            TransformFieldEvent(field="x", new_field="y", new_values=(10, 20, 30)),
            "Transform field with pre-computed values",
        )
    )

    # UniquifyFieldEvent
    fixtures.append(
        create_fixture(
            "uniquify_field",
            Store(entries=[{"name": "Alice"}, {"name": "Alice"}, {"name": "Bob"}], meta={}),
            UniquifyFieldEvent(field="name", new_values=("Alice_1", "Alice_2", "Bob")),
            "Make field values unique",
        )
    )

    # ==========================================================================
    # Value Events
    # ==========================================================================

    # FillNaEvent
    fixtures.append(
        create_fixture(
            "fill_na",
            Store(entries=[{"a": 1, "b": None}, {"a": None, "b": 2}], meta={}),
            FillNaEvent(fill_value=0),
            "Fill NA/None values",
        )
    )

    # StringCatFieldEvent - prefix
    fixtures.append(
        create_fixture(
            "string_cat_prefix",
            Store(entries=[{"name": "Alice"}, {"name": "Bob"}], meta={}),
            StringCatFieldEvent(field="name", addend="Mr. ", position="prefix"),
            "Concatenate string as prefix",
        )
    )

    # StringCatFieldEvent - suffix
    fixtures.append(
        create_fixture(
            "string_cat_suffix",
            Store(entries=[{"name": "Alice"}, {"name": "Bob"}], meta={}),
            StringCatFieldEvent(field="name", addend=" Jr.", position="suffix"),
            "Concatenate string as suffix",
        )
    )

    # ReplaceValuesEvent
    fixtures.append(
        create_fixture(
            "replace_values",
            Store(entries=[{"status": "yes"}, {"status": "no"}, {"status": "yes"}], meta={}),
            ReplaceValuesEvent(replacements=(("yes", True), ("no", False))),
            "Replace values based on mapping",
        )
    )

    # NumberifyEvent
    fixtures.append(
        create_fixture(
            "numberify",
            Store(entries=[{"val": "10"}, {"val": "20"}, {"val": "30"}], meta={}),
            NumberifyEvent(conversions=((0, "val", 10), (1, "val", 20), (2, "val", 30))),
            "Convert string values to numbers",
        )
    )

    # ==========================================================================
    # Meta Events
    # ==========================================================================

    # SetMetaEvent
    fixtures.append(
        create_fixture(
            "set_meta",
            Store(entries=[], meta={"existing": "value"}),
            SetMetaEvent(key="new_key", value="new_value"),
            "Set a single key-value pair in meta",
        )
    )

    # UpdateMetaEvent
    fixtures.append(
        create_fixture(
            "update_meta",
            Store(entries=[], meta={"a": 1}),
            UpdateMetaEvent(updates={"b": 2, "c": 3}),
            "Merge multiple key-value pairs into meta",
        )
    )

    # RemoveMetaKeyEvent
    fixtures.append(
        create_fixture(
            "remove_meta_key",
            Store(entries=[], meta={"keep": 1, "remove": 2}),
            RemoveMetaKeyEvent(key="remove"),
            "Remove a key from meta",
        )
    )

    # ==========================================================================
    # Composite Events
    # ==========================================================================

    # ReplaceEntriesAndMetaEvent
    fixtures.append(
        create_fixture(
            "replace_entries_and_meta",
            Store(entries=[{"old": 1}], meta={"old_meta": True}),
            ReplaceEntriesAndMetaEvent(
                entries=({"new": 1}, {"new": 2}),
                meta_updates=(("new_meta", True), ("version", 2)),
            ),
            "Replace all entries and update meta",
        )
    )

    # ==========================================================================
    # Nested Field Events
    # ==========================================================================

    # DropNestedFieldsEvent
    fixtures.append(
        create_fixture(
            "drop_nested_fields",
            Store(
                entries=[
                    {"name": "Agent1", "traits": {"a": 1, "b": 2, "c": 3}},
                    {"name": "Agent2", "traits": {"a": 4, "b": 5, "c": 6}},
                ],
                meta={},
            ),
            DropNestedFieldsEvent(parent_field="traits", fields=("b", "c")),
            "Drop fields from a nested dict",
        )
    )

    # KeepNestedFieldsEvent
    fixtures.append(
        create_fixture(
            "keep_nested_fields",
            Store(
                entries=[
                    {"name": "Agent1", "traits": {"a": 1, "b": 2, "c": 3}},
                    {"name": "Agent2", "traits": {"a": 4, "b": 5, "c": 6}},
                ],
                meta={},
            ),
            KeepNestedFieldsEvent(parent_field="traits", fields=("a",)),
            "Keep only specified fields in a nested dict",
        )
    )

    # RenameNestedFieldEvent
    fixtures.append(
        create_fixture(
            "rename_nested_field",
            Store(
                entries=[{"traits": {"old_key": "value"}}],
                meta={},
            ),
            RenameNestedFieldEvent(parent_field="traits", old_name="old_key", new_name="new_key"),
            "Rename a field within a nested dict",
        )
    )

    # AddNestedFieldByIndexEvent
    fixtures.append(
        create_fixture(
            "add_nested_field_by_index",
            Store(
                entries=[{"traits": {"a": 1}}, {"traits": {"a": 2}}],
                meta={},
            ),
            AddNestedFieldByIndexEvent(parent_field="traits", field="b", values=(10, 20)),
            "Add a field to a nested dict with per-entry values",
        )
    )

    # TranslateNestedValuesEvent
    fixtures.append(
        create_fixture(
            "translate_nested_values",
            Store(
                entries=[
                    {"traits": {"color": "red", "size": "small"}},
                    {"traits": {"color": "blue", "size": "large"}},
                ],
                meta={},
            ),
            TranslateNestedValuesEvent(
                parent_field="traits",
                value_map=(("color", (("red", "rouge"), ("blue", "bleu"))),),
            ),
            "Translate values in nested fields",
        )
    )

    # NumberifyNestedFieldsEvent
    fixtures.append(
        create_fixture(
            "numberify_nested_fields",
            Store(
                entries=[{"traits": {"score": "10"}}, {"traits": {"score": "20"}}],
                meta={},
            ),
            NumberifyNestedFieldsEvent(
                parent_field="traits", conversions=((0, "score", 10), (1, "score", 20))
            ),
            "Convert nested field values to numbers",
        )
    )

    # ==========================================================================
    # Agent-Specific Events
    # ==========================================================================

    # SetAgentNamesEvent
    fixtures.append(
        create_fixture(
            "set_agent_names",
            Store(entries=[{"traits": {}}, {"traits": {}}], meta={}),
            SetAgentNamesEvent(names=("Agent1", "Agent2")),
            "Set names for agents",
        )
    )

    # CollapseByFieldEvent
    fixtures.append(
        create_fixture(
            "collapse_by_field",
            Store(
                entries=[
                    {"name": "A", "traits": {"x": 1}},
                    {"name": "A", "traits": {"y": 2}},
                    {"name": "B", "traits": {"z": 3}},
                ],
                meta={},
            ),
            CollapseByFieldEvent(
                group_field="name",
                merge_field="traits",
                result_entries=(
                    {"name": "A", "traits": {"x": 1, "y": 2}},
                    {"name": "B", "traits": {"z": 3}},
                ),
            ),
            "Collapse entries with same field value",
        )
    )

    # ==========================================================================
    # Survey-Specific Events
    # ==========================================================================

    # AddRuleEvent
    fixtures.append(
        create_fixture(
            "add_rule",
            Store(entries=[], meta={}),
            AddRuleEvent(rule_dict={"current_q": 0, "next_q": 1, "expression": "True"}),
            "Add a navigation rule to the survey",
        )
    )

    # RemoveRulesForQuestionEvent
    fixtures.append(
        create_fixture(
            "remove_rules_for_question",
            Store(
                entries=[],
                meta={
                    "rule_collection": {
                        "rules": [
                            {"current_q": 0, "next_q": 1},
                            {"current_q": 1, "next_q": 2},
                            {"current_q": 0, "next_q": 3},
                        ],
                        "num_questions": 4,
                    }
                },
            ),
            RemoveRulesForQuestionEvent(question_index=0),
            "Remove all rules for a question",
        )
    )

    # UpdateRuleIndicesEvent
    fixtures.append(
        create_fixture(
            "update_rule_indices",
            Store(
                entries=[],
                meta={
                    "rule_collection": {
                        "rules": [
                            {"current_q": 0, "next_q": 1},
                            {"current_q": 1, "next_q": 2},
                            {"current_q": 2, "next_q": 3},
                        ],
                        "num_questions": 4,
                    }
                },
            ),
            UpdateRuleIndicesEvent(index_offset=1, from_index=1),
            "Update rule indices after insertion",
        )
    )

    # SetMemoryPlanEvent
    fixtures.append(
        create_fixture(
            "set_memory_plan",
            Store(entries=[], meta={}),
            SetMemoryPlanEvent(memory_plan_dict={"data": {"q1": {"prior_questions": []}}}),
            "Set the memory plan for the survey",
        )
    )

    # AddMemoryForQuestionEvent
    fixtures.append(
        create_fixture(
            "add_memory_for_question",
            Store(entries=[], meta={"memory_plan": {"data": {}}}),
            AddMemoryForQuestionEvent(focal_question="q2", prior_questions=("q0", "q1")),
            "Add memory entries for a question",
        )
    )

    # AddQuestionGroupEvent
    fixtures.append(
        create_fixture(
            "add_question_group",
            Store(entries=[], meta={}),
            AddQuestionGroupEvent(group_name="demographics", start_index=0, end_index=5),
            "Add a question group to the survey",
        )
    )

    # AddPseudoIndexEvent
    fixtures.append(
        create_fixture(
            "add_pseudo_index",
            Store(entries=[], meta={}),
            AddPseudoIndexEvent(entry_name="q1", pseudo_index=0.5),
            "Add a pseudo index for an instruction",
        )
    )

    # RemovePseudoIndexEvent
    fixtures.append(
        create_fixture(
            "remove_pseudo_index",
            Store(entries=[], meta={"pseudo_indices": {"q1": 0.5, "q2": 1.5}}),
            RemovePseudoIndexEvent(entry_name="q1"),
            "Remove a pseudo index",
        )
    )

    # UpdatePseudoIndicesEvent
    fixtures.append(
        create_fixture(
            "update_pseudo_indices",
            Store(entries=[], meta={"pseudo_indices": {"q0": 0, "q1": 1, "q2": 2}}),
            UpdatePseudoIndicesEvent(index_offset=1, from_index=1),
            "Update pseudo indices after insertion",
        )
    )

    # ==========================================================================
    # Survey Composite Events
    # ==========================================================================

    # AddSurveyQuestionEvent
    fixtures.append(
        create_fixture(
            "add_survey_question_append",
            Store(entries=[{"question_name": "q0"}], meta={"pseudo_indices": {"q0": 0}}),
            AddSurveyQuestionEvent(
                question_row={"question_name": "q1"},
                index=-1,
                rule_dict={"current_q": 1, "next_q": 2},
                pseudo_index_name="q1",
                pseudo_index_value=1.0,
                is_interior=False,
            ),
            "Add a question to the end of a survey",
        )
    )

    fixtures.append(
        create_fixture(
            "add_survey_question_insert",
            Store(
                entries=[{"question_name": "q0"}, {"question_name": "q2"}],
                meta={
                    "pseudo_indices": {"q0": 0, "q2": 1},
                    "rule_collection": {
                        "rules": [{"current_q": 0, "next_q": 1}, {"current_q": 1, "next_q": 2}],
                        "num_questions": 2,
                    },
                },
            ),
            AddSurveyQuestionEvent(
                question_row={"question_name": "q1"},
                index=1,
                rule_dict={"current_q": 1, "next_q": 2},
                pseudo_index_name="q1",
                pseudo_index_value=1.0,
                is_interior=True,
            ),
            "Insert a question in the middle of a survey",
        )
    )

    # DeleteSurveyQuestionEvent
    fixtures.append(
        create_fixture(
            "delete_survey_question",
            Store(
                entries=[{"question_name": "q0"}, {"question_name": "q1"}, {"question_name": "q2"}],
                meta={
                    "pseudo_indices": {"q0": 0, "q1": 1, "q2": 2},
                    "rule_collection": {
                        "rules": [
                            {"current_q": 0, "next_q": 1},
                            {"current_q": 1, "next_q": 2},
                            {"current_q": 2, "next_q": 3},
                        ],
                        "num_questions": 3,
                    },
                },
            ),
            DeleteSurveyQuestionEvent(index=1, question_name="q1"),
            "Delete a question from a survey",
        )
    )

    # MoveSurveyQuestionEvent
    fixtures.append(
        create_fixture(
            "move_survey_question",
            Store(
                entries=[{"question_name": "q0"}, {"question_name": "q1"}, {"question_name": "q2"}],
                meta={
                    "pseudo_indices": {"q0": 0, "q1": 1, "q2": 2},
                    "rule_collection": {
                        "rules": [
                            {"current_q": 0, "next_q": 1},
                            {"current_q": 1, "next_q": 2},
                            {"current_q": 2, "next_q": 3},
                        ],
                        "num_questions": 3,
                    },
                },
            ),
            MoveSurveyQuestionEvent(
                from_index=0,
                to_index=2,
                question_name="q0",
                question_row={"question_name": "q0"},
                new_rule_dict={"current_q": 2, "next_q": 3},
            ),
            "Move a question within a survey",
        )
    )

    return fixtures


def main():
    """Generate and save fixtures to JSON file."""
    fixtures = generate_fixtures()

    output_path = Path(__file__).parent / "fixtures.json"
    with open(output_path, "w") as f:
        json.dump(fixtures, f, indent=2)

    print(f"Generated {len(fixtures)} fixtures to {output_path}")

    # Also print summary
    print("\nFixtures generated:")
    for i, fixture in enumerate(fixtures, 1):
        print(f"  {i}. {fixture['name']}: {fixture['description']}")


if __name__ == "__main__":
    main()
