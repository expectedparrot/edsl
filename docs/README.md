# EDSL Documentation

The EDSL documentation site, built with [Mintlify](https://mintlify.com/docs). Configuration lives in [`docs.json`](./docs.json); content is under `en/latest/` as `.mdx` files.

## Local preview

Install the Mintlify CLI:

```
npm i -g mint
```

Then, from this `docs/` directory (where `docs.json` lives):

```
mint dev
```

The preview is served at `http://localhost:3000`.

## Publishing

Changes deploy automatically via the Mintlify GitHub app once merged to the default branch. The app is configured to build from this `docs/` directory.

## Troubleshooting

- **Dev server won't start:** run `mint update` to get the latest CLI.
- **A page 404s:** confirm you're running from the folder containing `docs.json`, and that the page's path is listed in the `navigation` block.
