# EDSL Documentation

Learn to design surveys, run studies with AI or human participants, and analyze
responses in the [EDSL documentation](https://docs.expectedparrot.com).

- [Run your first survey](en/latest/starter_tutorial.mdx): build a survey and
  inspect local test responses without model credentials.
- [EDSL overview](en/latest/overview.mdx): understand questions, surveys, agents,
  scenarios, models, jobs, and results.
- [CLI guide](en/latest/cli.mdx): use EDSL from a terminal or coding agent.
- [Human studies](en/latest/guides/human_studies.mdx): collect participant responses.

## Canonical manuals

The complete shared-state and workflow manuals are maintained as Mintlify MDX
chapters. See [Canonical manuals](MANUALS.md) for their sources, navigation,
validation commands, and the status of older print snapshots.

## Local preview

Install the Mintlify CLI with `npm i -g mint`, then run `mint dev` from this
directory. The preview is served at `http://localhost:3000`.

Changes deploy automatically via the Mintlify GitHub app when merged to the
default branch.

The [Python examples](examples/) contain runnable study and analysis examples.
Examples using the test model demonstrate the workflow with fixed responses;
real model calls require configured access and may incur costs.
