# Canonical manuals

The complete shared-state and workflow manuals live in the Mintlify MDX pages,
not in separately maintained Markdown or PDF editions:

- [Shared-state manual](en/latest/shared_state.mdx), with chapters in
  `en/latest/shared-state/`.
- [Workflow manual](en/latest/workflows.mdx), with chapters in
  `en/latest/workflows/`.
- [Current execution contracts](en/latest/coordinated-research/execution-contracts.mdx).
- [Draft language specification](en/latest/shared-state/semantics.mdx), with
  sections in `en/latest/shared-state/semantics/`.

Edit these sources and keep their chapter navigation in `docs.json`. The former
manual Markdown paths are relocation notices to preserve incoming repository
links. Existing PDF/LaTeX files are historical snapshots; do not edit or rebuild
them as a competing manual. Any future print export must be generated from the
canonical MDX chapters. Prospective simulation/design studies are design material,
not API documentation or promises of supported behavior.

From this directory, use the Mintlify CLI to check and preview changes:

```sh
mint validate
mint broken-links
mint dev
```

The formal specification retains its schema and executable vectors under
`shared_state_semantics/`. Distinguish its draft conformance requirements from the
currently implemented guarantees documented in the execution contracts.
