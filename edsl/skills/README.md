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

Search by method with `ep skills search "best worst scaling"`. The JSON response
lists bundled skills under `data.results` and public companion packages under
`data.packages`. Each package includes method keywords, its repository and a
README link. `--limit` applies to each list. Search works offline using a
release snapshot. Search recognizes related English word forms, so `forecast`
finds `forecasting` and `coded interviews` finds `interview coding`. Multiword
queries can match in any order within a method, description, or skill passage.
To update a listing, edit `packages.json` in [expectedparrot/directory](https://github.com/expectedparrot/directory).
Its catalog sync workflow proposes the updated `edsl/skills/packages.json` in
an EDSL pull request. Users receive that snapshot in a release after it merges.
