<p align="right">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

# Expected Parrot Domain-Specific Language (EDSL)

EDSL makes it easy to conduct computational social science and market research with AI. Use it to design and run surveys and experiments with many AI agents and large language models at once, or to perform complex data labeling and other research tasks. Results are formatted as specified datasets that can be replicated at no cost, and come with built-in methods for analysis, visualization and collaboration. 

## Getting started

1. Run `pip install edsl` to install the package. See <a href="https://www.expectedparrot.com/getting-started" target="_blank" rel="noopener noreferrer">instructions</a>.

2. <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Create an account</a> to run surveys at the Expected Parrot server and access a <a href="https://docs.expectedparrot.com/en/latest/remote_caching" target="_blank" rel="noopener noreferrer">universal remote cache</a> of stored responses for reproducing results.

3. Choose whether to use your own keys for language models or get an Expected Parrot key to access all available models at once. Securely <a href="https://www.expectedparrot.com/getting-started/edsl-api-keys" target="_blank" rel="noopener noreferrer">manage keys</a>,  expenses and usage for your team from your account.

4. Run the <a href="https://docs.expectedparrot.com/en/latest/starter_tutorial" target="_blank" rel="noopener noreferrer">starter tutorial</a> and explore other demo notebooks for a variety of use cases. 

5. Share workflows and survey results at <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Coop</a>: a free platform for creating and sharing AI research.

6. Join our <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank" rel="noopener noreferrer">Discord</a> for updates and discussions! 

## Getting started with a coding agent

EDSL includes the `ep` command-line interface for creating surveys, validating jobs, running them locally or through Expected Parrot / Coop, and inspecting saved results. Copy the instructions below into your coding agent. The fenced block is copyable in GitHub.

```text
You are working in a project that uses EDSL (Expected Parrot's Python library) and its `ep` command-line interface. Help me create, validate, and, when requested, run EDSL surveys in this workspace.

SETUP
- Check whether `ep` is installed with `ep --help` and `ep info`. If it is missing, install EDSL in the active Python environment with `pip install edsl`, then check again.
- Read the command list in `ep --help`. Before using a command or guessing flags, read `ep <command> --help`.
- For Expected Parrot / Coop remote services, check `ep auth status`. If login is needed, run `ep auth login`; it opens a browser-based sign-in flow and stores the key. If this environment cannot open a browser, tell me to complete login in an environment that can. Do not ask me to paste a secret into chat, put keys in source files, or expose keys in shell history.
- EDSL model calls need model credentials. Use the Expected Parrot key for remote inference or configure a provider key for local inference. Follow https://docs.expectedparrot.com/en/latest/api_keys.html and keep credentials private.

FIND DOCUMENTATION
- Search https://docs.expectedparrot.com using its search box for concepts and examples relevant to the task.
- Use `ep schema list` and `ep schema show --class Survey` or `ep schema show --question_type <type>` to inspect supported serialized formats. Use `ep validate --help` and other command help for current CLI behavior.
- In this repository, search source and examples with `rg` when the docs do not answer a question.

CREATE AND RUN A SURVEY
- Prefer durable `.ep` packages for EDSL objects. Create or edit the survey and any agents, scenarios, and model choices needed for the task. Do not launch inference just because you created a survey.
- Validate the survey or job before running it. For a Jobs file, use `ep validate --file jobs.ep`; fix validation errors before continuing.
- When I ask you to run the job, estimate scope/cost when useful with `ep jobs cost jobs.ep`, then run it and save the results: `ep run jobs.ep --output results.ep`. Use `--local` when I request local inference and provider credentials are configured. Remote runs use Expected Parrot / Coop credentials.
- Check each command's JSON `status` and `warnings`. Do not treat a command as successful based only on its exit code or diagnostic text.
- Inspect saved results with `ep results columns --file results.ep` and a bounded sample such as `ep results select --file results.ep --column "answer.*" --limit 5`. Summarize what was created, how it ran, and where results were saved.
```

## Code & Docs
- <a href="https://github.com/expectedparrot/edsl" target="_blank" rel="noopener noreferrer">GitHub</a>
- <a href="https://pypi.org/project/edsl/" target="_blank" rel="noopener noreferrer">PyPI</a>
- <a href="https://docs.expectedparrot.com" target="_blank" rel="noopener noreferrer">Documentation</a>

