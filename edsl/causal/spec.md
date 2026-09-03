# Causal Study Blueprint Specification

Status: initial executable specification
Format version: `1`

## 1. Purpose

A causal study blueprint is the durable, reviewable description of a social
science simulation or human study. It connects a research question to an SCM,
an experimental design, participant roles, information boundaries, an
interaction protocol, measurements, and a prespecified analysis.

The blueprint is declarative. Every object required to reproduce a study MUST
be serializable as JSON. A blueprint MUST NOT contain Python callbacks or rely
on unrecorded prompt construction. Model-assisted authoring is an optional
adapter that produces a draft blueprint; it is not part of blueprint semantics
and MUST NOT execute the draft automatically.

## 2. Goals and non-goals

The format is intended to:

- make the inferential target and execution procedure inspectable together;
- separate causal scope from information access;
- support LLM, human, and service-mediated roles in one study;
- detect under-specified or infeasible studies before model calls or delivery;
- compile deterministically into existing EDSL causal and conversation
  primitives; and
- retain hashes and authored inputs sufficient for provenance.

Version 1 does not discover a defensible SCM, prove identification, implement
power analysis, or guarantee that an LLM follows private instructions. Those
are review, validation, and future adapter concerns.

## 3. Lifecycle

The normative lifecycle is:

1. **Draft**: a person or authoring model proposes a blueprint.
2. **Validate**: structural and cross-object findings are produced without
   making model calls.
3. **Review and freeze**: the research question, SCM, design, information
   boundaries, procedure, and analysis are approved.
4. **Compile**: the frozen blueprint is deterministically materialized into
   assignments and a conversation definition.
5. **Preflight**: costs, cell counts, execution channels, and credentials are
   checked by the execution layer.
6. **Execute, measure, fit, and report**: outputs retain the blueprint hash.

Compilation MUST fail when validation contains an `error`. Warnings do not
prevent compilation. Execution is an explicit operation after compilation.

## 4. Top-level object

```json
{
  "type": "causal_study_blueprint",
  "schema_version": 1,
  "name": "mug-negotiation",
  "research_question": {
    "question": "How do private values affect bargaining success?",
    "population": "Simulated buyer-seller dyads",
    "setting": "Bilateral negotiation",
    "hypotheses": ["Higher buyer budgets increase agreement"]
  },
  "analysis_plan": {"type": "causal_analysis_plan", "...": "..."},
  "roles": [
    {
      "role": "buyer",
      "goal": "Buy at the lowest acceptable price",
      "constraints": ["Never pay above the private budget"],
      "execution": {"kind": "llm", "options": {"model_policy": "default"}}
    }
  ],
  "information": [
    {"variable": "buyer_budget", "visibility": "private", "audience": ["buyer"]}
  ],
  "design": {
    "method": "factorial",
    "replications": 20,
    "seed": "mug-v1",
    "max_cells": null
  },
  "interaction": {"type": "conversation", "...": "..."},
  "procedure_requirements": [],
  "metadata": {}
}
```

Unknown top-level fields are not part of version 1 semantics. Readers SHOULD
reject unsupported `schema_version` values instead of guessing.

## 5. Components

### 5.1 Research question

`question`, `population`, and `setting` are non-empty strings. `hypotheses` is
an ordered list of testable prose claims. These fields provide scientific
context; the SCM and estimands remain the machine-checkable claims.

### 5.2 Analysis plan and SCM

`analysis_plan` is a serialized `CausalAnalysisPlan`. Its SCM defines causal
variables and equations. Exogenous variables define treatment values and a
renderable `proxy_attribute`. Endogenous variables define their measurement
survey and respondent role. Estimands and estimator settings are frozen with
the study.

No arithmetic may be supplied as raw Python. Calculations belong in a
versioned expression or estimator DSL. Version 1 supports the existing SCM
equation families and estimator specification.

### 5.3 Roles and execution channels

A role has a unique `role`, a `goal`, one or more prose `constraints`, and an
execution channel:

- `llm`: answered by an EDSL model selected by `options`;
- `human`: delivered through a human-work adapter such as Humanize; or
- `service`: performed by deterministic or externally managed infrastructure.

