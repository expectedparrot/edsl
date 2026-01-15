/**
 * TypeScript implementation of Store events.
 *
 * This module provides TypeScript equivalents to the Python Store and Event
 * classes, ensuring parity between implementations.
 */

// Types
export type {
  Store,
  Event,
  EventType,
  BaseEvent,
  // Row/Entry Events
  AppendRowEvent,
  UpdateRowEvent,
  RemoveRowsEvent,
  InsertRowEvent,
  UpdateEntryFieldEvent,
  ClearEntriesEvent,
  ReplaceAllEntriesEvent,
  ReorderEntriesEvent,
  KeepRowsByIndicesEvent,
  // Field Events
  AddFieldToAllEntriesEvent,
  AddFieldByIndexEvent,
  DropFieldsEvent,
  KeepFieldsEvent,
  RenameFieldsEvent,
  ReorderKeysEvent,
  TransformFieldEvent,
  UniquifyFieldEvent,
  // Value Events
  FillNaEvent,
  StringCatFieldEvent,
  ReplaceValuesEvent,
  NumberifyEvent,
  // Meta Events
  SetMetaEvent,
  UpdateMetaEvent,
  RemoveMetaKeyEvent,
  // Composite Events
  ReplaceEntriesAndMetaEvent,
  // Nested Field Events
  DropNestedFieldsEvent,
  KeepNestedFieldsEvent,
  RenameNestedFieldEvent,
  AddNestedFieldByIndexEvent,
  TranslateNestedValuesEvent,
  NumberifyNestedFieldsEvent,
  // Agent-Specific Events
  SetAgentNamesEvent,
  CollapseByFieldEvent,
  // Survey-Specific Events
  AddRuleEvent,
  RemoveRulesForQuestionEvent,
  UpdateRuleIndicesEvent,
  SetMemoryPlanEvent,
  AddMemoryForQuestionEvent,
  AddQuestionGroupEvent,
  AddPseudoIndexEvent,
  RemovePseudoIndexEvent,
  UpdatePseudoIndicesEvent,
  // Survey Composite Events
  AddSurveyQuestionEvent,
  DeleteSurveyQuestionEvent,
  MoveSurveyQuestionEvent,
} from "./types.ts";

export { EVENT_TYPES } from "./types.ts";

// Store operations
export {
  createStore,
  copyStore,
  storeToDict,
  storeFromDict,
  // Row/Entry Operations
  append,
  updateRow,
  removeRows,
  insertRow,
  updateEntryField,
  clearEntries,
  replaceAllEntries,
  reorderEntries,
  keepRowsByIndices,
  // Field Operations
  addFieldToAll,
  addFieldByIndex,
  dropFields,
  keepFields,
  renameFields,
  reorderKeys,
  transformField,
  uniquifyField,
  // Nested Field Operations
  dropNestedFields,
  keepNestedFields,
  renameNestedField,
  addNestedFieldByIndex,
  translateNestedValues,
  numberifyNestedFields,
  setFieldByIndex,
  collapseByField,
  // Value Operations
  fillNa,
  stringCatField,
  replaceValues,
  numberify,
  // Meta Operations
  setMeta,
  updateMeta,
  removeMetaKey,
  // Composite Operations
  replaceEntriesAndMeta,
  // Survey-Specific Operations
  addRule,
  removeRulesForQuestion,
  updateRuleIndices,
  setMemoryPlan,
  addMemoryForQuestion,
  addQuestionGroup,
  addPseudoIndex,
  removePseudoIndex,
  updatePseudoIndices,
  // Survey Composite Operations
  addSurveyQuestion,
  deleteSurveyQuestion,
  moveSurveyQuestion,
} from "./store.ts";

// Event dispatcher
export { applyEvent, applyEvents } from "./applyEvent.ts";

// Event utilities
export {
  normalizeEventName,
  createEvent,
  serializeEvent,
  deserializeEvent,
  listEventTypes,
} from "./eventUtils.ts";