## Requirements
- Python 3.9 - 3.13
- API keys for language models. You can use your own keys or an Expected Parrot key that provides access to all available models.
See instructions on <a href="https://docs.expectedparrot.com/en/latest/api_keys" target="_blank" rel="noopener noreferrer">managing keys</a> and <a href="https://www.expectedparrot.com/models" target="_blank" rel="noopener noreferrer">model pricing and performance</a> information.

## Coop
Expected Parrot provides a free platform for creating, storing and sharing AI-based research, and validating it with human respondents.
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Signup</a>
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Explore</a>

## Community
- <a href="https://blog.expectedparrot.com" target="_blank" rel="noopener noreferrer">Blog</a>
- <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank" rel="noopener noreferrer">Discord</a>
- <a href="https://x.com/ExpectedParrot" target="_blank" rel="noopener noreferrer">Twitter</a>
- <a href="https://www.linkedin.com/company/expectedparrot/" target="_blank" rel="noopener noreferrer">LinkedIn</a>

## Contact
- <a href="mailto:info@expectedparrot.com" target="_blank" rel="noopener noreferrer">Email</a>


## Features 

**Declarative design**: 
Specified <a href="https://docs.expectedparrot.com/en/latest/questions" target="_blank" rel="noopener noreferrer">question types</a> ensure consistent results without requiring a JSON schema (<a href="https://www.expectedparrot.com/content/2a848a0e-f9de-46bc-98d0-a13b9a1caf11" target="_blank" rel="noopener noreferrer">view at Coop</a>):

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
Easily parameterize and control prompts with "<a href="https://docs.expectedparrot.com/en/latest/scenarios" target="_blank" rel="noopener noreferrer">scenarios</a>" of data automatically imported from many sources (CSV, PDF, PNG, etc.) (<a href="https://www.expectedparrot.com/content/7bb9ec2e-827b-4867-ac02-33163df1a1d1" target="_blank" rel="noopener noreferrer">view at Coop</a>):

```python
from edsl import ScenarioList, QuestionLinearScale

q = QuestionLinearScale(
  question_name = "example",
  question_text = "How much do you enjoy {{ scenario.activity }}?",
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
Construct agents with relevant traits to provide diverse responses to your surveys. Note that agent responses are generated by language models based on their training data — they reflect statistical patterns, not the actual opinions of any demographic group. Use AI-simulated responses for prototyping and pre-testing, and validate with real human data when measuring actual attitudes or behaviors. (<a href="https://www.expectedparrot.com/content/b639a2d7-4ae6-48fe-8b9e-58350fab93de" target="_blank" rel="noopener noreferrer">view at Coop</a>)

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
> | detective      | ['Gray', 'Black', 'Navy Blue']              |

<br>

**Simplified access to LLMs**: 
Choose whether to use your own API keys for LLMs, or access all <a href="https://www.expectedparrot.com/models" target="_blank" rel="noopener noreferrer">available models</a> with an Expected Parrot key. Run surveys with many models at once and compare responses at a convenient interface (<a href="https://www.expectedparrot.com/content/044465f0-b87f-430d-a3b9-4fd3b8560299" target="_blank" rel="noopener noreferrer">view at Coop</a>)

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

**Caching & reproducibility**: 
API calls to LLMs are cached automatically. When you run a survey remotely, results are stored at the Expected Parrot server with verified prompts and timestamps. Share your code and anyone can retrieve your exact outputs at no cost, with no setup or API keys required. Learn more about how the <a href="https://docs.expectedparrot.com/en/latest/remote_caching" target="_blank" rel="noopener noreferrer">universal remote cache</a> works.

**Flexibility**: 
Choose whether to run surveys on your own computer or at the Expected Parrot server.

**Tools for collaboration**: 
Easily share workflows and projects privately or publicly at Coop: an integrated platform for AI-based research. Your account comes with free credits for running surveys, and lets you securely share keys, track expenses and usage for your team.

**Built-in tools for analysis**: 
Analyze results as specified datasets from your account or workspace. Easily import data to use with your surveys and export results
