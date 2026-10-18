---
configs:
- config_name: agents
  data_files:
  - split: train
    path: agents/*.parquet
- config_name: scenarios
  data_files:
  - split: train
    path: scenarios/*.parquet
dataset_info:
- features:
  - name: age
    dtype: int64
  - name: note
    dtype: 'null'
  - name: _edsl_explicit_nulls
    list: string
  - name: _edsl_name
    dtype: string
  config_name: agents
  splits:
  - name: train
    num_bytes: 48
    num_examples: 2
- features:
  - name: text
    dtype: string
  - name: nested
    dtype: string
  config_name: scenarios
  splits:
  - name: train
    num_bytes: 29
    num_examples: 1
edsl:
  format_version: 1
  edsl_version: 1.0.8.dev1
  objects:
    agents:
      class: AgentList
      n: 2
      columns:
        age:
          kind: trait
          edsl_type: int
          original_key: age
        note:
          kind: trait
          edsl_type: 'null'
          original_key: note
          nullable: true
      codebook:
        age: Age in years
    scenarios:
      class: ScenarioList
      n: 1
      columns:
        text:
          kind: field
          edsl_type: str
          original_key: text
        nested:
          kind: field
          edsl_type: json
          original_key: nested
---

# EDSL dataset

Created with [EDSL](https://docs.expectedparrot.com). Each config contains a Parquet `train` split, usable without EDSL.

```python
from datasets import load_dataset
data = load_dataset("REPO_ID_OR_LOCAL_FOLDER", name="agents", split="train")
```

| Field | Description |
| --- | --- |
| age | Age in years |
