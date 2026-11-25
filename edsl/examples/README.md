# Runnable EDSL examples

This package contains user-facing examples that can be imported or run with an
installed EDSL distribution. The skill bundles provide the supported
agent-facing guidance and worked patterns in their linked Markdown references.

The large shared-state DSL corpus and respondent-workflow simulations are
maintained as test support under `tests/fixtures/`; they are not part of the
installed `edsl.examples` namespace. The test suite exercises those fixtures
alongside the core APIs. Public shared-state examples and the portable Machine
primitive corpus remain under `edsl/examples/shared_state/`.
