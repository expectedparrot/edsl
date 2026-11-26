# EDSL agent setup by harness

EDSL ships task-specific, version-matched skills with the Python package. A
harness does not need a second copy of every EDSL skill. Install the small
`edsl-harness` routing skill; it teaches the agent to search and load only the
EDSL guidance that matches the current task, using the active package's `ep`
CLI.

## When someone pastes the README prompt into a running agent

Start with `ep skills show edsl-harness`. If it returns `status: ok`, use the guidance in that response and proceed to the user's task. After a terminal install, the launched agent already has the skill and the matching `ep` on its path.

If `ep` or its skill is missing, check the shared launcher at `"${XDG_DATA_HOME:-$HOME/.local/share}/edsl/harness-venv/bin/ep"`. If setup is needed, run the installer below for the named agent with `--setup user` and omit `--launch` inside an existing session. Use the shared executable for the rest of the session.

When setup succeeds, tell the user EDSL is ready. If they included a research task, continue with that task.

## Installing the agent from a terminal

Run the installer once for your agent. By default, the installer manages one copy of EDSL for your account and makes the skills available across projects. It creates a launcher at `~/.local/bin/ep` if that name is free. Include `~/.local/bin` on your shell’s PATH to run `ep` from any folder. Rerun the installer to update the shared copy.

Use `--setup` if you want to choose the installation scope explicitly.

| Choice | What the agent discovers | Where EDSL lives |
| --- | --- | --- |
| `--setup project` | All bundled skills, linked in this project's harness skill directory | `.edsl-venv` in this project |
| `--setup user` (default) | All bundled skills, linked in the harness's user skill directory | `$XDG_DATA_HOME/edsl/harness-venv`, defaulting to `~/.local/share/edsl/harness-venv` |
| `--setup router` | A copy of the single user skill `edsl-harness`, which looks up guidance with `ep` | The active virtual environment or the project's `.edsl-venv` |

For example, `bash harnesses/install.sh antigravity --setup project --launch` sets up the current project and opens Antigravity. It supports macOS, Linux, and WSL.

Linked skills track updates in their chosen environment. Rerun the same installer command after an upgrade to pick up new or retired skills, then start a fresh agent session. If a destination already holds a copy or a link to another environment, the installer identifies the conflict. Move the conflicting entries outside the discovery directory before retrying. Older user-level copies may also appear alongside project skills.

The installer authenticates EDSL with Expected Parrot when needed. This is
separate from model-provider credentials: direct inference with a provider
requires that provider's key, while Expected Parrot account access can be used
for available models. See [Managing Keys](https://docs.expectedparrot.com/en/latest/api_keys)
for credential setup. The installer does not configure model-provider keys.

The Pi installer also registers a survey preview tool. Ask Pi to “show me the updated survey” after an edit. Pi passes the saved survey to EDSL and renders the resulting Markdown in the conversation. The preview completes that turn. For a long survey you can ask for a page, for example “show me the first five questions.” If Pi is already running when you install the extension, use `/reload` to load it.

To install and launch Pi from a local checkout:

```bash
bash harnesses/install.sh pi --launch
```

Replace `pi` with a name from the table below. To run the script without
cloning EDSL:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

User skill directories are listed below. Harness conventions can change; check the
linked setup guide if the target does not discover the skill.

| Harness | Script name | Suggested skill directory | Setup guide |
| --- | --- | --- | --- |
| Codex | `codex` | `~/.agents/skills` | [EP Agent Codex guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/codex) |
| Claude Code | `claude-code` | `~/.claude/skills` | [EP Agent Claude Code guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/claude-code) |
| OpenCode | `opencode` | `~/.config/opencode/skills` | [EP Agent OpenCode guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/opencode) |
| Pi | `pi` | `~/.pi/agent/skills` | [EP Agent Pi guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/pi) |
| Antigravity CLI | `antigravity` | `~/.gemini/config/skills` | [EP Agent Antigravity guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/antigravity) |
| Vercel fx | `fx` | `~/.fx/skills` | [EP Agent fx guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/fx) |
| Meta Muse Code | `muse` | `~/.agents/skills` | [Muse Code](https://dev.meta.ai/products/muse-code) · [Skill discovery](https://dev.meta.ai/docs/muse-code/extending) |
| Mistral Vibe | `vibe` | `~/.agents/skills` | [Vibe setup](https://docs.mistral.ai/vibe/code/cli) · [Skill discovery](https://docs.mistral.ai/vibe/code/cli/skills) |
| GitHub Copilot CLI | `copilot` | `~/.agents/skills` | [Copilot CLI skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| Cursor | `cursor` | `~/.cursor/skills` | [Cursor skills](https://cursor.com/docs/skills) |
| Amp | `amp` | `~/.agents/skills` | [Amp skills](https://ampcode.com/docs/customize/skills) |
| Kiro CLI | `kiro` | `~/.kiro/skills` | [Kiro skills](https://kiro.dev/docs/cli/skills/) |
| Cline | `cline` | `~/.cline/skills` | [Cline skills](https://docs.cline.bot/customization/skills) |

Muse Code and Vibe also discover project skills in `.agents/skills` after you trust the project directory.

If the harness accepts project instructions, add a short pointer such as:

> For EDSL tasks, use the `edsl-harness` skill. It routes you to the installed
> EDSL version's relevant skills and package guidance.

With router setup, rerun the installer to refresh the routing skill. With fx, a linked skill outside its trusted directories may require configuring a skill symlink authority. See the [fx troubleshooting guide](https://fx.sh/docs/using-fx/troubleshooting).

## Amp, Kiro CLI, and Cline

### Amp

Paste into Amp:

```text
Run `ep skills show edsl-harness` and follow its guidance. If the command or skill is missing, use https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Amp.
```

To install and launch from your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- amp --launch
```

### Kiro CLI

Paste into Kiro CLI:

```text
Run `ep skills show edsl-harness` and follow its guidance. If the command or skill is missing, use https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Kiro CLI.
```

To install and launch from your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- kiro --launch
```

### Cline

Paste into Cline:

```text
Run `ep skills show edsl-harness` and follow its guidance. If the command or skill is missing, use https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/README.md to set up EDSL for Cline.
```

To install and launch from your terminal, with npm installed:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- cline --launch
```

## Project layout

The `edsl-harness` skill gives a conservative starting layout for new EDSL work
and points to the more specific `edsl-study-files` skill. For a larger research
workflow, use the relevant package's scaffold and conventions instead. Start
by inspecting the workspace and preserve its existing organization.

## Package discovery

When the task calls for a method-specific tool, use the [Expected Parrot
package directory](https://github.com/expectedparrot/directory) to discover
candidate packages. Then read the chosen package's own README and bundled agent
guidance. Use its documented installation and commands; the directory itself
is a catalog.
