# FileStore: Working with Files in EDSL

## Creating a FileStore

Use `FileStore(path=...)` to wrap any file for use in surveys:

```python
from edsl import FileStore

fs = FileStore(path="photo.png")
```

This works with many file types: images (png, jpeg, svg), documents (PDF, DOCX, PPTX), data (CSV, spreadsheets, JSON), text (TXT, Markdown, HTML), code (Python, SQL), databases (SQLite), video (MP4, WebM), and LaTeX.

## Using FileStore in Scenarios

Pass a FileStore as a scenario value, then reference it in question text with Jinja2 templating:

```python
from edsl import FileStore, Scenario, QuestionFreeText, Survey

fs = FileStore(path="chart.png")
scenario = Scenario({"file_path": fs})

q = QuestionFreeText(
    question_name="describe",
    question_text="What is in this image: {{ scenario.file_path }}?"
)

survey = Survey([q])
results = survey.by(scenario).run()
```

The `{{ scenario.file_path }}` placeholder is replaced with the file content at runtime, so the model sees the actual image/document.

## Multiple Files with ScenarioList

Process many files by creating a scenario for each:

```python
from edsl import FileStore, Scenario, ScenarioList

filenames = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]

scenarios = ScenarioList([
    Scenario({"file_path": FileStore(path=f)}) for f in filenames
])

results = survey.by(scenarios).run()
```

## Combining Files with Other Scenario Data

Scenarios can contain both files and regular data:

```python
scenario = Scenario({
    "file_path": FileStore(path="resume.pdf"),
    "job_title": "Software Engineer"
})

q = QuestionFreeText(
    question_name="evaluate",
    question_text="Review this resume: {{ scenario.file_path }}. How well does the candidate fit the role of {{ scenario.job_title }}?"
)
```

## FileStores that come back as answers

A FileStore is not only an input. Two question types produce one as their **answer**, and
it behaves like any other FileStore from there — inspect it, save it, or pipe it into a
later question as an input file:

- `QuestionFileUpload` — the respondent's uploaded file(s), in a humanized survey. Wrap the
  raw answer with `FileStore.from_file_upload_answer` / `FileStoreList.from_file_upload_answers`
  (see `edsl:edsl-human-survey`).
- `QuestionImageGeneration` — an AI-generated image. Piping it into a later
  `QuestionImageGeneration` prompt sends it back to the provider as an input image, which
  is how you iterate on a generation (see `edsl:edsl-surveys`).

## Quick Reference

| Task | Code |
|------|------|
| Create from file | `FileStore(path="file.png")` |
| Wrap in scenario | `Scenario({"file_path": fs})` |
| Reference in question | `{{ scenario.file_path }}` |
| Multiple files | `ScenarioList([Scenario({"file_path": FileStore(path=f)}) for f in files])` |
| Extract text | `fs.extract_text()` |
| CSV to scenarios | `FileStore(path="data.csv").to_scenario_list()` |
| Get MIME type | `fs.mime_type` |
| Check if image | `fs.is_image()` |
| Generate an image as a FileStore | `QuestionImageGeneration(...)` → `edsl:edsl-surveys` |
