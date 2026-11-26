# <img src="static/edsl-wordmark.svg" alt="EDSL" width="180" height="48">

With EDSL, you define surveys in Python, from a single poll to a study with the question formats and branching logic you might use in Qualtrics. The questions, response options, and rules live together in code you can review, version, and reuse.

Run the same survey across hundreds of AI models with one Expected Parrot API key, or use your own provider keys. EDSL caches model responses so you can reuse answers without paying for the same calls again.

Invite people to take the survey by URL or email, or set up an AI interviewer to ask follow-up questions based on what each participant says.

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

## Key features

| Feature | What you can do |
| --- | --- |
| Question types | Ask respondents to choose one or more options, rate items in a matrix, rank choices, allocate a budget, or enter a number or free-text answer. [Question catalog](https://docs.expectedparrot.com/en/latest/questions) |
| Survey logic | Branch or stop based on an answer, pipe it into a later question, or repeat a group of follow-ups for each item a respondent lists. [Survey logic guide](https://docs.expectedparrot.com/en/latest/guides/survey_logic) |
| Model comparison | Give several models the same survey and compare answers by model, scenario, or simulated persona. |
| Human surveys | Share a survey by URL or send email invitations and collect responses. |
| AI interviews | Give an AI interviewer a research question and let it ask participants follow-up questions. |
| Data labeling | Apply the same questions to each document, image, or row in a dataset. |
| Results | Filter answers, export them to CSV, and reuse cached model responses when repeating an analysis. |

For Python setup and a worked example, see the [installation guide](https://docs.expectedparrot.com/en/latest/installation) and [first survey tutorial](https://docs.expectedparrot.com/en/latest/starter_tutorial).
