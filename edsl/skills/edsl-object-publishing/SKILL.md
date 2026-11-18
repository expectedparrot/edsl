---
name: edsl-object-publishing
description: Persist EDSL objects and use the EDSL CLI to push, inspect, share, update, and pull remote objects.
tags: [edsl, reference]
---

# EDSL object publishing and sharing

EDSL objects persist locally through their `.git.save(...)` interface. The CLI manages remote object lifecycle: `ep push` uploads an object, `ep metadata` inspects it, `ep update-metadata` changes metadata, `ep share` and `ep unshare` manage user access, and `ep pull` retrieves updates. Use `ep <command> --help` for exact flags and `ep auth status` to inspect authentication state.

`ep push` accepts an alias, description, and visibility. Visibility values are `private`, `unlisted`, and `public`; their effects are returned in command metadata. Pushing is a remote write. See [remote object commands](references/remote-object-commands.md) for common operations. This bundle documents the EDSL interface and object model; approval procedures and publishing decisions are EP Agent workflow policy.

Use installed CLI help for command details.
