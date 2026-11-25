# Bundled EDSL skills

Each immediate child directory is one installable skill bundle and contains a
`SKILL.md` plus any local references or scripts. References live in
`references/`; standalone helper scripts live in `scripts/` and must be linked
from that bundle's `SKILL.md`. Supported script types are Python, shell, and
JavaScript/TypeScript source files. These assets ship with this EDSL distribution
so guidance and examples can be maintained alongside the matching implementation.

Use `python -m edsl.skills.check_links` when editing bundles. Internal Markdown
and script links must resolve inside the bundle, and every bundled script must
be linked from its `SKILL.md`. Cross-skill links use `edsl:<name>`;
optional workflow or research links managed by EP Agent use
`ep-agent:<name>` and must be declared in `cross-references.json`.

`ep skills install --target <directory>` installs each complete bundle as a
child of the target directory, including its scripts. Repeat `--skill <name>`
to install only selected bundles; without it, all bundled skills are installed.
`ep skills show <name>`
returns the main file and every transitively linked local Markdown reference.
Fetch one reference with `ep skills show <name> --reference
references/<file>.md`; fetch a script's source with
`ep skills show <name> --script scripts/<file>`. Version-matched EDSL examples
are fetchable with `ep skills show <name> --example <path>` and listed by
`ep skills list --routing`. Search indexes skill references, scripts, and
assigned example source. The CLI returns code for inspection; it does not
execute bundled scripts or examples.
