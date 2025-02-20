# Expected Parrot Domain-Specific Language (EDSL)

The Expected Parrot Domain-Specific Language (EDSL) package makes it easy to conduct computational social science and market research with AI. Use it to design surveys and experiments, collect responses from humans and large language models, and perform data labeling and many other research tasks. Results are formatted as specified datasets and come with built-in methods for analyzing, visualizing and sharing. 

## Features 
**Caching**
API calls to LLMs are cached automatically, allowing you to retrieve responses to questions that have already been run and reproduce experiments at no cost. Learn more about how the <a href="https://docs.expectedparrot.com/en/latest/remote_caching.html" target="_blank" rel="noopener noreferrer">universal remote cache</a> works.

**Simplified access to LLMs**
Choose whether to use your own keys for LLMs, or access all <a href="https://www.expectedparrot.com/getting-started/coop-pricing" target="_blank" rel="noopener noreferrer">available models</a> with an Expected Parrot API key. Run surveys with many models at once and compare responses at a convenient inferface.

**Flexibility**
Choose whether to run surveys on your own computer or at the Expected Parrot server.

**Tools for collaboration**
Easily share workflows and projects privately or publicly at Coop: an integrated platform for AI-based research. Your account comes with free credits for running surveys, and lets you securely share keys, track expenses and usage for your team.

**Hybrid human/AI surveys**
Launch surveys and collect responses from humans and AI. Choose how to deliver surveys and analyze results from your Coop account or workspace.

**Declarative design**
Declared <a href="https://docs.expectedparrot.con/en/latest/questions.html" target="_blank" rel="noopener noreferrer">question types</a> ensure consistent results without requiring a JSON schema.

**Parameterized prompts**
Easily parameterize and control prompts with "<a href="https://docs.expectedparrot.com/en/latest/scenarios.html" target="_blank" rel="noopener noreferrer">scenarios</a>" of data automatically imported from many sources (CSV, PDF, PNG, etc.).

**Piping & skip-logic** 
Build rich data labeling flows with features for piping answers and adding survey logic such as skip and stop rules.

**Built-in tools for analyis**
Analyze results as specified datasets from your account or workspace. Easily import data to use with your surveys and export results.


<p align="right">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

## Getting started

1. Run `pip install edsl` to install the package.

2. <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Create an account</a> to run surveys at the Expected Parrot server and access a <a href="https://docs.expectedparrot.com/en/latest/remote_caching.html" target="_blank" rel="noopener noreferrer">universal remote cache</a> of stored responses for reproducing results.

3. Choose whether to use your own keys for language models or get an Expected Parrot key to access all available models at once. Securely <a href="https://docs.expectedparrot.com/en/latest/api_keys.html" target="_blank" rel="noopener noreferrer">manage keys</a>, share expenses and track usage for your team from your account.

4. Run the <a href="https://docs.expectedparrot.com/en/latest/starter_tutorial.html" target="_blank" rel="noopener noreferrer">starter tutorial</a> and explore other demo notebooks. 

5. Share workflows and survey results at <a href="https://www.expectedparrot.com/content/explore" target="_blank" rel="noopener noreferrer">Coop</a>

6. Join our <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank" rel="noopener noreferrer">Discord</a> for updates and discussions! Request new features!

## Code & Docs
- <a href="https://pypi.org/project/edsl/" target="_blank" rel="noopener noreferrer">PyPI</a>
- <a href="https://github.com/expectedparrot/edsl" target="_blank" rel="noopener noreferrer">GitHub</a>
- <a href="https://docs.expectedparrot.com" target="_blank" rel="noopener noreferrer">Documentation</a>

## Requirements
- Python 3.9 - 3.12
- API keys for language models. You can use your own keys or an Expected Parrot key that provides access to all available models.
See instructions on <a href="https://docs.expectedparrot.com/en/latest/api_keys.html" target="_blank" rel="noopener noreferrer">managing keys</a> and <a href="https://www.expectedparrot.com/getting-started/coop-pricing" target="_blank" rel="noopener noreferrer">model pricing and performance</a> information.

## Coop
An integrated platform for running experiments, sharing workflows and launching hybrid human/AI surveys.
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Signup</a>
- <a href="https://www.expectedparrot.com/content/explore" target="_blank" rel="noopener noreferrer">Explore</a>

## Community
- <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank" rel="noopener noreferrer">Discord</a>
- <a href="https://x.com/ExpectedParrot" target="_blank" rel="noopener noreferrer">Twitter</a>
- <a href="https://www.linkedin.com/company/expectedparrot/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
- <a href="https://blog.expectedparrot.com" target="_blank" rel="noopener noreferrer">Blog</a>

## Contact
- <a href="mailto:info@expectedparrot.com" target="_blank" rel="noopener noreferrer">Email</a>

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
|--------------|---------------------------------------------------------------------------------|
| Blue         | It's the color of so many beautiful flowers, from forget-me-nots to hydrangeas.<br>Plus, it reminds me of a clear, cool spring day, perfect for exploring the wild. |


[See results at Coop](https://www.expectedparrot.com/content/85583c1a-b407-4695-80eb-fd89b55cccd2)
