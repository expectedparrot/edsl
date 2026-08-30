# 5. Views and capabilities

## Views

A view is a pure function of a committed state snapshot and a permitted context:

$$
V : \mathit{State} \times \mathit{Context}
    \longrightarrow \mathit{RenderedValue}
$$

Rendering MUST NOT change state. The read event records the exact snapshot and
context identity used.

## Context capabilities

`current` references are capabilities, not unrestricted object traversal. Every
path MUST be declared by the runtime with a type and disclosure class.

Recommended classes:

| Class | Examples | Public view |
|---|---|---:|
| public | group ID, round number | Allowed |
| participant | viewer name, role | Allowed when needed |
| participant-private | private value, signal | Only that participant |
| scope-private | unrevealed ballots | Explicit policy only |
| administrative | interview ID, event IDs | Not participant-visible |
| secret | credentials, store tokens | Never accessible |

The validator MUST compute which capabilities every view expression may read.
A public view MUST be rejected if it can read a capability outside its declared
disclosure policy.

## Stored data labels

Fields MAY declare disclosure labels. Derivations inherit the most restrictive
label of their inputs unless a reviewed declassification rule applies.

Aggregation is not automatically safe declassification. Counts, timing,
completion, errors, and collection sizes can reveal private facts.

## Prompt rendering

Only the rendered view—not raw machine state—MAY be placed into a model prompt.
Internal state, command inputs, event metadata, and store references MUST NOT be
implicitly added to prompts.

## Errors and advisory outcomes

Participant-visible errors and outcomes MUST NOT reveal private state used to
evaluate a requirement. A generic `requirement_not_met` result is safer than
reporting the hidden value that caused it.

## Worked example: two views of one snapshot

Suppose one bargaining snapshot contains both private values:

$$
S = \{\mathit{price}\mapsto 60,
      \mathit{buyerValue}\mapsto 100,
      \mathit{sellerCost}\mapsto 35\}
$$

The buyer and seller read the same $S$ with different contexts:

$$
X_B(\mathit{viewer.role})=\mathit{buyer}
\qquad
X_S(\mathit{viewer.role})=\mathit{seller}
$$

A permitted view can render:

$$
V(S,X_B)=\{\mathit{price}\mapsto60,
            \mathit{yourValue}\mapsto100\}
$$

$$
V(S,X_S)=\{\mathit{price}\mapsto60,
            \mathit{yourCost}\mapsto35\}
$$

The shared snapshot does not change. Only the read-only context and rendered
result differ. This is the practical reason state $S$ and context $X$ are kept
separate.
