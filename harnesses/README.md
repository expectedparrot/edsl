# EDSL agent setup by harness

EDSL ships task-specific, version-matched skills with the Python package. A
harness does not need a second copy of every EDSL skill. Install the small
`edsl-harness` routing skill; it teaches the agent to search and load only the
EDSL guidance that matches the current task, using the active package's `ep`
CLI.

## When someone pastes the README prompt into a running agent

1. Set up EDSL in the user's project. Use its Python environment, or create one with Python 3.10–3.13. Install or update the build that includes the harness skill using the environment's interpreter:

   ```bash
   python -m pip install --upgrade 'edsl @ git+https://github.com/expectedparrot/edsl.git@feat/edsl-harness-guidance'
   ```

   With uv, use `uv pip install --python /path/to/environment/bin/python --upgrade` with the same package argument.

2. Find the named agent in the skill directory table below. Run `ep skills install --target <directory> --skill edsl-harness` with that directory expanded to its full path. Then run `ep skills show edsl-harness` and follow the guidance in this session. Use the same environment for each command.
3. Create the survey the user asked for and save it as a local `.ep` package. Render it with `ep open survey.ep --output survey.html --no-browser` (substitute the actual filenames) and give the user a link to the HTML file. Creating this preview requires no Expected Parrot login or model-provider key. When the user asks for cloud work, check `ep auth status` and use `ep auth login` if a key is missing.

## Installing the agent from a terminal

Run the bootstrap script from the project directory. It installs the selected harness if missing, installs EDSL from the
current branch into the active Python environment (using uv when available,
otherwise pip), checks Expected Parrot authentication, and installs the
`edsl-harness` skill in that harness's user skill directory. Add `--launch` to
start the harness in the current directory after setup. Activate the Python
environment where EDSL should be installed first. uv installs into the
interpreter selected by `python3`. The bootstrap script supports macOS, Linux,
and WSL. On native Windows, install the harness from its official guide first,
then run the EDSL and skill setup steps in that environment.

The installer authenticates EDSL with Expected Parrot when needed. This is
separate from model-provider credentials: direct inference with a provider
requires that provider's key, while Expected Parrot account access can be used
for available models. See [Managing Keys](https://docs.expectedparrot.com/en/latest/api_keys)
for credential setup. The installer does not configure model-provider keys.

After installation, verify the CLI and skill catalog in the activated
environment, then restart the harness to load the new skill:

```bash
ep info
ep auth status
ep skills list --routing
ep skills search "survey" --snippets
```

To confirm the harness is using dynamic skill discovery, ask it to use
`edsl-harness` for an EDSL survey task, find the relevant task skill through
`ep skills`, and summarize the guidance. It should use the CLI catalog rather
than inspect Python package installation paths.

```bash
bash harnesses/install.sh pi --launch
```

Replace `pi` with a name from the table below. To run the script without
cloning EDSL:

```bash
curl -fsSL https://raw.githubusercontent.com/expectedparrot/edsl/feat/edsl-harness-guidance/harnesses/install.sh | bash -s -- pi --launch
```

The bootstrap installs the skill in the harness's user directory. Current
common targets are listed below. Harness conventions can change; check the
linked setup guide if the target does not discover the skill.

| Harness | Script name | Suggested skill directory | Setup guide |
| --- | --- | --- |
| Codex | `codex` | `~/.agents/skills` | [EP Agent Codex guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/codex) |
| Claude Code | `claude-code` | `~/.claude/skills` | [EP Agent Claude Code guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/claude-code) |
| OpenCode | `opencode` | `~/.config/opencode/skills` | [EP Agent OpenCode guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/opencode) |
| Pi | `pi` | `~/.pi/agent/skills` | [EP Agent Pi guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/pi) |
| Antigravity CLI | `antigravity` | `~/.gemini/config/skills` | [EP Agent Antigravity guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/antigravity) |
| Vercel fx | `fx` | `~/.fx/skills` | [EP Agent fx guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/fx) |

If the harness accepts project instructions, add a short pointer such as:

> For EDSL tasks, use the `edsl-harness` skill. It routes you to the installed
> EDSL version's relevant skills and package guidance.

Run the install commands from the active EDSL environment. After upgrading
EDSL, rerun the skill-install command to refresh `edsl-harness`. Other skills
remain available on demand through `ep skills search` and `ep skills show`;
they do not have to be installed into the harness.

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
