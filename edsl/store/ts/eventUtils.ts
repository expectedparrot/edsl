/**
 * Event utilities for creating and serializing events.
 *
 * Mirrors the Python event registry and create_event function.
 */

import type { Event, EventType } from "./types.ts";
import { EVENT_TYPES } from "./types.ts";

/**
 * Convert a Python-style event name to TypeScript event type.
 *
 * Handles both:
 * - Class names: "AppendRowEvent" -> "append_row"
 * - Snake case names: "append_row" -> "append_row"
 */
export function normalizeEventName(name: string): EventType {
  // If it ends with "Event", convert from PascalCase
  if (name.endsWith("Event")) {
    name = name.slice(0, -5); // Remove "Event" suffix
    // Convert PascalCase to snake_case
    name = name
      .replace(/([A-Z])/g, "_$1")
      .toLowerCase()
      .replace(/^_/, "");
  }

  // Validate that it's a known event type
  if (!EVENT_TYPES.includes(name as EventType)) {
    throw new Error(`Unknown event type: ${name}`);
  }

  return name as EventType;
}

/**
 * Create an event from a name and payload.
 *
 * This function handles conversion from Python-serialized events
 * to TypeScript Event objects.
 *
 * @param eventName - Event name (PascalCase class name or snake_case)
 * @param payload - Event payload dictionary
 * @returns An Event object
 */
export function createEvent(
  eventName: string,
  payload: Record<string, unknown>
): Event {
  const type = normalizeEventName(eventName);
  return { type, ...payload } as Event;
}

/**
 * Serialize an event to a format compatible with Python.
 *
 * @param event - The event to serialize
 * @returns Object with 'name' and 'payload' properties
 */
export function serializeEvent(event: Event): {
  name: string;
  payload: Record<string, unknown>;
} {
  const { type, ...payload } = event;
  return { name: type, payload };
}

/**
 * Deserialize an event from Python format.
 *
 * @param data - Object with 'name' and 'payload' properties
 * @returns An Event object
 */
export function deserializeEvent(data: {
  name: string;
  payload: Record<string, unknown>;
}): Event {
  return createEvent(data.name, data.payload);
}

/**
 * List all available event types with their expected fields.
 */
export function listEventTypes(): Record<
  EventType,
  { fields: string[]; description: string }
> {
  return {
    append_row: {
      fields: ["row"],
      description: "Append a row to entries",
    },
    update_row: {
      fields: ["index", "row"],
      description: "Update a row at a specific index",
    },
    remove_rows: {
      fields: ["indices"],
      description: "Remove rows at specified indices",
    },
    insert_row: {
      fields: ["index", "row"],
      description: "Insert a row at a specified index",
    },
    update_entry_field: {
      fields: ["index", "field", "value"],
      description: "Update a specific field in an entry",
    },
    clear_entries: {
      fields: [],
      description: "Remove all entries",
    },
    replace_all_entries: {
      fields: ["entries"],
      description: "Replace all entries with new ones",
    },
    reorder_entries: {
      fields: ["new_order"],
      description: "Reorder entries by new index positions",
    },
    keep_rows_by_indices: {
      fields: ["indices"],
      description: "Keep only rows at specified indices",
    },
    add_field_to_all_entries: {
      fields: ["field", "value"],
      description: "Add a field with the same value to all entries",
    },
    add_field_by_index: {
      fields: ["field", "values"],
      description: "Add a field with per-entry values",
    },
    drop_fields: {
      fields: ["fields"],
      description: "Drop specified fields from all entries",
    },
    keep_fields: {
      fields: ["fields"],
      description: "Keep only specified fields in all entries",
    },
    rename_fields: {
      fields: ["rename_map"],
      description: "Rename fields in all entries",
    },
    reorder_keys: {
      fields: ["new_order"],
      description: "Reorder keys in all entries",
    },
    transform_field: {
      fields: ["field", "new_field", "new_values"],
      description: "Transform field values with pre-computed results",
    },
    uniquify_field: {
      fields: ["field", "new_values"],
      description: "Make field values unique",
    },
    fill_na: {
      fields: ["fill_value"],
      description: "Fill NA/None values with a specified value",
    },
    string_cat_field: {
      fields: ["field", "addend", "position"],
      description: "Concatenate a string to a field",
    },
    replace_values: {
      fields: ["replacements"],
      description: "Replace values based on a mapping",
    },
    numberify: {
      fields: ["conversions"],
      description: "Convert string values to numbers",
    },
    set_meta: {
      fields: ["key", "value"],
      description: "Set a single key-value pair in meta",
    },
    update_meta: {
      fields: ["updates"],
      description: "Merge multiple key-value pairs into meta",
    },
    remove_meta_key: {
      fields: ["key"],
      description: "Remove a key from meta",
    },
    replace_entries_and_meta: {
      fields: ["entries", "meta_updates"],
      description: "Replace all entries and update meta",
    },
    drop_nested_fields: {
      fields: ["parent_field", "fields"],
      description: "Drop fields from a nested dict field",
    },
    keep_nested_fields: {
      fields: ["parent_field", "fields"],
      description: "Keep only specified fields in a nested dict",
    },
    rename_nested_field: {
      fields: ["parent_field", "old_name", "new_name"],
      description: "Rename a field within a nested dict",
    },
    add_nested_field_by_index: {
      fields: ["parent_field", "field", "values"],
      description: "Add a field to a nested dict with per-entry values",
    },
    translate_nested_values: {
      fields: ["parent_field", "value_map"],
      description: "Translate values in nested fields",
    },
    numberify_nested_fields: {
      fields: ["parent_field", "conversions"],
      description: "Convert nested field values to numbers",
    },
    set_agent_names: {
      fields: ["names"],
      description: "Set names for agents",
    },
    collapse_by_field: {
      fields: ["group_field", "merge_field", "result_entries"],
      description: "Collapse entries with same field value",
    },
    add_rule: {
      fields: ["rule_dict"],
      description: "Add a navigation rule to the survey",
    },
    remove_rules_for_question: {
      fields: ["question_index"],
      description: "Remove all rules for a question",
    },
    update_rule_indices: {
      fields: ["index_offset", "from_index"],
      description: "Update rule indices after insertion/deletion",
    },
    set_memory_plan: {
      fields: ["memory_plan_dict"],
      description: "Set the memory plan for the survey",
    },
    add_memory_for_question: {
      fields: ["focal_question", "prior_questions"],
      description: "Add memory entries for a question",
    },
    add_question_group: {
      fields: ["group_name", "start_index", "end_index"],
      description: "Add a question group to the survey",
    },
    add_pseudo_index: {
      fields: ["entry_name", "pseudo_index"],
      description: "Add a pseudo index for an instruction",
    },
    remove_pseudo_index: {
      fields: ["entry_name"],
      description: "Remove a pseudo index",
    },
    update_pseudo_indices: {
      fields: ["index_offset", "from_index"],
      description: "Update pseudo indices after insertion/deletion",
    },
    add_survey_question: {
      fields: [
        "question_row",
        "index",
        "rule_dict",
        "pseudo_index_name",
        "pseudo_index_value",
        "is_interior",
      ],
      description: "Add a question to a survey atomically",
    },
    delete_survey_question: {
      fields: ["index", "question_name"],
      description: "Delete a question from a survey atomically",
    },
    move_survey_question: {
      fields: [
        "from_index",
        "to_index",
        "question_name",
        "question_row",
        "new_rule_dict",
      ],
      description: "Move a question within a survey",
    },
  };
}
