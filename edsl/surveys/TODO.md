# Surveys Refactoring TODO

## 1. ~~Remove all QSF-related methods~~ (DONE)
- Removed `qsf_parser.py`, `qsf_example.py`, `survey_generator.py`, `survey_simulator.py`
- Removed `survey_flow_visualization.py` (compat shim; extras/ version still live)
- Removed `qsf_to_survey` macro and its test
- Removed all commented-out QSF/generator/vibes code from `survey.py`

## 2. Remove TextualInteractiveSurvey
- Delete the textual interactive survey functionality

## 3. Remove InteractiveSurvey
- Delete the interactive survey functionality

## 4. Refactor Survey class with consistent delegation

### Current state (survey.py is ~3,700 lines with 6 different delegation patterns)

**Pattern A — Stored instance delegates (created in `__init__`)**
- `self._exporter = SurveyExport(self)` → `self._exporter.css()`, `.docx()`, `.html()`, etc.
- `self._navigator = SurveyNavigator(self)` → `self._navigator.next_question()`, etc.

**Pattern B — Create-on-use delegates (new instance every call, no stored reference)**
- `EditSurvey(self).add_question(...)`, `.delete_question(...)`, `.move_question(...)`
- `MemoryManagement(self)._set_memory_plan(...)`, `.add_targeted_memory(...)`
- `SurveyFlowVisualization(self).show_flow(...)`

**Pattern C — Static/classmethod delegates**
- `FollowupQuestionAdder.add_followup_questions(self, ...)`
- `QuestionRenamer.with_renamed_question(self, ...)`
- `combine_multiple_choice_to_matrix(survey=self, ...)`

**Pattern D — Standalone function**
- `generate_summary_repr(self, ...)` from survey_repr.py

**Pattern E — Inline (no delegation, everything on Survey class)**
- `to_dict`, `from_dict`, `by`, `run`, `__call__`, all rule methods
- DAG, grouping, question lookup, serialization

### Recommended approach: Stored instance delegates (Pattern A) as the standard

Pick **one** pattern and use it everywhere. Pattern A (stored instance delegates) is best because:
1. **Single allocation** — delegate created once in `__init__`, not on every method call
2. **Discoverable** — `self._editor`, `self._navigator`, etc. are visible in `__init__`
3. **Consistent API** — every delegated method follows `self._delegate.method(...)`
4. **Testable** — delegates can be unit-tested independently with a mock Survey

For class-level factory methods, use **Pattern C** (static/classmethod) since there's no instance yet.

### Proposed delegate classes

| Delegate class          | Stored as           | Responsibility                                              |
|------------------------|---------------------|-------------------------------------------------------------|
| `SurveyExport`         | `self._exporter`    | css, docx, html, latex, code, to_scenario_list, show        |
| `SurveyNavigator`      | `self._navigator`   | next_question, gen_path, question groups                    |
| `EditSurvey`           | `self._editor`      | add/delete/move question, add_instruction                   |
| `MemoryManagement`     | `self._memory`      | set_full_memory, set_lagged_memory, add_targeted_memory     |
| `RuleManager`          | `self._rules`       | add_rule, add_skip_rule, add_stop_rule, show_rules, clear   |
| `SurveyFlowVisualization` | `self._viz`      | show_flow                                                   |

### What stays on Survey directly
- `__init__`, `to_dict`, `from_dict`, `__eq__`, `__hash__`, `__len__`, `__repr__`
- `by`, `run`, `run_async`, `__call__`, `to_jobs` (job creation)
- `example`, `copy`, `duplicate`
- Core data properties: `questions`, `question_names`, `question_name_to_index`, `parameters`
- `dag()` (structural)

### Migration steps
1. ~~Remove QSF code first (item #1 above) — eliminates ~500 lines~~ (DONE)
2. Store `EditSurvey`, `MemoryManagement`, `SurveyFlowVisualization` as instance attrs
3. Convert create-on-use Pattern B calls to use stored delegates
4. Move remaining inline rule methods to a `RuleManager` delegate
5. Move grouping logic to navigator or a new `SurveyGrouping` delegate
6. Verify all tests pass after each step

## 5. Rename `base.py` → `survey_markers.py`
- `base.py` contains `RulePriority`, `EndOfSurveyParent`, and `EndOfSurvey` — the name `base` is vague and collides conceptually with `edsl/base/`
- Rename to `survey_markers.py` for clarity

### Files to update (22 references)

**Relative `.base` imports (8 files in `edsl/surveys/`):**
- `__init__.py`, `descriptors.py`, `textual_interactive_survey.py`, `survey_navigator.py`, `interactive_survey.py`, `survey.py`, `edit_survey.py`, `survey_repr.py`

**Relative `..base` imports (4 files in `edsl/surveys/` subdirs):**
- `rules/rule_manager.py`, `rules/rule.py`, `rules/rule_collection.py`, `dag/construct_dag.py`

**Absolute `edsl.surveys.base` imports (5 files):**
- `followup_questions_demo.py`, `edsl/surveys/followup_questions.py`, `tests/surveys/test_survey_flow.py`, `tests/surveys/test_group_navigation.py`

**Relative `..surveys.base` imports (2 files):**
- `edsl/interviews/answering_function.py`, `edsl/runner/service.py`

**Docstrings/docs (3 references):**
- `edsl/surveys/survey.py:2152`, `edsl/surveys/rules/rule_collection.py:325`, `docs/mintlify-migration/en/latest/surveys.mdx:1001`

