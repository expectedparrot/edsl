# Fetchable shared-state examples

These complete source files ship with the matching EDSL version. Fetch a file
through `ep` instead of searching for its installed package location:

```bash
ep skills list --routing
ep skills show edsl-shared-state --example shared_state/machine_primitives/running_ledger.py
```

The `shared_state/machine_primitives/` examples are deterministic Machine
definitions that run with an empty algorithm registry. The `shared_state/dsl/`
collection contains stateful Machine definitions used in study and game
examples. Survey adapters and complete local studies live in the top level of
`shared_state/`.

The Python examples can also be run from an installed EDSL distribution. For
example:

```bash
python -m edsl.examples.shared_state.machine_primitives
python -m edsl.examples.shared_state.dsl.validate
```

Some study examples call model providers. Read the module docstring before
running one; the deterministic primitive corpus makes no model calls.
