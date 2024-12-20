# Expected Parrot Domain-Specific Language 
<p align="center">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

The Expected Parrot Domain-Specific Language (EDSL) package lets you conduct computational social science and market research with AI. Use it to design surveys and experiments, simulate responses with large language models, and perform data labeling and other research tasks. Results are formatted as specified datasets and come with built-in methods for analyzing, visualizing, and sharing. 

## 🔗 Links
- [PyPI](https://pypi.org/project/edsl/)
- [Documentation](https://docs.expectedparrot.com)
- [Getting started](https://docs.expectedparrot.com/en/latest/starter_tutorial.html) 
- [Discord](https://discord.com/invite/mxAYkjfy9m)
- [Twitter](https://x.com/ExpectedParrot)
- [LinkedIn](https://www.linkedin.com/company/expectedparrot/)
- [Blog](https://blog.expectedparrot.com)

## 🌎 Hello, World!
A quick example:

```python
# Import a question type
from edsl import QuestionMultipleChoice

# Construct a question using the question type template
q = QuestionMultipleChoice(
    question_name="example_question",
    question_text="How do you feel today?",
    question_options=["Bad", "OK", "Good"]
)

# Run it with the default language model
results = q.run()

# Inspect the results in a dataset
results.select("example_question").print()
```

Output:
```python
┏━━━━━━━━━━━━━━━━━━━┓
┃ answer            ┃
┃ .example_question ┃
┡━━━━━━━━━━━━━━━━━━━┩
│ Good              │
└───────────────────┘
```

## 💻 Requirements
* EDSL is compatible with Python 3.9 - 3.12.
* API keys for large language models that you want to use, stored in a `.env` file.
See instructions on [storing API keys](https://docs.expectedparrot.com/en/latest/api_keys.html).

## 💡 Contributions, feature requests & bugs
Interested in contributing? Want us to add a new feature? Found a bug for us to squash? 
Please send us an email at [info@expectedparrot.com](mailto:info@expectedparrot.com) or message us at our [Discord channel](https://discord.com/invite/mxAYkjfy9m).
