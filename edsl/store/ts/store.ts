/**
 * Store class for event-sourced data storage.
 *
 * This TypeScript implementation mirrors the Python Store class in store.py
 * to ensure parity between implementations.
 */

import type { Store } from "./types.ts";

// =============================================================================
// Store Factory and Utilities
// =============================================================================

export function createStore(
  entries: Record<string, unknown>[] = [],
  meta: Record<string, unknown> = {}
): Store {
  return { entries, meta };
}

export function copyStore(store: Store): Store {
  // Deep copy entries (each entry is a new object)
  const newEntries = store.entries.map((entry) => ({ ...entry }));

  // Shallow copy meta, deep copy mutable nested structures
  const newMeta = { ...store.meta };
  const mutableKeys = [
    "rule_collection",
    "pseudo_indices",
    "question_groups",
    "memory_plan",
    "instruction_names_to_instructions",
  ];

  for (const key of mutableKeys) {
    if (key in newMeta) {
      newMeta[key] = JSON.parse(JSON.stringify(newMeta[key]));
    }
  }

  return { entries: newEntries, meta: newMeta };
}

export function storeToDict(store: Store): Record<string, unknown> {
  return { entries: store.entries, meta: store.meta };
}

export function storeFromDict(data: Record<string, unknown>): Store {
  // Deep clone to avoid mutating the source data
  return JSON.parse(JSON.stringify({
    entries: data.entries,
    meta: data.meta,
  })) as Store;
}

// =============================================================================
// Row/Entry Operations
// =============================================================================

export function append(store: Store, row: Record<string, unknown>): Store {
  store.entries.push(row);
  return store;
}

export function updateRow(
  store: Store,
  index: number,
  row: Record<string, unknown>
): Store {
  store.entries[index] = row;
  return store;
}

export function removeRows(store: Store, indices: number[]): Store {
  const indicesToRemove = new Set(indices);
  store.entries = store.entries.filter((_, i) => !indicesToRemove.has(i));
  return store;
}

export function insertRow(
  store: Store,
  index: number,
  row: Record<string, unknown>
): Store {
  store.entries.splice(index, 0, row);
  return store;
}

export function updateEntryField(
  store: Store,
  index: number,
  field: string,
  value: unknown
): Store {
  store.entries[index][field] = value;
  return store;
}

export function clearEntries(store: Store): Store {
  store.entries = [];
  return store;
}

export function replaceAllEntries(
  store: Store,
  entries: Record<string, unknown>[]
): Store {
  store.entries = [...entries];
  return store;
}

export function reorderEntries(store: Store, newOrder: number[]): Store {
  store.entries = newOrder.map((i) => store.entries[i]);
  return store;
}

export function keepRowsByIndices(store: Store, indices: number[]): Store {
  const indicesToKeep = new Set(indices);
  store.entries = store.entries.filter((_, i) => indicesToKeep.has(i));
  return store;
}

// =============================================================================
// Field Operations
// =============================================================================

export function addFieldToAll(
  store: Store,
  field: string,
  value: unknown
): Store {
  for (const entry of store.entries) {
    entry[field] = value;
  }
  return store;
}

export function addFieldByIndex(
  store: Store,
  field: string,
  values: unknown[]
): Store {
  for (let i = 0; i < store.entries.length; i++) {
    store.entries[i][field] = values[i];
  }
  return store;
}

export function dropFields(store: Store, fields: string[]): Store {
  const fieldsSet = new Set(fields);
  for (const entry of store.entries) {
    for (const field of fieldsSet) {
      delete entry[field];
    }
  }
  return store;
}

export function keepFields(store: Store, fields: string[]): Store {
  const fieldsSet = new Set(fields);
  for (let i = 0; i < store.entries.length; i++) {
    const entry = store.entries[i];
    const newEntry: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(entry)) {
      if (fieldsSet.has(k)) {
        newEntry[k] = v;
      }
    }
    store.entries[i] = newEntry;
  }
  return store;
}

export function renameFields(
  store: Store,
  renameMap: [string, string][]
): Store {
  for (const entry of store.entries) {
    for (const [oldName, newName] of renameMap) {
      if (oldName in entry) {
        entry[newName] = entry[oldName];
        delete entry[oldName];
      }
    }
  }
  return store;
}

export function reorderKeys(store: Store, newOrder: string[]): Store {
  store.entries = store.entries.map((entry) => {
    const newEntry: Record<string, unknown> = {};
    for (const key of newOrder) {
      if (key in entry) {
        newEntry[key] = entry[key];
      }
    }
    return newEntry;
  });
  return store;
}

export function transformField(
  store: Store,
  field: string,
  newField: string,
  newValues: unknown[]
): Store {
  for (let i = 0; i < store.entries.length; i++) {
    store.entries[i][newField] = newValues[i];
  }
  return store;
}

