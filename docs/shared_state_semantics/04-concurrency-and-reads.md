# 4. Concurrency and reads

## Per-scope serializability

Committed commands for one scope and machine MUST be equivalent to a total
serial order. A command's input snapshot is the committed snapshot immediately
preceding it in that order.

$$
S_0 \xrightarrow{c_1} S_1
    \xrightarrow{c_2} S_2
    \cdots
    \xrightarrow{c_n} S_n
$$

Different scopes MAY execute concurrently. This specification imposes no global
ordering across scopes.

## Conflicts and retries

An implementation MAY use locks, compare-and-swap, optimistic concurrency, or a
single-writer service. These mechanisms are not observable semantics.

After a conflict, the runtime MAY retry only by reevaluating the entire command
against the new committed snapshot, including its requirement, effect
expressions, and registered algorithms. It MUST NOT reuse a proposed state
computed from a stale snapshot.

If a proposal computed from $S_i$ loses a commit race to $c_j$, retry is a
new evaluation judgment over $S_{i+1}$:

$$
\frac{
  M \vdash \langle S_i,c_j,I_j,X_j \rangle
    \longrightarrow \langle S_{i+1},O_j \rangle
  \qquad
  \operatorname{conflict}(c_i,S_i)
}{
  \operatorname{retry}(c_i)
  = M \vdash \langle S_{i+1},c_i,I_i,X_i \rangle
}
\;\textsc{Retry-New-Snapshot}
$$

Commands SHOULD carry an idempotency key. Repeating one accepted command event
with the same key MUST NOT create a second logical command.

## Read operation

An explicit read is:

$$
\operatorname{read}(q,m,\sigma,v,x)
$$

where $q$ is scope, $m$ machine, $\sigma$ snapshot selector, $v$ view,
and $x$ viewer context.

It returns a rendered view plus a read event containing:

- read ID;
- scope key;
- machine name and version;
- exact snapshot ID;
- view name or version;
- permitted viewer-context identity;
- interview and survey position.

A read does not promise that its snapshot remains current after return.

View rendering is captured by:

$$
M,S_{\sigma},X \vdash V \Downarrow r
$$

and the read result is:

$$
(r,\operatorname{ReadEvent}(id,q,m,\sigma,V,X))
$$

## Just-in-time reads

Survey state reads SHOULD occur as explicit steps immediately before the
questions that need them. Implementations MUST NOT silently move a read earlier
than its declared survey position.

## Example timeline

```text
A reads S0
B reads S0
A proposes vote(Amina, hike)
B proposes vote(Amina, sailing)
A commits: S0 -> S1
B retries against S1: put-once is a no-op
final state: {Amina: hike}
```

Both commands have event IDs. Only the first changes the state.
