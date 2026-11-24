---
name: edsl-human-survey-preview
description: Render an EDSL humanized survey locally with the optional Runway preview tool.
tags: [edsl, reference]
---

# EDSL human survey preview

The optional `runway` tool renders a saved EDSL survey and humanize schema as local HTML without deploying it. It can render question groups, scenarios, images, and custom CSS. Use `runway --help` for installed options and validate the survey/schema with EDSL before rendering.

A local preview shows layout and static content; it does not execute server-side dynamic behavior. See the [detailed preview guide](references/detailed-guide.md) for input files, commands, and limitations. Runway is an external preview utility, not part of the EDSL Python API.
