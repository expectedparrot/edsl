---
name: edsl-human-survey-agent-access
description: Configure EDSL human survey access for AI agents, including participation modes and question guidance.
tags: [edsl, reference]
---

# EDSL human survey agent access

EDSL humanized surveys can expose an agent participation route. Use `ep humanize agent-access get <survey_uuid>` to inspect the configuration and `patch` to update participation mode, general instructions, or question-specific instructions. Consult `ep humanize agent-access --help` for all supported options.

This configuration controls agent access to a human survey. It is distinct from browser respondent links and from the AI chat assistant feature. See the [detailed agent-access guide](references/detailed-guide.md) for modes, config fields, answer limitations, and result representation.

Related bundle: `edsl:edsl-human-survey`.
