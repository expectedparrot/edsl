# EDSL examples

These examples are version-matched to the installed EDSL package. The examples
here are executable source and are also used by the local test suite.

## Shared state

- `shared_state/machine_primitives/` contains portable Machine definitions
  that run with the general interpreter and an empty algorithm registry.
- `shared_state/dsl/` contains stateful study and game definitions used to
  exercise the shared-state language across multiple patterns.
- `shared_state/*.py` contains complete Survey integrations, local acceptance
  exercises, and analysis adapters built on those definitions.

Run the deterministic primitive corpus without model calls:

```bash
python -m edsl.examples.shared_state.machine_primitives
python -m edsl.examples.shared_state.dsl.validate
```

Examples that call a model provider or send Humanize deliveries say so in their
module docstring. Run only the deterministic commands when validating a local
checkout without remote credentials.

## Respondent workflows

`workflows/` contains authoring and execution examples for durable respondent
workflows. The stress gallery and Humanize examples can create local run state;
their generated outputs belong under the ignored `artifacts/` directory.

The detailed shared-state and orchestration instructions, including individual
examples fetchable through `ep skills show`, live in the matching skill bundles.