Execution options are durable configuration, not credentials. Secrets MUST
NOT be serialized into a blueprint. A role is a function in the study; runtime
participant instances are generated separately for every design cell.

### 5.4 Information policy

Every exogenous variable has exactly one information policy. Causal `scope`
answers *whose attribute or scenario the variable describes*. Information
policy answers *which roles observe its realized value*.

- `private`: exactly one audience role receives the rendered instruction;
- `shared`: two or more named audience roles receive it;
- `public`: every interaction role receives it through public context; and
- `system`: no participant receives it; orchestration and measurement may use
  the raw value.

The compiler always retains raw treatment assignments in system context for
provenance. Participant contexts contain rendered instructions rather than raw
cross-role data. Measurements do not implicitly grant the respondent access
to a treatment; access must be declared.

### 5.5 Design

Version 1 implements deterministic full-factorial designs. `replications` MUST
be positive. `seed` MUST be non-empty. `max_cells`, when present, selects a
stable seeded subset of factorial cells and MUST be positive. All and only SCM
exogenous variables are factors.

The projected run count is the product of treatment counts, limited by
`max_cells`, multiplied by `replications`. Validators SHOULD warn about empty
variation, truncation, and large projected runs. Power-based, blocked,
adaptive, and sequential designs are reserved extensions and must use a new
supported method rather than opaque Python.

### 5.6 Interaction

`interaction` is a serialized `Conversation`. Its roles must be declared study
roles. Protocol, stop rules, role-specific turn instructions, retirement rules,
structured response contracts, and transcript visibility are frozen inputs.
Structured contracts are preferred when a response has machine-enforceable
syntax.

### 5.7 Procedure requirements

A procedure requirement is a serializable invariant checked by validation or
execution. Version 1 reserves this list and accepts named requirements only
when the runtime implements their semantics. An unsupported requirement is an
error, never a silently ignored annotation.

## 6. Validation findings

Validation returns an ordered `blueprint_validation` document. Each finding
has `severity` (`error` or `warning`), stable `code`, JSON-style `path`,
`message`, and optional `suggestion`. Version 1 defines at least:

- `duplicate-role`
- `missing-role`
- `interaction-role-mismatch`
- `missing-information-policy`
- `duplicate-information-policy`
- `unknown-information-variable`
- `invalid-information-audience`
- `invalid-information-cardinality`
- `constant-factor`
- `design-too-large`
- `design-truncated`
- `insufficient-observations`
- `unsupported-design-method`
- `unsupported-procedure-requirement`

Constructors may reject malformed local values immediately. Cross-component
problems SHOULD be returned as findings so authoring tools can present several
issues in one pass.

## 7. Compilation semantics

For a valid version 1 blueprint, compilation MUST:

1. materialize the factorial design deterministically;
2. compile SCM roles, cells, and measurements with `ExperimentCompiler`;
3. apply information policies to public and participant-private contexts;
4. preserve the authored conversation definition;
5. attach the canonical blueprint hash and validation report; and
6. return a serializable `compiled_causal_study`.

The canonical hash is SHA-256 over compact, key-sorted JSON of `to_dict()`.
Equal blueprints therefore compile to equal hashes, designs, assignments, and
conversation definitions.

## 8. Safety, review, and execution

Private context is an orchestration boundary, not a claim of cryptographic
isolation. Adapters MUST send a participant only public context and context for
that participant's role. Human delivery MUST not embed another role's private
values in URLs, email copy, or shared survey state. Logs and reports SHOULD
redact or role-filter private treatment values where appropriate.

Draft generation, validation, compilation, execution, and publication are
separate permissions. In particular, producing or compiling a blueprint does
not authorize model spend, emails, human-subject recruitment, or publication.

## 9. Extensions

Future versions may add declarative power analysis, assignment units and
clusters, repeated-measures panels, richer information graphs, calculation
expressions, procedural gates, intervention policies, and authoring-model
provenance. Extensions must remain serializable, versioned, validate before
execution, and preserve deterministic compilation wherever their semantics
are deterministic.
