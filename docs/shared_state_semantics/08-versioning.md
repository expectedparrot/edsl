# 8. Versioning and compatibility

## Envelope

Every serialized definition MUST declare:

```json
{
  "dsl_version": "0.1",
  "requires": {
    "operators": {},
    "reducers": {},
    "algorithms": {}
  },
  "limits": {},
  "machine": {}
}
```

The server MUST reject unsupported versions. It MUST NOT silently reinterpret a
recipe under newer semantics.

## Semantic versioning

Changing any of the following requires a new semantic version:

- effect no-op or ordering behavior;
- lazy versus eager evaluation;
- empty-reducer behavior;
- tie-breaking or sort stability;
- numeric coercion or precision;
- retry or close behavior;
- algorithm matching or settlement behavior;
- context disclosure rules.

Adding a backward-compatible optional envelope field does not necessarily
change expression semantics.

## Capability manifest

Every non-core operator, reducer, and algorithm SHOULD be listed with an exact
integer semantic version. A runtime may derive core operator requirements from
the AST, but explicit manifests improve inspection and admission control.

Recipes MUST NOT invoke an algorithm absent from their declared manifest.

The draft prototype's inner `machine.algorithms` list MAY contain legacy
references such as `lmsr_trade@1`. The normative version is the outer manifest.
A validator MUST normalize legacy references and reject any disagreement. A
future schema version SHOULD remove the redundant inner list.

## State migration

Changing field names, field types, initial values for existing scopes, or
meaningful constants may require a state migration. A migration is a separate,
versioned, audited transition; loading old state into a new machine definition
without validation is prohibited.

## Compatibility identity

A machine compatibility identity SHOULD hash the canonicalized DSL version,
machine definition, capability manifest, and relevant limits. Results and state
snapshots SHOULD record this identity.

Two definitions with different diagnostic names but identical canonical
semantics MAY share a compatibility identity. Implementations must not depend on
this optimization.
