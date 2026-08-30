# 7. Remote execution and security

## Observable equivalence

For the same versioned machine, initial state, ordered command events, contexts,
and registered capability versions, local and remote runtimes MUST produce the
same:

- committed states;
- views;
- completion and terminal values;
- close settlement;
- semantic outcome classifications.

Identifiers, timestamps, physical storage layout, and retry counts MAY differ.

## Untrusted recipes

Serialized machines are untrusted data. Parsing MUST NOT execute expressions or
registered algorithms.

Before execution, both submitting client and server MUST perform:

1. envelope and schema validation;
2. DSL and capability version resolution;
3. operator and reducer allowlisting;
4. reference resolution;
5. recursive type checking;
6. context and information-flow checking;
7. static complexity analysis;
8. literal and declared-limit validation.

The authoritative security decision occurs on the execution server.

## Resource limits

A runtime MUST enforce configured maxima for:

- AST nodes and depth;
- literal and string bytes;
- state bytes;
- collection items and nesting;
- generated collection items;
- sort input size;
- evaluation steps;
- command and close wall time;
- event and rendered-view bytes;
- registered algorithm memory and time.

Nested collection operations require conservative cost estimation. A recipe
whose provable upper bound exceeds policy MUST be rejected before execution or
require a separately authorized capability.

## Numeric behavior

NaN and infinity are invalid. Division by zero, overflow beyond the supported
numeric domain, invalid indexing, and invalid empty reductions MUST produce a
deterministic validation or evaluation error and commit no state.

## Registered algorithm isolation

Registered algorithms are trusted implementation code and part of the trusted
computing base. They MUST:

- be allowlisted by exact name and version;
- accept and return plain typed values;
- be deterministic;
- have no ambient filesystem, network, subprocess, environment, or credential
  access;
- run within stricter time and memory limits;
- validate their whole proposed output before commit;
- include conformance, invariant, and adversarial tests.

User-provided Python callbacks MUST NOT execute remotely as algorithms.

## Results provenance

`Results.shared_state` SHOULD contain incoming and outgoing snapshot references,
read events, write events, machine versions, and capability versions. Public
serialization MUST redact private inputs, store credentials, and administrative
context unless explicitly requested by an authorized reader.
