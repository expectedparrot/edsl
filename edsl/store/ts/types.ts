/**
 * TypeScript type definitions for Store and Events.
 *
 * These types mirror the Python dataclasses in store.py and events.py
 * to ensure parity between Python and TypeScript implementations.
 */

// =============================================================================
// Store Types
// =============================================================================

export interface Store {
  entries: Record<string, unknown>[];
  meta: Record<string, unknown>;
}

// =============================================================================
// Event Base Type
// =============================================================================

export interface BaseEvent {
  type: string;
}

// =============================================================================
// Row/Entry Events
// =============================================================================

export interface AppendRowEvent extends BaseEvent {
  type: "append_row";
  row: Record<string, unknown>;
}

export interface UpdateRowEvent extends BaseEvent {
  type: "update_row";
  index: number;
  row: Record<string, unknown>;
}

export interface RemoveRowsEvent extends BaseEvent {
  type: "remove_rows";
  indices: number[];
}

export interface InsertRowEvent extends BaseEvent {
  type: "insert_row";
  index: number;
  row: Record<string, unknown>;
}

export interface UpdateEntryFieldEvent extends BaseEvent {
  type: "update_entry_field";
  index: number;
  field: string;
  value: unknown;
}

export interface ClearEntriesEvent extends BaseEvent {
  type: "clear_entries";
}

export interface ReplaceAllEntriesEvent extends BaseEvent {
  type: "replace_all_entries";
  entries: Record<string, unknown>[];
}

export interface ReorderEntriesEvent extends BaseEvent {
  type: "reorder_entries";
  new_order: number[];
}

export interface KeepRowsByIndicesEvent extends BaseEvent {
  type: "keep_rows_by_indices";
  indices: number[];
}

// =============================================================================
// Field Events
// =============================================================================

export interface AddFieldToAllEntriesEvent extends BaseEvent {
  type: "add_field_to_all_entries";
  field: string;
  value: unknown;
}

export interface AddFieldByIndexEvent extends BaseEvent {
  type: "add_field_by_index";
  field: string;
  values: unknown[];
}

export interface DropFieldsEvent extends BaseEvent {
  type: "drop_fields";
  fields: string[];
}

export interface KeepFieldsEvent extends BaseEvent {
  type: "keep_fields";
  fields: string[];
}

export interface RenameFieldsEvent extends BaseEvent {
  type: "rename_fields";
  rename_map: [string, string][];
}

export interface ReorderKeysEvent extends BaseEvent {
  type: "reorder_keys";
  new_order: string[];
}

export interface TransformFieldEvent extends BaseEvent {
  type: "transform_field";
  field: string;
  new_field: string;
  new_values: unknown[];
}

export interface UniquifyFieldEvent extends BaseEvent {
  type: "uniquify_field";
  field: string;
  new_values: unknown[];
}

// =============================================================================
// Value Events
// =============================================================================

export interface FillNaEvent extends BaseEvent {
  type: "fill_na";
  fill_value: unknown;
}

export interface StringCatFieldEvent extends BaseEvent {
  type: "string_cat_field";
  field: string;
  addend: string;
  position: "prefix" | "suffix";
}

export interface ReplaceValuesEvent extends BaseEvent {
  type: "replace_values";
  replacements: [string, unknown][];
}

export interface NumberifyEvent extends BaseEvent {
  type: "numberify";
  conversions: [number, string, unknown][];
}

// =============================================================================
// Meta Events
// =============================================================================

export interface SetMetaEvent extends BaseEvent {
  type: "set_meta";
  key: string;
  value: unknown;
}

export interface UpdateMetaEvent extends BaseEvent {
  type: "update_meta";
  updates: Record<string, unknown>;
}

export interface RemoveMetaKeyEvent extends BaseEvent {
  type: "remove_meta_key";
  key: string;
}

// =============================================================================
// Composite Events
// =============================================================================

export interface ReplaceEntriesAndMetaEvent extends BaseEvent {
  type: "replace_entries_and_meta";
  entries: Record<string, unknown>[];
  meta_updates: [string, unknown][];
}

// =============================================================================
// Nested Field Events
// =============================================================================

export interface DropNestedFieldsEvent extends BaseEvent {
  type: "drop_nested_fields";
  parent_field: string;
  fields: string[];
}

export interface KeepNestedFieldsEvent extends BaseEvent {
  type: "keep_nested_fields";
  parent_field: string;
  fields: string[];
}

export interface RenameNestedFieldEvent extends BaseEvent {
  type: "rename_nested_field";
  parent_field: string;
  old_name: string;
  new_name: string;
}

export interface AddNestedFieldByIndexEvent extends BaseEvent {
  type: "add_nested_field_by_index";
  parent_field: string;
  field: string;
  values: unknown[];
}

export interface TranslateNestedValuesEvent extends BaseEvent {
  type: "translate_nested_values";
  parent_field: string;
  value_map: [string, [unknown, unknown][]][];
}

export interface NumberifyNestedFieldsEvent extends BaseEvent {
  type: "numberify_nested_fields";
  parent_field: string;
  conversions: [number, string, unknown][];
}

// =============================================================================
// Agent-Specific Events
// =============================================================================

export interface SetAgentNamesEvent extends BaseEvent {
  type: "set_agent_names";
  names: string[];
}

export interface CollapseByFieldEvent extends BaseEvent {
  type: "collapse_by_field";
  group_field: string;
  merge_field: string;
  result_entries: Record<string, unknown>[];
}