export function uniquifyField(
  store: Store,
  field: string,
  newValues: unknown[]
): Store {
  for (let i = 0; i < store.entries.length; i++) {
    if (field in store.entries[i]) {
      store.entries[i][field] = newValues[i];
    }
  }
  return store;
}

// =============================================================================
// Nested Field Operations
// =============================================================================

export function dropNestedFields(
  store: Store,
  parentField: string,
  fields: string[]
): Store {
  const fieldsSet = new Set(fields);
  for (const entry of store.entries) {
    if (
      parentField in entry &&
      typeof entry[parentField] === "object" &&
      entry[parentField] !== null
    ) {
      const nested = entry[parentField] as Record<string, unknown>;
      for (const field of fieldsSet) {
        delete nested[field];
      }
    }
  }
  return store;
}

export function keepNestedFields(
  store: Store,
  parentField: string,
  fields: string[]
): Store {
  const fieldsSet = new Set(fields);
  for (const entry of store.entries) {
    if (
      parentField in entry &&
      typeof entry[parentField] === "object" &&
      entry[parentField] !== null
    ) {
      const nested = entry[parentField] as Record<string, unknown>;
      const newNested: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(nested)) {
        if (fieldsSet.has(k)) {
          newNested[k] = v;
        }
      }
      entry[parentField] = newNested;
    }
  }
  return store;
}

export function renameNestedField(
  store: Store,
  parentField: string,
  oldName: string,
  newName: string
): Store {
  for (const entry of store.entries) {
    if (
      parentField in entry &&
      typeof entry[parentField] === "object" &&
      entry[parentField] !== null
    ) {
      const nested = entry[parentField] as Record<string, unknown>;
      if (oldName in nested) {
        nested[newName] = nested[oldName];
        delete nested[oldName];
      }
    }
  }
  return store;
}

export function addNestedFieldByIndex(
  store: Store,
  parentField: string,
  field: string,
  values: unknown[]
): Store {
  for (let i = 0; i < store.entries.length; i++) {
    if (!(parentField in store.entries[i])) {
      store.entries[i][parentField] = {};
    }
    (store.entries[i][parentField] as Record<string, unknown>)[field] =
      values[i];
  }
  return store;
}

export function translateNestedValues(
  store: Store,
  parentField: string,
  valueMap: [string, [unknown, unknown][]][]
): Store {
  // Convert to more usable format: {field: Map(old -> new)}
  const translations = new Map<string, Map<unknown, unknown>>();
  for (const [field, mappings] of valueMap) {
    translations.set(field, new Map(mappings));
  }

  for (const entry of store.entries) {
    if (
      parentField in entry &&
      typeof entry[parentField] === "object" &&
      entry[parentField] !== null
    ) {
      const nested = entry[parentField] as Record<string, unknown>;
      for (const [field, mapping] of translations) {
        if (field in nested && mapping.has(nested[field])) {
          nested[field] = mapping.get(nested[field]);
        }
      }
    }
  }
  return store;
}

export function numberifyNestedFields(
  store: Store,
  parentField: string,
  conversions: [number, string, unknown][]
): Store {
  for (const [entryIdx, field, newValue] of conversions) {
    if (parentField in store.entries[entryIdx]) {
      (store.entries[entryIdx][parentField] as Record<string, unknown>)[field] =
        newValue;
    }
  }
  return store;
}

export function setFieldByIndex(
  store: Store,
  field: string,
  values: unknown[]
): Store {
  for (let i = 0; i < store.entries.length; i++) {
    store.entries[i][field] = values[i];
  }
  return store;
}

export function collapseByField(
  store: Store,
  _groupField: string,
  _mergeField: string,
  resultEntries: Record<string, unknown>[]
): Store {
  store.entries = [...resultEntries];
  return store;
}

// =============================================================================
// Value Operations
// =============================================================================

function isNull(val: unknown): boolean {
  if (val === null || val === undefined) {
    return true;
  }
  if (typeof val === "number" && isNaN(val)) {
    return true;
  }
  if (typeof val === "string") {
    const strVal = val.toLowerCase();
    if (["nan", "none", "null", ""].includes(strVal)) {
      return true;
    }
  }
  return false;
}

export function fillNa(store: Store, fillValue: unknown): Store {
  for (const entry of store.entries) {
    for (const key of Object.keys(entry)) {
      if (isNull(entry[key])) {
        entry[key] = fillValue;
      }
    }
  }
  return store;
}

export function stringCatField(
  store: Store,
  field: string,
  addend: string,
  position: "prefix" | "suffix"
): Store {
  for (const entry of store.entries) {
    if (field in entry) {
      const current = entry[field];
      if (typeof current === "string") {
        if (position === "prefix") {
          entry[field] = addend + current;
        } else {
          entry[field] = current + addend;
        }
      }
    }
  }
  return store;
}

