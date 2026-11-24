---
name: edsl-collections
description: Build, inspect, and publish EDSL Collections that group Expected Parrot objects by typed UUID reference.
tags: [edsl, collections, expected-parrot]
---

# EDSL Collections

Use this skill when someone wants to group, retrieve, or organize EDSL objects with a `Collection`.

A Collection is an ordered, metadata-only list of typed UUID references to objects stored on Expected Parrot. It does not contain member content, freeze a member version, or change member visibility or sharing permissions. Use `ep collections metadata` to resolve current metadata for members the authenticated account can access.

## Create and edit a local collection

Use the installed command help if a CLI option differs by version:

```bash
ep collections create --name "Study materials" --purpose "Survey and prompt for the study." --output study-materials.ep
ep collections add study-materials.ep "$SURVEY_UUID" --type survey
ep collections add study-materials.ep "$PROMPT_UUID" --type prompt
ep collections show study-materials.ep
ep collections metadata study-materials.ep
```

Set `SURVEY_UUID` and `PROMPT_UUID` to UUIDs returned by `ep push`, `ep clone`, or `ep metadata`. Supply each member's type with `--type`. The collection command records references only; it does not fetch member content.

To remove a reference, use `ep collections remove <collection.ep> <uuid> --type <type>`. To build a collection from search, use `ep collections from-search --help`; it creates a collection from one result page. Check pagination data and warnings. Use `ep search` and `ep collections add` to add results from other pages to that collection.

## Publish and retrieve

Collections are `.ep` packages and use the standard object commands:

```bash
ep push study-materials.ep --alias study-materials --description "Survey and prompt references for the study." --visibility private
ep clone "$COLLECTION_UUID" --path study-materials-copy.ep
ep pull study-materials-copy.ep
```

Set `COLLECTION_UUID` to the UUID returned by `ep push`. Collections can also be cloned by owner and alias or by URL.

Visibility applies to the collection object only. A public collection can contain a reference to a private object, but that reference does not grant access to the private object's contents. For visibility, alias, description, and sharing guidance, see `edsl:edsl-object-publishing`.

For the full CLI workflow and search example, see the Collections page in the EDSL documentation.
