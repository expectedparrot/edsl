/**
 * Event dispatcher for applying events to a Store.
 *
 * This mirrors the Python apply_event function in events.py
 */

import type { Store, Event } from "./types.ts";
import * as ops from "./store.ts";

/**
 * Apply an event to a store, returning the modified store.
 *
 * The store is mutated in-place and also returned for chaining.
 *
 * @param event - The event to apply
 * @param store - The store to modify
 * @returns The modified store (same instance)
 * @throws Error if the event type is unknown
 */
export function applyEvent(event: Event, store: Store): Store {
  switch (event.type) {
    // Row/Entry Events
    case "append_row":
      return ops.append(store, event.row);

    case "update_row":
      return ops.updateRow(store, event.index, event.row);

    case "remove_rows":
      return ops.removeRows(store, event.indices);

    case "insert_row":
      return ops.insertRow(store, event.index, event.row);

    case "update_entry_field":
      return ops.updateEntryField(store, event.index, event.field, event.value);

    case "clear_entries":
      return ops.clearEntries(store);

    case "replace_all_entries":
      return ops.replaceAllEntries(store, event.entries);

    case "reorder_entries":
      return ops.reorderEntries(store, event.new_order);

    case "keep_rows_by_indices":
      return ops.keepRowsByIndices(store, event.indices);

    // Field Events
    case "add_field_to_all_entries":
      return ops.addFieldToAll(store, event.field, event.value);

    case "add_field_by_index":
      return ops.addFieldByIndex(store, event.field, event.values);

    case "drop_fields":
      return ops.dropFields(store, event.fields);

    case "keep_fields":
      return ops.keepFields(store, event.fields);

    case "rename_fields":
      return ops.renameFields(store, event.rename_map);

    case "reorder_keys":
      return ops.reorderKeys(store, event.new_order);

    case "transform_field":
      return ops.transformField(
        store,
        event.field,
        event.new_field,
        event.new_values
      );

    case "uniquify_field":
      return ops.uniquifyField(store, event.field, event.new_values);

    // Value Events
    case "fill_na":
      return ops.fillNa(store, event.fill_value);

    case "string_cat_field":
      return ops.stringCatField(
        store,
        event.field,
        event.addend,
        event.position
      );

    case "replace_values":
      return ops.replaceValues(store, event.replacements);

    case "numberify":
      return ops.numberify(store, event.conversions);

    // Meta Events
    case "set_meta":
      return ops.setMeta(store, event.key, event.value);

    case "update_meta":
      return ops.updateMeta(store, event.updates);

    case "remove_meta_key":
      return ops.removeMetaKey(store, event.key);

    // Composite Events
    case "replace_entries_and_meta":
      return ops.replaceEntriesAndMeta(
        store,
        event.entries,
        event.meta_updates
      );

    // Nested Field Events
    case "drop_nested_fields":
      return ops.dropNestedFields(store, event.parent_field, event.fields);

    case "keep_nested_fields":
      return ops.keepNestedFields(store, event.parent_field, event.fields);

    case "rename_nested_field":
      return ops.renameNestedField(
        store,
        event.parent_field,
        event.old_name,
        event.new_name
      );

    case "add_nested_field_by_index":
      return ops.addNestedFieldByIndex(
        store,
        event.parent_field,
        event.field,
        event.values
      );

    case "translate_nested_values":
      return ops.translateNestedValues(
        store,
        event.parent_field,
        event.value_map
      );

    case "numberify_nested_fields":
      return ops.numberifyNestedFields(
        store,
        event.parent_field,
        event.conversions
      );

    // Agent-Specific Events
    case "set_agent_names":
      return ops.setFieldByIndex(store, "name", event.names);

    case "collapse_by_field":
      return ops.collapseByField(
        store,
        event.group_field,
        event.merge_field,
        event.result_entries
      );

    // Survey-Specific Events
    case "add_rule":
      return ops.addRule(store, event.rule_dict);

    case "remove_rules_for_question":
      return ops.removeRulesForQuestion(store, event.question_index);

    case "update_rule_indices":
      return ops.updateRuleIndices(store, event.index_offset, event.from_index);

    case "set_memory_plan":
      return ops.setMemoryPlan(store, event.memory_plan_dict);

    case "add_memory_for_question":
      return ops.addMemoryForQuestion(
        store,
        event.focal_question,
        event.prior_questions
      );

    case "add_question_group":
      return ops.addQuestionGroup(
        store,
        event.group_name,
        event.start_index,
        event.end_index
      );

    case "add_pseudo_index":
      return ops.addPseudoIndex(store, event.entry_name, event.pseudo_index);

    case "remove_pseudo_index":
      return ops.removePseudoIndex(store, event.entry_name);

    case "update_pseudo_indices":
      return ops.updatePseudoIndices(
        store,
        event.index_offset,
        event.from_index
      );

    // Survey Composite Events
    case "add_survey_question":
      return ops.addSurveyQuestion(
        store,
        event.question_row,
        event.index,
        event.rule_dict,
        event.pseudo_index_name,
        event.pseudo_index_value,
        event.is_interior
      );

    case "delete_survey_question":
      return ops.deleteSurveyQuestion(store, event.index, event.question_name);

    case "move_survey_question":
      return ops.moveSurveyQuestion(
        store,
        event.from_index,
        event.to_index,
        event.question_name,
        event.question_row,
        event.new_rule_dict
      );

    default:
      // TypeScript exhaustiveness check
      const _exhaustiveCheck: never = event;
      throw new Error(`Unknown event type: ${(_exhaustiveCheck as Event).type}`);
  }
}

/**
 * Apply multiple events to a store in sequence.
 *
 * @param events - Array of events to apply
 * @param store - The store to modify
 * @returns The modified store
 */
export function applyEvents(events: Event[], store: Store): Store {
  for (const event of events) {
    applyEvent(event, store);
  }
  return store;
}
