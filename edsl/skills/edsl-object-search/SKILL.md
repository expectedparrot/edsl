---
name: edsl-object-search
description: Search, inspect, clone, and pull shared EDSL objects through the EDSL CLI.
tags: [edsl, reference]
---

# EDSL remote object search

Use `ep search --query <text> --page 1 --page_size 50` to search available objects. Inspect metadata and object type, then use `ep clone <owner>/<alias> --path object.ep` or `ep pull object.ep` as appropriate. `ep inspect` and `ep metadata` expose local package details. Set explicit pagination and use installed CLI help for current filters.

Search and retrieval are EDSL CLI capabilities.
