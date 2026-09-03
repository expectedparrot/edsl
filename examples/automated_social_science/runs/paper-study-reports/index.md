# Automated Social Science: EDSL replications

## Overview

This collection recreates all four published experimental designs with serializable EDSL causal and conversation objects and a contemporary Google model.

| Study | Cells | EDSL mean | Paper mean | Mean turns |
|---|---:|---:|---:|---:|
| Bail hearing | 245 | 42204.082 | 54428.570 | 7.18 |
| Lawyer job interview | 80 | 0.575 | 0.620 | 13.85 |
| Art auction | 343 | 277.609 | 186.530 | 14.75 |

## Reports

- [Mug bargaining](../mug-original-replication/report.html)
- [Bail hearing](../paper-replications-v3/bail/report.html)
- [Lawyer job interview](../paper-replications/interview/report.html)
- [Art auction](../paper-replications-v8/auction/report.html)

## What changed during validation

The first bail pass allowed the judge to decide before hearing the parties; a second pass fixed sequencing but showed that private defendant facts never reliably reached the judge. The canonical bail run therefore models criminal history and expressed remorse as shared courtroom information.

The first auction pass allowed closure after bidder 1. The canonical auction requires all three bidders to participate before closure. This restored strong positive budget effects, although the published 20-turn cap still truncates most auctions.

## Reproducibility

Each study directory contains its compiled experiment, conversation definition, frozen analysis plan, benchmark, fitted results, flat CSV, and one durable transcript/provenance bundle per factorial cell.
