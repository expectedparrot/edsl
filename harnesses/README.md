# EDSL agent setup by harness

EDSL ships task-specific, version-matched skills with the Python package. A
harness does not need a second copy of every EDSL skill. Install the small
`edsl-harness` routing skill; it teaches the agent to search and load only the
EDSL guidance that matches the current task, using the active package's `ep`
CLI.

Run the install command from the environment where the target harness will run
EDSL commands. `--skill` is repeatable and leaves other EDSL skills out of the
harness directory:

```bash
ep skills install --target .agents/skills --skill edsl-harness
```

For user-wide installation, use the harness's user skill directory instead of
`.agents/skills`. Current common targets are listed below. Harness conventions
can change; check the linked setup guide if the target does not discover the
skill.

| Harness | Suggested skill directory | Setup guide |
| --- | --- | --- |
| Codex | `.agents/skills` or `~/.agents/skills` | [EP Agent Codex guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/codex) |
| Claude Code | `.claude/skills` or `~/.claude/skills` | [EP Agent Claude Code guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/claude-code) |
| OpenCode | `.agents/skills` or `~/.config/opencode/skills` | [EP Agent OpenCode guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/opencode) |
| Pi | `.agents/skills` or `~/.pi/agent/skills` | [EP Agent Pi guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/pi) |
| Antigravity CLI | `.agents/skills` or `~/.gemini/config/skills` | [EP Agent Antigravity guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/antigravity) |
| Vercel fx | `.agents/skills` or `~/.fx/skills` | [EP Agent fx guide](https://github.com/expectedparrot/ep-ra/tree/main/harnesses/fx) |

If the harness accepts project instructions, add a short pointer such as:

> For EDSL tasks, use the `edsl-harness` skill. It routes you to the installed
> EDSL version's relevant skills and package guidance.

Install or update the EDSL package first if `ep skills install` is unavailable.
After upgrading EDSL, rerun the command to refresh `edsl-harness`. Other skills
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
