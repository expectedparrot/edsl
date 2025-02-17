# Expected Parrot Domain-Specific Language (EDSL)

The Expected Parrot Domain-Specific Language (EDSL) package makes it easy to conduct computational social science and market research with AI. Use it to design surveys and experiments, collect responses from humans and large language models, and perform data labeling and many other research tasks. Results are formatted as specified datasets and come with built-in methods for analyzing, visualizing and sharing. 
<p align="right">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

## Getting started
- [PyPI](https://pypi.org/project/edsl/): `pip install edsl`
- [GitHub](https://github.com/expectedparrot/edsl)
- [Documentation](https://docs.expectedparrot.com)
- [Starter tutorial](https://docs.expectedparrot.com/en/latest/starter_tutorial.html) 

## Requirements
- Python 3.9 - 3.12
- API keys for language models. You can use your own keys or an Expected Parrot key that provides access to all available models.
See instructions on [managing keys](https://docs.expectedparrot.com/en/latest/api_keys.html) and [model pricing and performance](https://www.expectedparrot.com/getting-started/coop-pricing) information.

## Coop
An integrated platform for running experiments, sharing workflows and launching hybrid human/AI surveys.
- [Login/Signup](https://www.expectedparrot.com/login)
- [Explore](https://www.expectedparrot.com/content/explore)

## Community
- [Discord](https://discord.com/invite/mxAYkjfy9m)
- [Twitter](https://x.com/ExpectedParrot)
- [LinkedIn](https://www.linkedin.com/company/expectedparrot/)
- [Blog](https://blog.expectedparrot.com)

## Contact
- [Email](mailto:info@expectedparrot.com) 

## Hello, World!
A quick example:

```python
# Import a question type
from edsl import QuestionMultipleChoice, Agent, Model

# Construct a question
q = QuestionMultipleChoice(
    question_name = "color",
    question_text = "What is your favorite primary color?",
    question_options = ["Red", "Yellow", "Blue"]
)

# Design an agent
a = Agent(traits = {"persona":"You are a botanist."})

# Select a model
m = Model("gemini-1.5-flash")

# Administer the question
results = q.by(a).by(m).run()

# Inspect the results
results.select("color")
```

Output:
| answer.color  | comment.color_comment                                                            |
|:------------- |:--------------------------------------------------------------------------------|
| Blue         | It's the color of so many beautiful flowers, from forget-me-nots to hydrangeas.<br>Plus, it reminds me of a clear, cool spring day, perfect for exploring the wild. |


[See results at Coop](https://www.expectedparrot.com/content/85583c1a-b407-4695-80eb-fd89b55cccd2)
