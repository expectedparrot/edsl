# Expected Parrot Domain-Specific Language (EDSL) <img src="static/logo.png" alt="" width="48">

EDSL is a Python library for research. You can build surveys, ask several AI models the same questions, and compare their answers in a dataset. You can send the same survey to people by sharing a URL or emailing them an invitation. You can also set up an AI interviewer to ask participants questions and follow up on their answers.

## The best way to use EDSL is with your coding agent

Choose your agent and paste the prompt into its chat. It will set up EDSL and make a three-question survey you can preview on your computer.

<details>
<summary><img src="docs/assets/harness-icons/codex.svg" width="22" height="22" alt=""> Codex</summary>

Paste into Codex:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Codex, then make a three-question survey about coffee habits and show me the preview.
```

Need Codex first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- codex --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/claude-code.svg" width="22" height="22" alt=""> Claude Code</summary>

Paste into Claude Code:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Claude Code, then make a three-question survey about coffee habits and show me the preview.
```

Need Claude Code first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- claude-code --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/opencode.svg" width="22" height="22" alt=""> OpenCode</summary>

Paste into OpenCode:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for OpenCode, then make a three-question survey about coffee habits and show me the preview.
```

Need OpenCode first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- opencode --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/pi.svg" width="22" height="22" alt=""> Pi</summary>

Paste into Pi:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Pi, then make a three-question survey about coffee habits and show me the preview.
```

Need Pi first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/antigravity.png" width="22" height="22" alt=""> Google Antigravity CLI</summary>

Paste into Google Antigravity CLI:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Google Antigravity CLI, then make a three-question survey about coffee habits and show me the preview.
```

Need Google Antigravity CLI first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- antigravity --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/vercel-fx.svg" width="22" height="22" alt=""> Vercel fx</summary>

Paste into Vercel fx:

```text
Follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Vercel fx, then make a three-question survey about coffee habits and show me the preview.
```

Need Vercel fx first? Run this in your terminal, then paste the prompt above.

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- fx --launch
```

</details>

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

## Getting started

1. Run `pip install edsl` to install the package. See the <a href="https://docs.expectedparrot.com/en/latest/installation" target="_blank" rel="noopener noreferrer">installation guide</a>.

2. <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Create an account</a> to run surveys at the Expected Parrot server and access a <a href="https://docs.expectedparrot.com/en/latest/remote_caching" target="_blank" rel="noopener noreferrer">universal remote cache</a> of stored responses for reproducing results.

3. Choose whether to use your own keys for language models or get an Expected Parrot key to access all available models at once. Securely <a href="https://www.expectedparrot.com/getting-started/edsl-api-keys" target="_blank" rel="noopener noreferrer">manage keys</a>,  expenses and usage for your team from your account.

4. Follow <a href="https://docs.expectedparrot.com/en/latest/starter_tutorial" target="_blank" rel="noopener noreferrer">Run your first survey</a>, then explore the <a href="https://docs.expectedparrot.com/en/latest/index#explore-the-docs" target="_blank" rel="noopener noreferrer">how-to guides and research examples</a>, including <a href="https://docs.expectedparrot.com/en/latest/guides/data_labeling" target="_blank" rel="noopener noreferrer">labeling data with survey questions</a>.

5. Share workflows and survey results at <a href="https://www.expectedparrot.com/login" target="_blank" rel="noopener noreferrer">Coop</a>: a free platform for creating and sharing AI research.
