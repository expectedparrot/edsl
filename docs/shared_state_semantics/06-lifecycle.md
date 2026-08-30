# 6. Lifecycle

The terms complete, terminal, closed, and settled are distinct.

## Complete

`complete(S)` is a pure predicate indicating that the machine has enough data
for its intended activity. Completion does not itself modify state or prohibit
writes.

$$
\operatorname{complete}_M(S)
  = \operatorname{eval}(P_M,S)
  \in \{\mathrm{true},\mathrm{false}\}
$$

## Terminal

A terminal state prohibits ordinary commands except those explicitly declared
as terminal-safe. Negotiation acceptance and walking away are common terminal
events.

A machine MAY define terminal as identical to complete, but this MUST be
explicit.

## Closed

Close is an explicit, uniquely identified transition. It prevents further
ordinary writes and evaluates close effects against one committed snapshot.

$$
\frac{
  \widehat{K}=\operatorname{evalEffects}(K_M,S,\varnothing,X)
  \qquad
  S'=\operatorname{applyEffects}(S,\widehat{K})
  \qquad
  \operatorname{validState}(M,S')
}{
  M \vdash \langle S,\operatorname{close}(id),X \rangle
  \longrightarrow
  \langle S',\operatorname{closed\_and\_settled}\rangle
}
\;\textsc{Close}
$$

Close MUST be idempotent by event ID. Retrying the same close event cannot apply
settlement twice. A second distinct close request SHOULD return the already
closed snapshot without rerunning effects.

$$
\frac{
  \operatorname{closed}(S,id)
}{
  M \vdash \langle S,\operatorname{close}(id),X \rangle
  \longrightarrow
  \langle S,\operatorname{already\_closed}\rangle
}
\;\textsc{Close-Idempotent}
$$

## Settled

A machine is settled after all close effects and registered settlement
algorithms have committed successfully. Closed but unsettled is a recoverable
operational state only when an implementation cannot make close and settlement
one transaction; it MUST NOT be exposed as successful closure.

## State diagram

```text
open --commands--> open
open --completion predicate true--> complete
open/complete --terminal command--> terminal
open/complete/terminal --close--> closed+settled
```

Schedules MAY use completion or terminal predicates to stop new interview
turns. Only the close transition changes the closed state.

## Views over lifecycle

The context capability `current.closed` is false before close and true only for
the committed closed snapshot. It supports sealed views without giving recipes
write authority over lifecycle metadata.
