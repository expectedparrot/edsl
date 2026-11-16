# ScenarioList Creation Patterns

> **GOTCHAS -- read before writing any ScenarioList code**
>
> - **Build scenarios in a plain list or append to a `ScenarioList`.** Both patterns work; `ScenarioList.append()` mutates the sequence.
> - **Every scenario field must appear in `question_text`.** Use `{{ scenario.field }}` in the question text itself. Putting a scenario reference only in an `Instruction` will raise `JobsCompatibilityError`.
> - **`Scenario.from_image()` is a convenience for image scenarios.** A `Scenario` can also contain a `FileStore` constructed directly.
> - **Image scenarios require `{{ scenario.image_field }}` in EVERY question.** LLMs have no cross-question memory by default in EDSL. If you pass an image via a scenario in Q1, the image is NOT automatically available in Q2, Q3, etc. You must include `{{ scenario.image_field }}` in the `question_text` of every question that needs to see the image. This is the same as any scenario field — it only exists in the context where you explicitly reference it. Using memory modes to work around this is unnecessary and introduces token cost and carry-over bias.
> - **Guard empty ScenarioList before `.by()`.** Calling `.by()` with an empty `ScenarioList` raises `IndexError`. Check `len(scenario_list) > 0` first.
> - **`from_source()` auto-snakifies keys.** By default `ScenarioList.from_source()` converts column names to snake_case. Pass `snakify=False` to preserve originals.
> - **Save/load uses `.ep`.** Always use `scenario_list.git.save("scenario_list.ep")` / `ScenarioList.git.load("scenario_list.ep")`.

## From a List of Dicts

```python
from edsl import Scenario, ScenarioList

scenarios = ScenarioList([
    Scenario({"company": "Apple", "industry": "Technology", "revenue_b": 394}),
    Scenario({"company": "Amazon", "industry": "Retail/Cloud", "revenue_b": 575}),
    Scenario({"company": "Walmart", "industry": "Retail", "revenue_b": 648}),
])
```

## From External Data Sources

The `from_source()` method auto-detects the source type (just like `AgentList.from_source()`):

```python
from edsl import ScenarioList

# From CSV file
scenarios = ScenarioList.from_source("companies.csv")

# From Excel file
scenarios = ScenarioList.from_source("data.xlsx", sheet_name="Sheet1")

# From dictionary (column-oriented)
scenarios = ScenarioList.from_source({
    "company": ["Apple", "Google", "Microsoft"],
    "sector": ["Tech", "Tech", "Tech"],
    "employees": [164000, 182000, 221000],
})

# From pandas DataFrame
import pandas as pd
df = pd.DataFrame({"topic": ["AI", "climate"], "region": ["US", "EU"]})
scenarios = ScenarioList.from_source(df)
```

By default, `from_source()` converts column names to snake_case (`snakify=True`). Pass `snakify=False` to keep original names:
```python
scenarios = ScenarioList.from_source("data.csv", snakify=False)
```

For large files, load then slice:
```python
import pandas as pd
df = pd.read_csv("big_file.csv").sample(n=20, random_state=42)
scenario_list = ScenarioList.from_source(df)
```

## Programmatically with Combinations

```python
from edsl import Scenario, ScenarioList
from itertools import product

topics = ["climate change", "immigration", "healthcare"]
framings = ["positive", "negative", "neutral"]

scenario_list = ScenarioList([
    Scenario({"topic": topic, "framing": framing})
    for topic, framing in product(topics, framings)
])
# Creates 9 scenarios (3 topics x 3 framings)
```

## With Images

Use `Scenario.from_image()` to include images:

```python
from edsl import Scenario, ScenarioList

# Single image scenario
s = Scenario.from_image("photo.png")

# Add extra fields alongside the image
img_key = list(s.keys())[0]  # e.g., "photo"
scenario = Scenario({
    "my_image": s[img_key],
    "label": "Product A",
    "category": "electronics",
})

# Build a list of image scenarios
import glob

image_files = glob.glob("images/*.png")
scenarios_list = []
for img_path in image_files:
    s = Scenario.from_image(img_path)
    img_key = list(s.keys())[0]
    scenarios_list.append(Scenario({
        "image": s[img_key],
        "filename": img_path,
    }))

scenario_list = ScenarioList(scenarios_list)
```

**Using image scenarios in a survey:**

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice

# CRITICAL: Include {{ scenario.image }} in EVERY question that needs the image.
# LLMs have no cross-question memory by default.

q1 = QuestionFreeText(
    question_name="describe",
    question_text="Please look at this image: {{ scenario.image }}\n\nDescribe what you see."
)

q2 = QuestionMultipleChoice(
    question_name="category",
    question_text="Based on this image: {{ scenario.image }}\n\nWhich category best fits?",
    question_options=["Product", "Person", "Place", "Abstract"]
)

q3 = QuestionFreeText(
    question_name="emotion",
    question_text="Looking at this image again: {{ scenario.image }}\n\nWhat emotion does it convey?"
)

# Notice: {{ scenario.image }} appears in ALL THREE questions.
# If you omit it from q2 or q3, those questions won't see the image.

survey = Survey([q1, q2, q3])
results = survey.by(scenario_list).run()
```

## Combining ScenarioLists

```python
list_a = ScenarioList([Scenario({"x": 1}), Scenario({"x": 2})])
list_b = ScenarioList([Scenario({"x": 3}), Scenario({"x": 4})])

combined = list_a + list_b  # ScenarioList with 4 scenarios
```

## Save / Load

```python
# Save
scenario_list.git.save("scenario_list.ep")

# Load
from edsl import ScenarioList
scenario_list = ScenarioList.git.load("scenario_list.ep")
```

## Quick Reference

| Source | Pattern |
|--------|---------|
| List of dicts | `ScenarioList([Scenario({...}), ...])` |
| CSV file | `ScenarioList.from_source("file.csv")` |
| Excel file | `ScenarioList.from_source("file.xlsx", sheet_name="Sheet1")` |
| DataFrame | `ScenarioList.from_source(df)` |
| Dictionary | `ScenarioList.from_source({"col": [1, 2, 3]})` |
| Combinations | `itertools.product` + list comprehension |
| Images | `Scenario.from_image("file.png")` |
| Web data | Scrape/extract to list of dicts, then wrap |
| Combining | `list_a + list_b` |
