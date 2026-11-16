---
name: edsl-quirks
description: Diagnose EDSL compatibility failures and known API edge cases using the version-matched reference.
tags: [edsl, compatibility]
---

# Diagnose an EDSL compatibility issue

Use this skill when an EDSL command or script fails, or when implementing an advanced feature known to be fragile. Start from the exact error or feature and search the local reference:

```bash
rg -n "<error-fragment|feature-name>" references/full-reference.md
```

Apply the smallest fix supported by the installed EDSL version. Prefer documented CLI and API behavior over assumptions. This bundle describes EDSL behavior; workflow policy and research-method choices are outside its scope.

See [the compatibility reference](references/full-reference.md). Related EDSL guidance: `edsl:edsl-surveys`.
