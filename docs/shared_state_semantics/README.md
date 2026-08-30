# EDSL Shared-State Semantics

Status: **Draft 0.1**

This directory specifies the meaning of the EDSL shared-state DSL independently
of any particular local or remote implementation.

The normative words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
have their usual RFC 2119 meanings. Code examples are informative unless a
section labels them normative.

## How to read this specification

Each formal section is followed where useful by an informative worked example.
The examples use one activity poll throughout:

```python
activities = ["bike ride", "sailing", "hike", "beach day"]

fields = {
    "votes": state_field(
        T.map(T.text(), T.choice(activities)),
        initial={},
    ),
}

vote = Command(
    inputs={
        "voter": T.text(),
        "activity": T.choice(activities),
    },
    effects=(
        put("votes", input_("voter"), input_("activity"), once=True),
    ),
)
```

The poll is intentionally simple. It lets the reader connect the same concrete
field, command, input, state, and view to the notation in later sections.

## Artifacts

- `01-data-model.md` defines machines, states, scopes, and identifiers.
- `02-expressions-and-types.md` defines expression evaluation and static typing.
- `03-command-transitions.md` defines requirements, effects, and atomic commit.
- `04-concurrency-and-reads.md` defines per-scope ordering, retries, and reads.
- `05-views-and-capabilities.md` defines views and information access.
- `06-lifecycle.md` distinguishes complete, terminal, closed, and settled.
- `07-remote-and-security.md` defines local/remote equivalence and resource limits.
- `08-versioning.md` defines compatibility and registered capabilities.
- `machine.schema.json` defines the serialized envelope and structural grammar.
- `test-vectors/` contains implementation-independent examples.
- `run_vectors.py` executes the vectors against the reference interpreter.

## Central semantic promise

For one scope, committed commands form a serial history:

```text
S0 --c1--> S1 --c2--> S2 ... --cn--> Sn
```

Each command evaluates its requirement and every effect expression against one
immutable committed input snapshot. It proposes one complete replacement state.
The runtime validates and commits all of that state or none of it.

Reads name the exact snapshot and viewer context used to render a view. Local
and remote implementations MUST produce the same observable result for the
same versioned machine, history, context, and registered capabilities.

## Notation

Expression evaluation is written:

$$
M, S, I, X, L \vdash e \Downarrow v
$$

where `M` is the machine, `S` state, `I` command inputs, `X` execution context,
`L` lexical collection locals, `e` an expression, and `v` its value.

The environments have different ownership and lifetimes:

- $S$ is the persistent, versioned machine-state snapshot. Commands may propose
  changes to its declared fields.
- $I$ is the finite map of actual arguments supplied to this command invocation.
- $X$ is read-only execution context supplied by EDSL, such as authenticated
  participant identity, group, interview ID, viewer role, run round, and
  lifecycle status. A machine cannot modify $X$.
- $L$ contains temporary bindings introduced while evaluating collection
  expressions and disappears after evaluation.

A command transition is written:

$$
M \vdash
\langle S, c, I, X \rangle
\longrightarrow
\langle S', O \rangle
$$

where `S'` is the committed or unchanged state and `O` is advisory outcome data.

Here $c$ and $I$ are intentionally separate. The command identifier $c$ selects
one definition from the machine's command map $D$; $I$ supplies the actual input
values for this invocation. For example:

$$
c = \mathit{vote}
\qquad
I = \{\mathit{voter}\mapsto\text{Amina},
      \mathit{activity}\mapsto\text{hike}\}
$$

The same command $c=\mathit{vote}$ can be invoked many times with different
input maps $I$.

$S$ is not part of $X$ because it has different semantics. $S$ is durable shared
data, has a snapshot ID, participates in concurrency control, and is the target
of atomic transitions. $X$ is immutable authority and execution metadata that
may differ for two readers of the same $S$. Keeping them separate prevents a
machine from modifying identity or authorization data and permits
viewer-specific views over one shared snapshot.

## Conformance

An implementation conforms to a DSL version only if it:

1. accepts every valid test vector for that version;
2. rejects every invalid vector with the specified error class;
3. produces the specified state, view, completion, and outcome values;
4. implements the security and resource requirements in this specification.

Passing the included reference vectors is necessary but not sufficient for
production conformance.
