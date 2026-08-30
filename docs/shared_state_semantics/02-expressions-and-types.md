# 2. Expressions and types

## Environments

Expression evaluation receives five environments:

- constants `C`;
- immutable state snapshot `S`;
- validated command input `I`;
- capability-checked execution context `X`;
- lexical collection locals `L`.

A reference MUST resolve within its declared namespace. Missing references are
validation errors, except for context references declaring an explicit default.

## Type judgment

Static typing is written:

$$
\Gamma \vdash e : \tau
$$

The type environment is the disjoint union:

$$
\Gamma
  = \Gamma_C \uplus \Gamma_F \uplus \Gamma_I
    \uplus \Gamma_X \uplus \Gamma_L
$$

where the components contain types for constants, fields, command inputs,
context capabilities, and lexical locals. Context entries additionally carry a
disclosure label:

$$
\Gamma_X(x) = (\tau,\ell)
$$

The label $\ell$ is checked by the information-flow rules in Section 5 and does
not change the ordinary value type $\tau$.

Representative rules:

$$
\frac{
  \Gamma_F(f) = \tau
}{
  \Gamma \vdash \operatorname{field}(f) : \tau
}
\;\textsc{T-Field}
$$

Map lookup without a default returns an optional value:

$$
\frac{
  \Gamma \vdash m : \operatorname{Map}[K,V]
  \qquad
  \Gamma \vdash k : K
}{
  \Gamma \vdash \operatorname{get}(m,k) : \operatorname{Optional}[V]
}
\;\textsc{T-Get-Optional}
$$

Map lookup with a default of the map's value type returns a non-optional value:

$$
\frac{
  \Gamma \vdash m : \operatorname{Map}[K,V]
  \qquad
  \Gamma \vdash k : K
  \qquad
  \Gamma \vdash d : V
}{
  \Gamma \vdash \operatorname{get}(m,k,d) : V
}
\;\textsc{T-Get-Default}
$$

Conditional branches are combined with the least defined type join:

$$
\frac{
  \Gamma \vdash p : \operatorname{Boolean}
  \qquad
  \Gamma \vdash e_1 : \tau_1
  \qquad
  \Gamma \vdash e_2 : \tau_2
  \qquad
  \tau_1 \sqcup \tau_2 = \tau
}{
  \Gamma \vdash \operatorname{choose}(p,e_1,e_2) : \tau
}
\;\textsc{T-Choose}
$$

The required joins are:

$$
\tau \sqcup \tau = \tau
$$

$$
\tau \sqcup \operatorname{Null}
  = \operatorname{Null} \sqcup \tau
  = \operatorname{Optional}[\tau]
$$

$$
\operatorname{Optional}[\tau] \sqcup \tau
  = \tau \sqcup \operatorname{Optional}[\tau]
  = \operatorname{Optional}[\tau]
$$

No implicit join exists for unrelated types. For example,
$\operatorname{Number} \sqcup \operatorname{Text}$ is undefined unless a future
DSL version introduces an explicitly declared union type. An undefined join is
a creation-time type error; it does not silently widen to `Any`.

## Worked example: constructing the poll's type environment

While checking the `vote` command, the relevant environments include:

$$
\begin{aligned}
\Gamma_C(\mathit{activities})
  &= \operatorname{Sequence}[\operatorname{Activity}], \\
\Gamma_F(\mathit{votes})
  &= \operatorname{Map}[\operatorname{Text},\operatorname{Activity}], \\
\Gamma_I(\mathit{voter})
  &= \operatorname{Text}, \\
\Gamma_I(\mathit{activity})
  &= \operatorname{Activity}, \\
\Gamma_X(\mathit{current.agent.name})
  &= (\operatorname{Text},\operatorname{Participant}), \\
\Gamma_L &= \varnothing.
\end{aligned}
$$

Here `Activity` is the finite choice type containing the four configured
activities. There are no lexical locals because the command does not contain a
map, filter, or similar binding expression.

The expression:

```python
field("votes").get(input_("voter"))
```

is typed in three steps:

$$
\Gamma \vdash \operatorname{field}(\mathit{votes})
  : \operatorname{Map}[\operatorname{Text},\operatorname{Activity}]
$$

$$
\Gamma \vdash \operatorname{input}(\mathit{voter})
  : \operatorname{Text}
$$

and therefore:

$$
\Gamma \vdash
  \operatorname{get}(
    \operatorname{field}(\mathit{votes}),
    \operatorname{input}(\mathit{voter})
  )
  : \operatorname{Optional}[\operatorname{Activity}]
$$

The optional result reflects that this voter may not have voted yet.

By contrast:

```python
field("votes").get(input_("voter"), "hike")
```

has type `Activity`, because its default is also an `Activity`.

A context-dependent expression illustrates the disclosure component:

```python
current.agent.name
```

has ordinary value type `Text`, while its label records that it identifies the
current participant. Type checking answers “is this text?”; information-flow
checking separately answers “may this view disclose it?”

An implementation MUST recursively validate sequence element types, map key and
value types, and record fields. Top-level container checking is insufficient.

## Evaluation

Pure expressions MUST NOT modify state or perform I/O. Evaluation is
deterministic for identical environments and semantic versions.

Arithmetic MUST reject division by zero and non-finite results. Positional
access MUST reject an invalid index unless guarded by a lazy expression.

## Laziness

`choose`, Boolean `and`, and Boolean `or` are short-circuiting:

$$
\frac{
  M,S,I,X,L \vdash p \Downarrow \mathrm{true}
  \qquad
  M,S,I,X,L \vdash e_1 \Downarrow v
}{
  M,S,I,X,L \vdash
  \operatorname{choose}(p,e_1,e_2)
  \Downarrow v
}
\;\textsc{E-Choose-True}
$$

$$
\frac{
  M,S,I,X,L \vdash p \Downarrow \mathrm{false}
  \qquad
  M,S,I,X,L \vdash e_2 \Downarrow v
}{
  M,S,I,X,L \vdash
  \operatorname{choose}(p,e_1,e_2)
  \Downarrow v
}
\;\textsc{E-Choose-False}
$$

The absent branch premise is intentional: the unselected expression is not
evaluated.

Short-circuit conjunction and disjunction are:

$$
\frac{M,S,I,X,L \vdash p \Downarrow \mathrm{false}}
{M,S,I,X,L \vdash p \land q \Downarrow \mathrm{false}}
\;\textsc{E-And-False}
$$

$$
\frac{M,S,I,X,L \vdash p \Downarrow \mathrm{true}
\qquad M,S,I,X,L \vdash q \Downarrow v}
{M,S,I,X,L \vdash p \land q \Downarrow v}
\;\textsc{E-And-True}
$$

The rules for $\lor$ are dual.

The unselected branch MUST NOT be evaluated. Similarly, the right operand of
`and` is skipped after false and the right operand of `or` is skipped after true.

## Collection operations

Map, filter, reduction, and sorting operate only on finite collections. Their
lexical locals are visible only inside their own expression body.

Stable sorting MUST preserve input order among records equal under all declared
sort keys. Reducers MUST define empty-collection behavior explicitly. It is an
error to invoke a reducer for which the runtime lacks the exact semantic
version.

## Expression safety

The language MUST NOT provide arbitrary callbacks, imports, evaluation of code,
reflection, unrestricted object attributes, filesystem or network access,
general recursion, or user-defined unbounded loops.
