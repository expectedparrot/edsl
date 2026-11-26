# <img src="static/edsl-wordmark.svg" alt="EDSL" width="180" height="48">

EDSL is a Python library for surveys and simulations. You describe a study in natural language, and your coding agent uses EDSL to write and run it. The study design lives in code, so you can inspect it, ask the agent to change it, and run it again.

## The best way to use EDSL is with your coding agent

Choose your agent and paste the prompt into its chat. It will set up EDSL and make a three-question survey you can preview on your computer.

<details>
<summary><img src="docs/assets/harness-icons/codex.svg" width="22" height="22" alt=""> Codex</summary>

Paste into Codex:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Codex. Make a three-question survey about coffee habits and show me the preview.
```

Need Codex first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- codex --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/claude-code.svg" width="22" height="22" alt=""> Claude Code</summary>

Paste into Claude Code:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Claude Code. Make a three-question survey about coffee habits and show me the preview.
```

Need Claude Code first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- claude-code --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/opencode.svg" width="22" height="22" alt=""> OpenCode</summary>

Paste into OpenCode:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for OpenCode. Make a three-question survey about coffee habits and show me the preview.
```

Need OpenCode first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- opencode --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/pi.svg" width="22" height="22" alt=""> Pi</summary>

Paste into Pi:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Pi. Make a three-question survey about coffee habits and show me the preview.
```

Need Pi first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/antigravity.png" width="22" height="22" alt=""> Google Antigravity CLI</summary>

Paste into Google Antigravity CLI:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Google Antigravity CLI. Make a three-question survey about coffee habits and show me the preview.
```

Need Google Antigravity CLI first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- antigravity --launch
```

</details>

<details>
<summary><img src="docs/assets/harness-icons/vercel-fx.svg" width="22" height="22" alt=""> Vercel fx</summary>

Paste into Vercel fx:

```text
Follow `ep skills show edsl-harness`. If unavailable, follow https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Vercel fx. Make a three-question survey about coffee habits and show me the preview.
```

Need Vercel fx first? Run this in your project terminal. When the agent opens, ask: **Make a three-question survey about coffee habits and show me the preview.**

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- fx --launch
```

</details>

The terminal installer offers project, user-wide, and routing-skill setup. [Setup options](harnesses/README.md#installing-the-agent-from-a-terminal)

## Key features

| Feature | What you can do |
| --- | --- |
| Question types | Ask respondents to choose one or more options, rate items in a matrix, rank choices, allocate a budget, or enter a number or free-text answer. [Question catalog](https://docs.expectedparrot.com/en/latest/questions) |
| Survey logic | Branch or stop based on an answer, pipe it into a later question, or repeat a group of follow-ups for each item a respondent lists. [Survey logic guide](https://docs.expectedparrot.com/en/latest/guides/survey_logic) |
| Model access | Use one Expected Parrot API key to access hundreds of AI models, or use your own provider keys. |
| Model comparison | Give several models the same survey and compare answers by model, scenario, or simulated persona. |
| Human surveys | Share a survey by URL or send email invitations and collect responses. |
| AI interviews | Give an AI interviewer a research question and let it ask participants follow-up questions. |
| Data labeling | Apply the same questions to each document, image, or row in a dataset. |
| Results | Filter answers, export them to CSV, and reuse cached model responses when repeating an analysis. |

For Python setup and a worked example, see the [installation guide](https://docs.expectedparrot.com/en/latest/installation) and [first survey tutorial](https://docs.expectedparrot.com/en/latest/starter_tutorial).