export function replaceValues(
  store: Store,
  replacements: [string, unknown][]
): Store {
  const replacementsMap = new Map(replacements);
  for (const entry of store.entries) {
    for (const key of Object.keys(entry)) {
      const strVal = String(entry[key]);
      if (replacementsMap.has(strVal)) {
        entry[key] = replacementsMap.get(strVal);
      }
    }
  }
  return store;
}

export function numberify(
  store: Store,
  conversions: [number, string, unknown][]
): Store {
  for (const [entryIdx, field, newValue] of conversions) {
    store.entries[entryIdx][field] = newValue;
  }
  return store;
}

// =============================================================================
// Meta Operations
// =============================================================================

export function setMeta(store: Store, key: string, value: unknown): Store {
  store.meta[key] = value;
  return store;
}

export function updateMeta(
  store: Store,
  updates: Record<string, unknown>
): Store {
  Object.assign(store.meta, updates);
  return store;
}

export function removeMetaKey(store: Store, key: string): Store {
  delete store.meta[key];
  return store;
}

// =============================================================================
// Composite Operations
// =============================================================================

export function replaceEntriesAndMeta(
  store: Store,
  entries: Record<string, unknown>[],
  metaUpdates: [string, unknown][]
): Store {
  store.entries = [...entries];
  for (const [key, value] of metaUpdates) {
    store.meta[key] = value;
  }
  return store;
}

// =============================================================================
// Survey-Specific Operations
// =============================================================================

interface RuleCollection {
  rules: Record<string, unknown>[];
  num_questions: number | null;
}

function ensureRuleCollection(store: Store): RuleCollection {
  if (!("rule_collection" in store.meta)) {
    store.meta["rule_collection"] = { rules: [], num_questions: null };
  } else if (
    !(store.meta["rule_collection"] as Record<string, unknown>)["rules"]
  ) {
    (store.meta["rule_collection"] as Record<string, unknown>)["rules"] = [];
  }
  return store.meta["rule_collection"] as RuleCollection;
}

export function addRule(
  store: Store,
  ruleDict: Record<string, unknown>
): Store {
  const ruleCollection = ensureRuleCollection(store);
  ruleCollection.rules.push(ruleDict);
  const currentQ = (ruleDict["current_q"] as number) ?? 0;
  if (ruleCollection.num_questions === null) {
    ruleCollection.num_questions = currentQ + 1;
  } else {
    ruleCollection.num_questions = Math.max(
      ruleCollection.num_questions,
      currentQ + 1
    );
  }
  return store;
}

export function removeRulesForQuestion(
  store: Store,
  questionIndex: number
): Store {
  const ruleCollection = ensureRuleCollection(store);
  ruleCollection.rules = ruleCollection.rules.filter(
    (rule) => rule["current_q"] !== questionIndex
  );
  return store;
}

export function updateRuleIndices(
  store: Store,
  indexOffset: number,
  fromIndex: number
): Store {
  const ruleCollection = ensureRuleCollection(store);
  for (const rule of ruleCollection.rules) {
    const currentQ = (rule["current_q"] as number) ?? 0;
    if (currentQ >= fromIndex) {
      rule["current_q"] = currentQ + indexOffset;
    }
    const nextQ = rule["next_q"];
    if (typeof nextQ === "number" && nextQ >= fromIndex) {
      rule["next_q"] = nextQ + indexOffset;
    }
  }
  if (ruleCollection.num_questions !== null) {
    ruleCollection.num_questions += indexOffset;
  }
  return store;
}

export function setMemoryPlan(
  store: Store,
  memoryPlanDict: Record<string, unknown>
): Store {
  store.meta["memory_plan"] = memoryPlanDict;
  return store;
}

export function addMemoryForQuestion(
  store: Store,
  focalQuestion: string,
  priorQuestions: string[]
): Store {
  if (!("memory_plan" in store.meta)) {
    store.meta["memory_plan"] = { data: {} };
  }
  const memoryPlan = store.meta["memory_plan"] as Record<string, unknown>;
  if (!("data" in memoryPlan)) {
    memoryPlan["data"] = {};
  }
  (memoryPlan["data"] as Record<string, unknown>)[focalQuestion] = {
    prior_questions: [...priorQuestions],
  };
  return store;
}

export function addQuestionGroup(
  store: Store,
  groupName: string,
  startIndex: number,
  endIndex: number
): Store {
  if (!("question_groups" in store.meta)) {
    store.meta["question_groups"] = {};
  }
  (store.meta["question_groups"] as Record<string, unknown>)[groupName] = [
    startIndex,
    endIndex,
  ];
  return store;
}

