# EDSL template rendering audit and patch recommendations

Date: September 7, 2026

Reviewed checkout: `75a8ec03474137d1d426d8e0a281920da4a4a012`

Scope: EDSL template rendering, especially Jinja2 and use on coopr servers

## Local patch status

The patch on `security/sandbox-template-rendering`, proposed in [PR #2647](https://github.com/expectedparrot/edsl/pull/2647), addresses the unrestricted renderers described below. Deployment has not been verified. The findings and source line numbers in this report describe the baseline commit above.

- Added shared sandboxed string/native rendering, including preservation of a caller's custom sandbox policy in native rendering. Ordinary unrestricted environment overrides are rejected.
- Denied arbitrary function and method calls, including on live or nested context objects. A reviewed allowlist retains read-only methods on exact builtin types, Jinja range/dictionary/namespace helpers and macros, and Prompt's variable-capture methods. Custom sandbox overrides retain their stricter policies while also enforcing this callable restriction.
- Switched dynamic attributes, Runner options, question rendering, answer translation, rules, filters, image prompts, reports, and macro arguments to sandboxed rendering. The existing `Prompt` also uses the shared factory.
- Made security failures propagate through the relevant rendering fallbacks, removed generated-HTML recompilation, and replaced both loop-label `eval()` calls with `ast.literal_eval()`.
- Raised the Jinja2 dependency floor to 3.1.6 and refreshed lockfile metadata without changing locked dependency versions.
- The initial regression suite exposed **27 canary-access failures**; its four controls passed. This also confirmed the previously source-reviewed rule, filter, answer-translation, image-prompt, report, and macro sinks locally. After patching and adding compatibility checks, **37 security/compatibility tests pass**, along with **80 existing focused regression tests**.

The focused tests live in [`tests/security/test_template_sandbox.py`](../../tests/security/test_template_sandbox.py). Run them independently of the repository's service/cleanup hooks:

```bash
python -m pytest -q --confcutdir=tests/security tests/security/test_template_sandbox.py
```

Deployment reachability, reducing live-object exposure (including properties and implicit Python operations), resource limits, and the broader recursive-template data policy remain follow-up work. Custom filters, tests, and explicitly allowlisted methods are trusted application code. Passing these checks establishes that the tested access paths are blocked; it does not certify all template execution as safe.

### Callable-policy review fix — September 14, 2026 UTC

Greptile identified that the default Jinja callable policy still allowed
`Interview.include()` to execute `survey.delete_question(0)`. A local reproduction
confirmed the survey changed before this follow-up. The regression now requires
`SecurityError` and verifies the complete serialized survey remains unchanged.

After restricting calls in both shared environments and caller-supplied sandbox
overlays, **54 security/compatibility tests and 94 focused regression tests pass**
with Python 3.11.0 and Jinja2 3.1.6. Run the security command and focused regression
command below to reproduce them. Coverage includes nested public methods,
context-supplied functions, container mutation, native-rendering fallbacks,
custom policies, legitimate read-only lookups, macros, and prompt variable capture.

Compatibility change: templates can no longer invoke arbitrary context functions
or methods, even with an ordinary `SandboxedEnvironment` override. Use data lookup
and Jinja filters for computations. Explicit application-level allowlists must
only contain reviewed methods; they are not configuration for untrusted authors.

### Branch validation — September 13, 2026

Rebased the working patch onto upstream `main` at
`9d186ffaddb3d567e005c4de6ce16d172a7ea703` when creating the security branch.
Using Python 3.11.0 and Jinja2 3.1.6:

- The security suite above passed: **37 tests**.
- The focused regression command below passed: **94 tests**. Its initial sandboxed run had 17 filesystem-permission failures writing the local EDSL object store; the same command passed with that access allowed.
- `git diff --check` passed. Black accepted 19 of the 21 changed/new Python files; its two findings are existing formatting in `question_check_box.py` and `question_multiple_choice.py`, outside the patch hunks.
- These runs exclude repository-wide service and cleanup hooks via `--confcutdir`. They do not constitute a full test-suite or deployment check.

```bash
python -m pytest -q --confcutdir=tests/security \
  tests/invigilators/test_question_option_processor.py \
  tests/runner/test_dynamic_option_resolution.py \
  tests/runner/test_compute_piping_direct_answer.py \
  tests/runner/test_loop_merge_dynamic.py \
  tests/prompts/test_Prompts.py \
  tests/questions/test_QuestionMultipleChoice.py \
  tests/questions/test_QuestionCheckbox.py \
  tests/questions/test_QuestionRank.py \
  tests/questions/test_QuestionMatrix.py \
  tests/questions/test_QuestionLinearScale.py \
  tests/questions/test_QuestionImageGeneration.py \
  tests/questions/test_failing_loop.py \
  tests/questions/test_attribute_expand.py \
  tests/surveys/test_Rule.py \
  tests/surveys/test_RuleCollection.py
```

## Summary

The existing `Prompt` sandbox does not protect every EDSL rendering path. Local probes confirmed that dynamic question options, Runner option resolution, general question rendering, and HTML rendering can access a synthetic environment variable through unrestricted Jinja templates.

Passing a `SandboxedEnvironment` explicitly to `question.render()` also leaves an unrestricted native rendering fallback. This means securing only the main string renderer is insufficient.

Treat these as critical patch priorities wherever a server processes templates supplied by another user. Unrestricted Jinja permits access to Python internals and can enable arbitrary code execution with the rendering process's permissions. The local checks demonstrated environment access, not command execution.

## Evidence and limitations

- Source review covered Jinja imports, environment construction, template compilation, rendering calls, and related callers across `edsl`.
- Local probes created and read only a synthetic environment variable. They did not read real credentials, execute shell commands, or submit surveys to a remote service.
- The same probe was blocked with `SecurityError` by the patched `Prompt` path when rendering was forced with a nonempty context.
- Installed Jinja2 and the Poetry lockfile both reported version **3.1.6**. The package dependency still permits versions starting at **3.1.2**.
- This review did not establish which paths are exposed by the deployed coopr application or verify its deployed patch. Server endpoint reachability remains to be checked.
- The original audit was read-only. See **Local patch status** above for subsequent implementation and validation.

Line numbers below refer to the reviewed commit. Links use repository-relative paths for sharing with the team.

## Confirmed vulnerable rendering paths

### 1. Dynamic question attributes

Location: [`edsl/invigilators/question_attribute_processor.py`](../../edsl/invigilators/question_attribute_processor.py), line 130.

`_render_template_to_native_value()` compiles and renders incoming templates using unrestricted `NativeEnvironment`.

**Confirmed:** the options processor returned the synthetic environment marker from a dynamic `question_options` template.

The same helper is called by:

- `question_option_processor.py:180,202` for option lists and dynamic option sources, including the dictionary `from`/`add` format.
- `question_item_processor.py:227` for dynamic matrix items.
- `question_numerical_processor.py:141` for numerical bounds.

Matrix items and numerical bounds share the vulnerable sink but were not individually exercised by the local probes. Checking the rendered result's type does not prevent execution that already occurred during rendering.

**Patch:** use a sandboxed native environment for all attribute processing and propagate security failures. Do not turn a `SecurityError` into a permissive fallback.

### 2. Runner option resolution

Location: [`edsl/runner/service.py`](../../edsl/runner/service.py), lines 2547–2609.

`JobService._resolve_template_string()` independently constructs an unrestricted `NativeEnvironment`. `_resolve_question_options()` invokes it for string templates, templated list entries, and dictionary `from` values.

**Confirmed:** the Runner options helper returned the synthetic marker. Fixing the invigilator attribute processor alone will leave this separate path exposed.

**Patch:** use the same sandboxed native renderer here and review callers in `runner/executor.py`, `runner/direct_answer.py`, and the service itself.

### 3. General question rendering and sandbox fallback bypass

Location: [`edsl/questions/question_base_gen_mixin.py`](../../edsl/questions/question_base_gen_mixin.py), lines 29, 95–96, and 449–451.

`TemplateRenderer` defaults to unrestricted `Environment`. `QuestionBaseGenMixin.render()` additionally creates a fresh unrestricted `NativeEnvironment` to preserve native option and item values.

**Confirmed:** a free-text question's `render()` returned the synthetic marker. A dynamic multiple-choice question also returned it when the caller explicitly supplied `jinja_env=SandboxedEnvironment()`.

The latter works because the string-rendering failure can be caught and the original template is subsequently passed to the unrestricted native renderer.

**Patch:** secure both renderers, preserve the security policy through all passes, and fail closed on security errors. Audit indirect users such as compute questions and invigilator validation.

### 4. HTML question rendering and option-string injection

Location: [`edsl/questions/HTMLQuestion.py`](../../edsl/questions/HTMLQuestion.py), lines 59 and 67.

Two separate operations compile dynamic strings with unrestricted `Template`:

- Rendering `question_text`.
- Recompiling `question_html_content` after a question-specific HTML template has already interpolated user data into it.

**Confirmed:** both malicious question text and an ordinary string entry in a multiple-choice options list produced the synthetic marker in the resulting HTML.

The second case is significant: an initially fixed HTML template can insert an option as data, after which the outer renderer treats the resulting HTML as executable template source.

**Patch:** sandbox intentional question-text templates. Render dynamic fields before inserting them into the HTML shell, and stop recompiling completed HTML. Review HTML escaping separately; autoescaping prevents some HTML injection but does not sandbox Python access.

## Additional unrestricted sinks identified by source review

These locations should be included in the patch. Unlike the four groups above, they were not individually validated with execution probes. Impact on coopr depends on whether untrusted inputs reach them.

| Surface | Source location | Recommended change |
| --- | --- | --- |
| Survey skip/stop rule expressions | [`surveys/rules/rule.py`](../../edsl/surveys/rules/rule.py):374–376 | Sandbox the Jinja rendering that precedes `EvalWithCompoundTypes`. A restricted evaluator cannot protect an earlier unrestricted render. |
| Multiple-choice answer translation | [`questions/question_multiple_choice.py`](../../edsl/questions/question_multiple_choice.py):741,753 | Replace unrestricted option rendering, including the exception fallback. |
| Checkbox answer translation | [`questions/question_check_box.py`](../../edsl/questions/question_check_box.py):849 | Sandbox option-string rendering. |
| Rank answer translation | [`questions/question_rank.py`](../../edsl/questions/question_rank.py):513 | Sandbox option-string rendering. |
| Job inclusion filters | [`jobs/interview_tuple_filter.py`](../../edsl/jobs/interview_tuple_filter.py):45–55 | Sandbox expressions and provide restricted data representations of agent, scenario, and model. |
| Interview inclusion filters | [`interviews/interview.py`](../../edsl/interviews/interview.py):754–756 | Sandbox expressions and restrict the context, including the survey object. |
| Image-generation question text | [`questions/question_image_generation.py`](../../edsl/questions/question_image_generation.py):87 | Sandbox question-text rendering before the provider call. |
| Custom report templates | [`results/report.py`](../../edsl/results/report.py):168–172 | Sandbox user-authored templates. Ordinary row values are data unless subsequently recompiled. |
| Macro formatter arguments | [`macros/output_formatter.py`](../../edsl/macros/output_formatter.py):324 | Sandbox argument rendering. Checking for a context-key substring and using `StrictUndefined` are not security boundaries. |

### Adjacent Python injection: looped option labels

Location: [`edsl/questions/loop_processor.py`](../../edsl/questions/loop_processor.py), lines 74 and 316.

Both loop processors call Python `eval()` on substituted **`option_labels`** strings. This is a separate unsafe evaluation sink; changing Jinja environments will not fix it. The earlier conversational description called these option strings; the precise field is `option_labels`.

**Patch:** preserve structured dictionaries through substitution where possible. If parsing serialized labels is necessary, use JSON or `ast.literal_eval` with size limits and explicit validation of the expected mapping shape. Verify whether supported constructors or serialized inputs permit untrusted values to reach these branches; that reachability has not yet been demonstrated.

## Cross-cutting remediation

1. **Centralize template environments.** Supply shared factories for sandboxed string and native rendering. A native sandbox can combine Jinja's `SandboxedEnvironment` and `NativeEnvironment`; native type preservation alone provides no sandbox. Prevent security-sensitive callers from supplying an unrestricted override.
2. **Preserve security across fallbacks.** Catch `SecurityError` separately and propagate a controlled failure. Review broad `except Exception` handlers that preserve malicious text or send it into another renderer.
3. **Keep data from becoming template source.** Remove HTML recompilation and review recursive rendering of scenario values, prior answers, option text, and other substituted data. Define explicitly which fields may contain templates.
4. **Restrict render contexts.** Prefer primitive values and narrowly scoped data views over live EDSL objects. Jinja's sandbox normally allows public callable methods; merely blocking double-underscore attributes is insufficient when exposed methods can read files, make requests, or mutate state. Allow only methods needed for supported template features.
5. **Raise the dependency floor.** Require at least Jinja2 3.1.6, such as `jinja2 = "^3.1.6"` in the current Poetry configuration. Verify the resolved version in every server and worker image. The existing lockfile does not impose that floor on downstream installations.
6. **Bound resource use.** Apply template/input/output size limits and worker CPU, memory, and execution-time limits. Sandboxing does not prevent all expensive loops or output expansion. Review large template caches as part of memory budgeting.
7. **Map deployment entry points.** Trace human-survey creation, previews, respondent navigation, remote inference, result/report rendering, and macro execution to these sinks. Verify the deployed EDSL revision in each process; a fix in only one service or rendering path is incomplete.

The upstream [Jinja sandbox documentation](https://jinja.palletsprojects.com/en/stable/sandbox/) describes callable access, context restrictions, and resource limits. Its [release notes](https://jinja.palletsprojects.com/en/stable/changes/) document additional sandbox fixes in 3.1.5 and 3.1.6. These recommendations are not a claim that 3.1.6 alone makes EDSL rendering safe.

## Suggested regression coverage

Use synthetic markers and temporary fixtures; tests should not access real credentials or depend on production services.

- Re-run environment-access canaries through every confirmed path and assert that access is blocked before any fallback or downstream call.
- Test dynamic options as strings, list entries, and dictionary `from`/`add` values; include matrix items and numerical bounds.
- Test `question.render()` with its default environment and with an explicitly supplied sandbox. Include native lists/tuples and both string and native passes.
- Test question text and option labels through the complete HTML renderer, including data inserted by a fixed inner template.
- Exercise rules, filters, answer translation, image prompt generation with a mocked provider, reports, and macro arguments.
- Test template syntax carried in scenario data and prior answers to detect unexpected recursive evaluation.
- Use a harmless object with a side-effect counter to verify that unapproved public methods are not callable from templates.
- Test invalid and malicious looped `option_labels` inputs without executing arbitrary Python.
- Preserve legitimate scenario substitution, prior-answer piping, numerical bounds, matrix rendering, and supported template-variable capture.
- Add a source-level guard against new unrestricted Jinja rendering of user-controlled strings. Parsing-only uses and fixed repository templates need explicit review rather than being automatically counted as vulnerabilities.

## Avoiding false positives

An ordinary Jinja environment used only to parse syntax is not, by itself, a demonstrated execution sink. Likewise, rendering a fixed repository template with untrusted values does not normally execute those values as Jinja. The HTML finding above arises because the generated output is compiled again.

The existing sandboxed `Prompt` blocked the tested Python-internals traversal. That observation validates this specific control, not every callable exposed in its context or every resource-consumption pattern. This review should guide the patch and deployment verification; it is not a certification that all template-related vulnerabilities have been eliminated.
