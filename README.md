<p align="right">
  <img src="https://github.com/expectedparrot/edsl/blob/main/static/logo.png?raw=true" alt="edsl.png" width="100"/>
</p>

# Expected Parrot Domain-Specific Language (EDSL)

EDSL makes it easy to conduct computational social science and market research with AI. Use it to design and run surveys and experiments with many AI agents and large language models at once, or to perform complex data labeling and other research tasks. Results are formatted as specified datasets that can be replicated at no cost, and come with built-in methods for analysis, visualization and collaboration. 

## Getting started

1. Run `pip install edsl` to install the package. See the <a href="https://docs.expectedparrot.com/en/latest/installation" target="_blank" rel="noopener noreferrer">installation guide</a>.

2. <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Create an account</a> to run surveys at the Expected Parrot server and access a <a href="https://docs.expectedparrot.com/en/latest/remote_caching" target="_blank" rel="noopener noreferrer">universal remote cache</a> of stored responses for reproducing results.

3. Choose whether to use your own keys for language models or get an Expected Parrot key to access all available models at once. Securely <a href="https://www.expectedparrot.com/getting-started/edsl-api-keys" target="_blank" rel="noopener noreferrer">manage keys</a>,  expenses and usage for your team from your account.

4. Follow <a href="https://docs.expectedparrot.com/en/latest/starter_tutorial" target="_blank" rel="noopener noreferrer">Run your first survey</a>, then explore the <a href="https://docs.expectedparrot.com/en/latest/index#explore-the-docs" target="_blank" rel="noopener noreferrer">how-to guides and research examples</a>, including <a href="https://docs.expectedparrot.com/en/latest/guides/data_labeling" target="_blank" rel="noopener noreferrer">labeling data with survey questions</a>.

5. Share workflows and survey results at <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Coop</a>: a free platform for creating and sharing AI research.

## Use EDSL with coding harnesses

The copyable prompts below are for a harness you can already open. If you do
not have that harness installed yet, run its bootstrap command in a terminal
first. The script installs the selected harness when missing, installs EDSL
from this branch using uv when available (pip otherwise), logs in to Expected
Parrot if needed, and installs the harness-specific `edsl-harness` skill. Add
`--launch` to the bootstrap command to open the harness in the current
directory when setup finishes. Activate the Python environment where you want
EDSL installed before running it.

From a local EDSL checkout:

```bash
bash harnesses/install.sh pi --launch
```

Replace `pi` with `codex`, `claude-code`, `opencode`, `antigravity`, or `fx` as
needed. To bootstrap directly from this branch without cloning EDSL:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

<h3><img src="docs/assets/harness-icons/codex.svg" width="22" height="22" alt=""> Codex</h3>

If Codex is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- codex --launch
```

```text
Set up EDSL for Codex:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.agents/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

<h3><img src="docs/assets/harness-icons/claude-code.svg" width="22" height="22" alt=""> Claude Code</h3>

If Claude Code is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- claude-code --launch
```

```text
Set up EDSL for Claude Code:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.claude/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

<h3><img src="docs/assets/harness-icons/opencode.svg" width="22" height="22" alt=""> OpenCode</h3>

If OpenCode is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- opencode --launch
```

```text
Set up EDSL for OpenCode:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.config/opencode/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

<h3><img src="docs/assets/harness-icons/pi.svg" width="22" height="22" alt=""> Pi</h3>

If Pi is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

```text
Set up EDSL for Pi:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.pi/agent/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

<h3><img src="docs/assets/harness-icons/antigravity.png" width="22" height="22" alt=""> Google Antigravity CLI</h3>

If Google Antigravity CLI is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- antigravity --launch
```

```text
Set up EDSL for Google Antigravity CLI:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.gemini/config/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

<h3><img src="docs/assets/harness-icons/vercel-fx.svg" width="22" height="22" alt=""> Vercel fx</h3>

If Vercel fx is not installed, run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- fx --launch
```

```text
Set up EDSL for Vercel fx:
1. Install EDSL from this branch into the active Python environment. If uv is
   installed, run:
   `uv pip install --python "$(command -v python3)" --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
   Otherwise run:
   `python3 -m pip install --upgrade "edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance"`
2. Run `ep auth status`. If no Expected Parrot key is configured, run `ep auth login`.
   Never print or expose the key.
3. Install only the EDSL harness skill:
   ep skills install --target "$HOME/.fx/skills" --skill edsl-harness
Check the JSON status and warnings from each EDSL CLI command.
```

For skill locations and package discovery details, see the [harness setup guide](harnesses/README.md).

## Code & Docs
- <a href="https://github.com/expectedparrot/edsl" target="_blank" rel="noopener noreferrer">GitHub</a>
- <a href="https://pypi.org/project/edsl/" target="_blank" rel="noopener noreferrer">PyPI</a>
- <a href="https://docs.expectedparrot.com" target="_blank" rel="noopener noreferrer">Documentation</a>

## Requirements
- Python 3.10 - 3.13
- API keys for language models. You can use your own keys or an Expected Parrot key that provides access to all available models.
See instructions on <a href="https://docs.expectedparrot.com/en/latest/api_keys" target="_blank" rel="noopener noreferrer">managing keys</a> and <a href="https://www.expectedparrot.com/models" target="_blank" rel="noopener noreferrer">model pricing and performance</a> information.

## Coop
Expected Parrot provides a free platform for creating, storing and sharing AI-based research, and validating it with human respondents.
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Signup</a>
- <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Login / Explore</a>

## Community
- <a href="https://blog.expectedparrot.com" target="_blank" rel="noopener noreferrer">Blog</a>
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
