# 3. Command transitions

## Command definition

A command contains:

```text
Command = (inputs, optional requirement, ordered effects, timing)
```

Inputs MUST match the declaration exactly and recursively satisfy their types.

Formally, $c$ is a command identifier and $D(c)$ is its definition in machine
$M$'s command map. $I$ is the map of actual values supplied to this particular
invocation. Command lookup therefore precedes input validation:

$$
d = D(c)
\qquad
\operatorname{dom}(I)=\operatorname{dom}(\operatorname{inputs}(d))
$$

## Normative execution algorithm

```python
def execute(machine, committed_state, command_name, inputs, context):
    command = machine.commands[command_name]
    validate_inputs_exactly(command.inputs, inputs)
    validate_context_capabilities(command, context)

    snapshot = freeze(committed_state)

    if command.require is not None:
        if not evaluate(command.require, snapshot, inputs, context):
            return unchanged(snapshot, reason="requirement_not_met")

    evaluated = [
        evaluate_effect(effect, snapshot, inputs, context)
        for effect in command.effects
    ]

    proposed = copy(snapshot)
    for effect in evaluated:
        proposed = apply_effect(effect, proposed)

    validate_complete_state(machine.fields, proposed)
    enforce_resource_limits(proposed)
    return atomic_commit(proposed)
```

All effect expressions MUST evaluate against `snapshot`. Effects are applied in
declaration order to `proposed`.

## Transition judgments

Let $\operatorname{evalEffects}(E,S,I,X)$ evaluate all expressions in effect
sequence $E$ against immutable snapshot $S$. Let
$\operatorname{applyEffects}(S,\widehat{E})$ apply the resulting concrete
effects in order.

A successful changing command is:

$$
\frac{
  \operatorname{validInputs}(M,c,I)
  \qquad
  M,S,I,X,\varnothing \vdash \operatorname{require}(c) \Downarrow \mathrm{true}
  \qquad
  \widehat{E} = \operatorname{evalEffects}(\operatorname{effects}(c),S,I,X)
  \qquad
  S' = \operatorname{applyEffects}(S,\widehat{E})
  \qquad
  \operatorname{validState}(M,S')
  \qquad
  S' \neq S
}{
  M \vdash \langle S,c,I,X \rangle
  \longrightarrow
  \langle S',\operatorname{changed}\rangle
}
\;\textsc{C-Commit}
$$

An unmet requirement leaves state unchanged:

$$
\frac{
  \operatorname{validInputs}(M,c,I)
  \qquad
  M,S,I,X,\varnothing \vdash \operatorname{require}(c) \Downarrow \mathrm{false}
}{
  M \vdash \langle S,c,I,X \rangle
  \longrightarrow
  \langle S,\operatorname{requirement\_not\_met}\rangle
}
\;\textsc{C-Require-False}
$$

A valid command whose concrete effects make no change commits no new state
contents, though it still receives a command-event ID:

$$
\frac{
  \operatorname{validInputs}(M,c,I)
  \qquad
  \operatorname{require}(c) \Downarrow \mathrm{true}
  \qquad
  \operatorname{applyEffects}(S,\widehat{E}) = S
}{
  M \vdash \langle S,c,I,X \rangle
  \longrightarrow
  \langle S,\operatorname{unchanged}\rangle
}
\;\textsc{C-No-Change}
$$

If the proposed state is invalid, the transition fails and commits nothing:

$$
\frac{
  S' = \operatorname{applyEffects}(S,\widehat{E})
  \qquad
  \neg\operatorname{validState}(M,S')
}{
  M \vdash \langle S,c,I,X \rangle
  \longrightarrow
  \langle S,\operatorname{validation\_error}\rangle
}
\;\textsc{C-Invalid-State}
$$

## Effects

`set(f,v)` replaces field `f` with `v`.

$$
\operatorname{apply}(\operatorname{set}(f,v),P) = P[f \mapsto v]
$$

`set_once(f,v)` sets `f` only when its current proposed value is null; otherwise
it is a no-op.

$$
\operatorname{apply}(\operatorname{setOnce}(f,v),P) =
\begin{cases}
P[f \mapsto v], & P(f)=\mathrm{null} \\
P, & \text{otherwise}
\end{cases}
$$

`put(f,k,v)` assigns `f[k] = v`.

`put(f,k,v,once=true)` assigns only when `k` is absent from the current proposed
map; otherwise it is a no-op.

$$
\operatorname{apply}(\operatorname{putOnce}(f,k,v),P) =
\begin{cases}
P[f \mapsto P(f)[k \mapsto v]], & k \notin \operatorname{dom}(P(f)) \\
P, & \text{otherwise}
\end{cases}
$$

`append(f,v)` appends `v` to sequence field `f`.

$$
\operatorname{apply}(\operatorname{append}(f,v),P)
= P[f \mapsto P(f) \mathbin{+\!+} [v]]
$$

`when(p,e)` applies effect `e` only when predicate `p`, evaluated against the
immutable input snapshot, is true.

$$
\operatorname{apply}(\operatorname{when}(p,e),P) =
\begin{cases}
\operatorname{apply}(e,P), & S,I,X \vdash p \Downarrow \mathrm{true} \\
P, & S,I,X \vdash p \Downarrow \mathrm{false}
\end{cases}
$$

A no-op `set_once` or `put-once` does not cancel sibling effects. If sibling
effects must occur only when insertion is possible, the shared condition MUST be
stated in the command requirement or on every dependent effect.

## Worked example: executing `vote`

Let the current state be empty:

$$
S_0 = \{\mathit{votes}\mapsto\{\}\}
$$

The command identifier and invocation inputs are:

$$
c=\mathit{vote}
\qquad
I_1=\{\mathit{voter}\mapsto\text{Amina},
      \mathit{activity}\mapsto\text{hike}\}
$$

The command definition $D(c)$ says to evaluate the key and value expressions
against $S_0$ and $I_1$, producing the concrete effect:

$$
\operatorname{putOnce}(\mathit{votes},\text{Amina},\text{hike})
$$

Because `Amina` is absent, the transition is:

$$
M \vdash \langle S_0,c,I_1,X\rangle
\longrightarrow
\left\langle
\{\mathit{votes}\mapsto
  \{\text{Amina}\mapsto\text{hike}\}\},
\operatorname{changed}
\right\rangle
$$

Now invoke the same command with different inputs:

$$
I_2=\{\mathit{voter}\mapsto\text{Amina},
      \mathit{activity}\mapsto\text{sailing}\}
$$

The `putOnce` key already exists, so:

$$
M \vdash \langle S_1,c,I_2,X\rangle
\longrightarrow
\langle S_1,\operatorname{unchanged}\rangle
$$

This example also shows why $c$ and $I$ are separate: `vote` selects one command
definition, while each invocation supplies a different input map.

## Outcomes

Outcome data is advisory. It MAY report processed, changed, no-op, validation,
and conflict information. It MUST NOT be represented as proof that the caller
holds the latest state. Durable truth is the committed event and snapshot
history.

## Registered effects

A registered effect invokes an allowlisted algorithm capability. It receives
only evaluated plain data and a copy of proposed state. Its complete output MUST
pass the same type and resource validation before commit. Failure commits
nothing.
