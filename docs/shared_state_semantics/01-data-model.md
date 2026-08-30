# 1. Data model

## Machine

A machine is a labeled record:

$$
M =
\left\langle
\begin{array}{rcl}
\mathit{name}         & = & N, \\
\mathit{constants}    & = & C, \\
\mathit{fields}       & = & F, \\
\mathit{commands}     & = & D, \\
\mathit{view}         & = & V, \\
\mathit{complete}     & = & P, \\
\mathit{close}        & = & K, \\
\mathit{capabilities} & = & A
\end{array}
\right\rangle
$$

The symbols name the following components:

- $N$ is the diagnostic machine name and MUST NOT affect behavior.

- $C$ is an immutable finite map of constants. Its values MUST be serializable
  DSL values.

- $F$ is a finite map from field names to `(type, initial-expression)`.

- $D$ is a finite map from command names to command definitions.

- $V$ is a finite map from public result names to expressions.

- $P$ is an optional Boolean completion predicate.

- $K$ is an ordered finite sequence of close effects.

- $A$ is the manifest of exact registered algorithm names and versions.

The labeled form is normative. Implementations MAY use a class, dictionary, or
other representation, but field order MUST NOT affect machine semantics.

## Worked example: the activity-poll machine

For the activity poll, the labeled machine components are approximately:

$$
\begin{array}{rcl}
N &=& \text{ActivityPoll}, \\
C &=& \{\mathit{activities} \mapsto
       [\text{bike ride},\text{sailing},\text{hike},\text{beach day}]\}, \\
F &=& \{\mathit{votes} \mapsto
       (\operatorname{Map}[\operatorname{Text},\operatorname{Activity}],\{\})\}, \\
D &=& \{\mathit{vote} \mapsto \text{the vote command definition}\}, \\
V &=& \{\mathit{votes} \mapsto \operatorname{field}(\mathit{votes}),
       \mathit{voteCount} \mapsto |\operatorname{field}(\mathit{votes})|\}, \\
P &=& \mathrm{null}, \\
K &=& [\,], \\
A &=& \{\}
\end{array}
$$

The poll has no completion predicate, close effects, or registered algorithms.
Those empty components remain part of the machine shape, making serialization
and validation uniform across simple and complex machines.

## Values

DSL values are:

```text
null | boolean | finite number | text | sequence[value] | map[value, value]
```

NaN and positive or negative infinity are not valid numbers. Implementations
MUST enforce configured limits on nesting, string length, collection length, and
serialized size.

## State

A state is a finite map containing exactly the machine's declared fields. A
state is valid when every field value recursively satisfies its declared type.

The initial state is obtained by evaluating field initial expressions in field
declaration order. An initial expression MAY read constants and previously
initialized fields. It MUST NOT read inputs, viewer context, or lexical locals.

For the poll:

$$
S_0 = \{\mathit{votes} \mapsto \{\}\}
$$

After Amina's first accepted vote, a later snapshot may be:

$$
S_1 = \{\mathit{votes} \mapsto
       \{\text{Amina} \mapsto \text{hike}\}\}
$$

## SharedState and scope

A `SharedState` space is a finite map from machine names to machine instances:

$$
\mathit{Space}
  = \operatorname{Map}\!\left[
      \mathit{MachineName},
      (\mathit{MachineDefinition}, \mathit{MachineState})
    \right]
$$

A `SharedStateMap` is a map from scope keys to spaces:

$$
\mathit{SharedStateMap}
  = \operatorname{Map}[\mathit{ScopeKey}, \mathit{Space}]
$$

Selecting an absent scope MAY create a space from the map's declared initial
definition. Scope creation MUST be atomic and deterministic.

Machines in different scopes have no implicit access to each other's state.
Machines in one space also have no cross-machine access unless an explicit,
typed capability is introduced by a future DSL version.

## Snapshot and event identifiers

Every committed state version has an immutable snapshot ID. Every attempted
command and explicit read has a globally unique event ID. Identifiers MUST NOT
be reused, even when a command produces no state change.

The identifier representation is implementation-defined; equality and durable
serialization are required.
