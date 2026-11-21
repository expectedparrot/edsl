---
name: edsl-surveys-cost
description: Estimate EDSL job costs and manage EDSL low-balance email settings.
tags: [edsl, reference]
---

# EDSL cost tools

Use `ep jobs cost jobs.ep` to estimate a saved job and `ep results cost results.ep` to inspect actual costs. Estimates depend on model pricing, prompt size, iteration counts, token overrides, and skip logic; consult [estimation details](references/estimation-details.md) and [calibration and branching](references/calibration-and-branching.md) for calculation details.

Use `ep balance` to inspect the configured account balance and `ep balance alert` to manage low-balance notifications. Cost estimates and alerts are EDSL features; study budget approval and whether to run a job are separate workflow decisions.
