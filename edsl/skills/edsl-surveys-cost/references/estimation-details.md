# Cost-estimation details

## Contents

- Output-token rules
- Input and file tokens
- Warnings and unsupported media
- Reasoning-model estimates

## Output-token rules

Output is answer, comment, and thinking tokens. Compute/functional questions
are not billable but can contribute memory. Free-text-like questions default
to output near prompt length; interview uses a larger fixed allowance; thinking
scales with prompt length. Structured questions estimate answer length from
options plus comment allowance. Matrix questions scale by rows; demand scales
by price points. Unknown types fall back to prompt-length output and warn.

## Input and file tokens

Input includes prompts, provider-specific file tokens, and prior-answer memory.
The generated Markdown estimate contains per-question/model formulas and file
components; use it for detailed review.

## Warnings and unsupported media

Warnings identify approximations, not necessarily errors. Missing branch
weights imply a worst-case all-questions path. Offloaded files may use default
page counts. Unsupported audio/video can contribute zero unless manually
overridden. Image-generation fallback is only a text-token guess; price image
generation separately using the selected model's reported rates.

## Reasoning-model estimates

`ep jobs cost` can return `estimate_kind="lower_bound"` when reasoning tokens are
not accounted for in the server point estimate. Inspect `warnings` and
`assumptions.reasoning_tokens`, including models attached to individual thinking
questions. Report known USD/credit values, the lower-bound status, and missing
bounds together. If the server supplies expected/upper values, preserve them.

Do not equate `credits_hold` with a guaranteed total charge. A `null` bound is
unknown. Existing pilot results can help calibrate uncertainty when available.