export function addPseudoIndex(
  store: Store,
  name: string,
  pseudoIndex: number
): Store {
  if (!("pseudo_indices" in store.meta)) {
    store.meta["pseudo_indices"] = {};
  }
  (store.meta["pseudo_indices"] as Record<string, unknown>)[name] = pseudoIndex;
  return store;
}

export function removePseudoIndex(store: Store, name: string): Store {
  if ("pseudo_indices" in store.meta) {
    delete (store.meta["pseudo_indices"] as Record<string, unknown>)[name];
  }
  return store;
}

export function updatePseudoIndices(
  store: Store,
  indexOffset: number,
  fromIndex: number
): Store {
  if ("pseudo_indices" in store.meta) {
    const pseudoIndices = store.meta["pseudo_indices"] as Record<
      string,
      number
    >;
    for (const name of Object.keys(pseudoIndices)) {
      if (pseudoIndices[name] >= fromIndex) {
        pseudoIndices[name] += indexOffset;
      }
    }
  }
  return store;
}

// =============================================================================
// Survey Composite Operations
// =============================================================================

export function addSurveyQuestion(
  store: Store,
  questionRow: Record<string, unknown>,
  index: number,
  ruleDict: Record<string, unknown>,
  pseudoIndexName: string,
  pseudoIndexValue: number,
  isInterior: boolean
): Store {
  // 1. Insert the question entry
  if (index === -1 || index >= store.entries.length) {
    store.entries.push(questionRow);
  } else {
    store.entries.splice(index, 0, questionRow);
  }

  // 2. Update existing rule indices if interior insertion
  if (isInterior) {
    updateRuleIndices(store, 1, index);
    updatePseudoIndices(store, 1, index);
  }

  // 3. Add the default rule
  addRule(store, ruleDict);

  // 4. Add the pseudo index
  addPseudoIndex(store, pseudoIndexName, pseudoIndexValue);

  return store;
}

export function deleteSurveyQuestion(
  store: Store,
  index: number,
  questionName: string
): Store {
  // 1. Remove rules for this question
  removeRulesForQuestion(store, index);

  // 2. Update remaining rule indices
  updateRuleIndices(store, -1, index + 1);

  // 3. Remove the question entry
  if (index >= 0 && index < store.entries.length) {
    store.entries.splice(index, 1);
  }

  // 4. Remove the pseudo index
  removePseudoIndex(store, questionName);

  // 5. Update remaining pseudo indices
  updatePseudoIndices(store, -1, index + 1);

  // 6. Update memory_plan to remove the deleted question
  const memoryPlan = store.meta["memory_plan"] as Record<string, unknown>;
  if (memoryPlan) {
    // Remove from survey_question_names
    const surveyNames = memoryPlan["survey_question_names"] as string[];
    if (surveyNames && surveyNames.includes(questionName)) {
      const nameIdx = surveyNames.indexOf(questionName);
      const newSurveyNames = [...surveyNames];
      newSurveyNames.splice(nameIdx, 1);
      memoryPlan["survey_question_names"] = newSurveyNames;

      // Remove corresponding survey_question_text
      const surveyTexts = memoryPlan["survey_question_texts"] as unknown[];
      if (surveyTexts && nameIdx < surveyTexts.length) {
        const newSurveyTexts = [...surveyTexts];
        newSurveyTexts.splice(nameIdx, 1);
        memoryPlan["survey_question_texts"] = newSurveyTexts;
      }
    }

    // Remove from memory_plan data
    const data = memoryPlan["data"] as Record<string, unknown>;
    if (data) {
      // Remove as focal question
      if (questionName in data) {
        delete data[questionName];
      }
      // Remove as prior question in other focal questions
      for (const focalQ of Object.keys(data)) {
        const memoryEntry = data[focalQ] as Record<string, unknown>;
        if (
          memoryEntry &&
          typeof memoryEntry === "object" &&
          "prior_questions" in memoryEntry
        ) {
          const priorQs = memoryEntry["prior_questions"] as string[];
          if (priorQs && priorQs.includes(questionName)) {
            memoryEntry["prior_questions"] = priorQs.filter(
              (q) => q !== questionName
            );
          }
        }
      }
    }
  }

  return store;
}

export function moveSurveyQuestion(
  store: Store,
  fromIndex: number,
  toIndex: number,
  questionName: string,
  questionRow: Record<string, unknown>,
  newRuleDict: Record<string, unknown>
): Store {
  // Delete from old position
  deleteSurveyQuestion(store, fromIndex, questionName);

  // Add at new position
  const isInterior = toIndex < store.entries.length;
  addSurveyQuestion(
    store,
    questionRow,
    toIndex,
    newRuleDict,
    questionName,
    toIndex,
    isInterior
  );

  return store;
}