// =============================================================================
// Survey-Specific Events
// =============================================================================

export interface AddRuleEvent extends BaseEvent {
  type: "add_rule";
  rule_dict: Record<string, unknown>;
}

export interface RemoveRulesForQuestionEvent extends BaseEvent {
  type: "remove_rules_for_question";
  question_index: number;
}

export interface UpdateRuleIndicesEvent extends BaseEvent {
  type: "update_rule_indices";
  index_offset: number;
  from_index: number;
}

export interface SetMemoryPlanEvent extends BaseEvent {
  type: "set_memory_plan";
  memory_plan_dict: Record<string, unknown>;
}

export interface AddMemoryForQuestionEvent extends BaseEvent {
  type: "add_memory_for_question";
  focal_question: string;
  prior_questions: string[];
}

export interface AddQuestionGroupEvent extends BaseEvent {
  type: "add_question_group";
  group_name: string;
  start_index: number;
  end_index: number;
}

export interface AddPseudoIndexEvent extends BaseEvent {
  type: "add_pseudo_index";
  entry_name: string;
  pseudo_index: number;
}

export interface RemovePseudoIndexEvent extends BaseEvent {
  type: "remove_pseudo_index";
  entry_name: string;
}

export interface UpdatePseudoIndicesEvent extends BaseEvent {
  type: "update_pseudo_indices";
  index_offset: number;
  from_index: number;
}

// =============================================================================
// Survey Composite Events
// =============================================================================

export interface AddSurveyQuestionEvent extends BaseEvent {
  type: "add_survey_question";
  question_row: Record<string, unknown>;
  index: number;
  rule_dict: Record<string, unknown>;
  pseudo_index_name: string;
  pseudo_index_value: number;
  is_interior: boolean;
}

export interface DeleteSurveyQuestionEvent extends BaseEvent {
  type: "delete_survey_question";
  index: number;
  question_name: string;
}

export interface MoveSurveyQuestionEvent extends BaseEvent {
  type: "move_survey_question";
  from_index: number;
  to_index: number;
  question_name: string;
  question_row: Record<string, unknown>;
  new_rule_dict: Record<string, unknown>;
}

// =============================================================================
// Union Type of All Events
// =============================================================================

export type Event =
  // Row/Entry Events
  | AppendRowEvent
  | UpdateRowEvent
  | RemoveRowsEvent
  | InsertRowEvent
  | UpdateEntryFieldEvent
  | ClearEntriesEvent
  | ReplaceAllEntriesEvent
  | ReorderEntriesEvent
  | KeepRowsByIndicesEvent
  // Field Events
  | AddFieldToAllEntriesEvent
  | AddFieldByIndexEvent
  | DropFieldsEvent
  | KeepFieldsEvent
  | RenameFieldsEvent
  | ReorderKeysEvent
  | TransformFieldEvent
  | UniquifyFieldEvent
  // Value Events
  | FillNaEvent
  | StringCatFieldEvent
  | ReplaceValuesEvent
  | NumberifyEvent
  // Meta Events
  | SetMetaEvent
  | UpdateMetaEvent
  | RemoveMetaKeyEvent
  // Composite Events
  | ReplaceEntriesAndMetaEvent
  // Nested Field Events
  | DropNestedFieldsEvent
  | KeepNestedFieldsEvent
  | RenameNestedFieldEvent
  | AddNestedFieldByIndexEvent
  | TranslateNestedValuesEvent
  | NumberifyNestedFieldsEvent
  // Agent-Specific Events
  | SetAgentNamesEvent
  | CollapseByFieldEvent
  // Survey-Specific Events
  | AddRuleEvent
  | RemoveRulesForQuestionEvent
  | UpdateRuleIndicesEvent
  | SetMemoryPlanEvent
  | AddMemoryForQuestionEvent
  | AddQuestionGroupEvent
  | AddPseudoIndexEvent
  | RemovePseudoIndexEvent
  | UpdatePseudoIndicesEvent
  // Survey Composite Events
  | AddSurveyQuestionEvent
  | DeleteSurveyQuestionEvent
  | MoveSurveyQuestionEvent;

// =============================================================================
// Event Type Names (for runtime type checking)
// =============================================================================

export const EVENT_TYPES = [
  "append_row",
  "update_row",
  "remove_rows",
  "insert_row",
  "update_entry_field",
  "clear_entries",
  "replace_all_entries",
  "reorder_entries",
  "keep_rows_by_indices",
  "add_field_to_all_entries",
  "add_field_by_index",
  "drop_fields",
  "keep_fields",
  "rename_fields",
  "reorder_keys",
  "transform_field",
  "uniquify_field",
  "fill_na",
  "string_cat_field",
  "replace_values",
  "numberify",
  "set_meta",
  "update_meta",
  "remove_meta_key",
  "replace_entries_and_meta",
  "drop_nested_fields",
  "keep_nested_fields",
  "rename_nested_field",
  "add_nested_field_by_index",
  "translate_nested_values",
  "numberify_nested_fields",
  "set_agent_names",
  "collapse_by_field",
  "add_rule",
  "remove_rules_for_question",
  "update_rule_indices",
  "set_memory_plan",
  "add_memory_for_question",
  "add_question_group",
  "add_pseudo_index",
  "remove_pseudo_index",
  "update_pseudo_indices",
  "add_survey_question",
  "delete_survey_question",
  "move_survey_question",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];
