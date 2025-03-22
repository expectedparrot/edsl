# Expected Parrot Domain-Specific Language (EDSL)

The Expected Parrot Domain-Specific Language (EDSL) package makes it easy to conduct computational social science and market research with AI. Use it to design surveys and experiments, collect responses from humans and large language models, and perform data labeling and many other research tasks. Results are formatted as specified datasets and come with built-in methods for analyzing, visualizing and sharing. 

<p align="right">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

## Features 

**Declarative design**: 
Specified <a href="https://docs.expectedparrot.con/en/latest/questions.html" target="_blank" rel="noopener noreferrer">question types</a> ensure consistent results without requiring a JSON schema (<a href="https://www.expectedparrot.com/content/2a848a0e-f9de-46bc-98d0-a13b9a1caf11" target="_blank" rel="noopener noreferrer">view at Coop</a>):

```python
from edsl import QuestionMultipleChoice

q = QuestionMultipleChoice(
  question_name = "example",
  question_text = "How do you feel today?",
  question_options = ["Bad", "OK", "Good"]
)

results = q.run()

results.select("example")
```

> | answer.example  |
> |-----------------|
> | Good            |

<br>

**Parameterized prompts**: 
Easily parameterize and control prompts with "<a href="https://docs.expectedparrot.com/en/latest/scenarios.html" target="_blank" rel="noopener noreferrer">scenarios</a>" of data automatically imported from many sources (CSV, PDF, PNG, etc.)(<a href="https://www.expectedparrot.com/content/7bb9ec2e-827b-4867-ac02-33163df1a1d1" target="_blank" rel="noopener noreferrer">view at Coop</a>):

```python
from edsl import ScenarioList, QuestionLinearScale

q = QuestionLinearScale(
  question_name = "example",
  question_text = "How much do you enjoy {{ activity }}?",
  question_options = [1,2,3,4,5,],
  option_labels = {1:"Not at all", 5:"Very much"}
)

sl = ScenarioList.from_list("activity", ["coding", "sleeping"])

results = q.by(sl).run()

results.select("activity", "example")
```

> | scenario.activity  | answer.example  |
> |--------------------|-----------------|
> | Coding             | 5               |
> | Sleeping           | 5               |

<br>

**Design AI agent personas to answer questions**: 
Construct agents with relevant traits to provide diverse responses to your surveys (<a href="https://www.expectedparrot.com/content/b639a2d7-4ae6-48fe-8b9e-58350fab93de" target="_blank" rel="noopener noreferrer">view at Coop</a>)

```python
from edsl import Agent, AgentList, QuestionList

al = AgentList(Agent(traits = {"persona":p}) for p in ["botanist", "detective"])

q = QuestionList(
  question_name = "example",
  question_text = "What are your favorite colors?",
  max_list_items = 3
)

results = q.by(al).run()

results.select("persona", "example")
```

> | agent.persona  | answer.example                              |
> |----------------|---------------------------------------------|
> | botanist       | ['Green', 'Earthy Brown', 'Sunset Orange']  |
> | detective      | ['Gray', 'Black', 'Navy Blye']              |

<br>

**Simplified access to LLMs**: 
Choose whether to use your own keys for LLMs, or access all <a href="https://www.expectedparrot.com/getting-started/coop-pricing" target="_blank" rel="noopener noreferrer">available models</a> with an Expected Parrot API key. Run surveys with many models at once and compare responses at a convenient inferface (<a href="https://www.expectedparrot.com/content/044465f0-b87f-430d-a3b9-4fd3b8560299" target="_blank" rel="noopener noreferrer">view at Coop</a>)

```python
from edsl import Model, ModelList, QuestionFreeText

ml = ModelList(Model(m) for m in ["gpt-4o", "gemini-1.5-flash"])

q = QuestionFreeText(
  question_name = "example",
  question_text = "What is your top tip for using LLMs to answer surveys?"
)

results = q.by(ml).run()

results.select("model", "example")
```

> | model.model        | answer.example                                                                                  |
> |--------------------|-------------------------------------------------------------------------------------------------|
> | gpt-4o             | When using large language models (LLMs) to answer surveys, my top tip is to ensure that the ... |
> | gemini-1.5-flash   | My top tip for using LLMs to answer surveys is to **treat the LLM as a sophisticated brainst... |

<br>

**Piping & skip-logic**: 
Build rich data labeling flows with features for piping answers and adding survey logic such as skip and stop rules (<a href="https://www.expectedparrot.com/content/b8afe09d-49bf-4c05-b753-d7b0ae782eb3" target="_blank" rel="noopener noreferrer">view at Coop</a>):

```python
from edsl import QuestionMultipleChoice, QuestionFreeText, Survey

q1 = QuestionMultipleChoice(
  question_name = "color",
  question_text = "What is your favorite primary color?",
  question_options = ["red", "yellow", "blue"]
)

q2 = QuestionFreeText(
  question_name = "flower",
  question_text = "Name a flower that is {{ color.answer }}."
)

survey = Survey(questions = [q1, q2])

results = survey.run()

results.select("color", "flower")
```

> | answer.color  | answer.flower                                                                     |
> |---------------|-----------------------------------------------------------------------------------|
> | blue          | A commonly known blue flower is the bluebell. Another example is the cornflower.  |

<br>

**Caching**: 
API calls to LLMs are cached automatically, allowing you to retrieve responses to questions that have already been run and reproduce experiments at no cost. Learn more about how the <a href="https://docs.expectedparrot.com/en/latest/remote_caching.html" target="_blank" rel="noopener noreferrer">universal remote cache</a> works.

**Logging**:
EDSL includes a comprehensive logging system to help with debugging and monitoring. Control log levels and see important information about operations:

```python
from edsl import logger
import logging

# Set the logging level
logger.set_level(logging.DEBUG)  # Show all log messages

# Get a module-specific logger
my_logger = logger.get_logger(__name__)
my_logger.info("This is a module-specific log message")

# Log messages at different levels
logger.debug("Detailed debugging information")
logger.info("General information about operation")
logger.warning("Something unexpected but not critical")
logger.error("Something went wrong")
```

**Flexibility**: 
Choose whether to run surveys on your own computer or at the Expected Parrot server.

**Tools for collaboration**: 
Easily share workflows and projects privately or publicly at Coop: an integrated platform for AI-based research. Your account comes with free credits for running surveys, and lets you securely share keys, track expenses and usage for your team.

**Built-in tools for analyis**: 
Analyze results as specified datasets from your account or workspace. Easily import data to use with your surveys and export results.

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

## Developer Notes

### Running Tests
- Unit tests: `python -m pytest tests/`  
- Integration tests: `python -m pytest integration/`
- Doctests: `python run_doctests.py` (use `-v` flag for verbose output)

## Coop
An integrated platform for running experiments, sharing workflows and launching hybrid human/AI surveys.
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Signup</a>
- <a href="https://www.expectedparrot.com/content/explore" target="_blank" rel="noopener noreferrer">Explore</a>

## Community
- <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank" rel="noopener noreferrer">Discord</a>
- <a href="https://x.com/ExpectedParrot" target="_blank" rel="noopener noreferrer">Twitter</a>
- <a href="https://www.linkedin.com/company/expectedparrot/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
- <a href="https://blog.expectedparrot.com" target="_blank" rel="noopener noreferrer">Blog</a>.

## Contact
- <a href="mailto:info@expectedparrot.com" target="_blank" rel="noopener noreferrer">Email</a>.
