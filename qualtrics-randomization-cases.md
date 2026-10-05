# Qualtrics Randomization Cases

2026-10-04 · Rae

Qualtrics can randomize at four levels: the order of whole sections, the questions inside a section, repeated "loop" sections, and the answer choices of a question. At each level it can shuffle everything, show only some of the items, and balance what respondents see. This doc goes through each case and shows how to do it with EDSL today and with the `Survey.flow` spec.

Syntax marked **(proposed)** isn't in the spec yet.

## The spec's building blocks

The survey's questions are kept in one fixed order, and each question keeps its name. A separate **flow** describes what each respondent actually sees: which pages, in what order, with what content. EDSL works out a concrete version of the flow for each respondent when the interview starts. Because the questions never change name, `answer.trust` is the same column for everyone, whatever order they saw it in.

The flow is built from five pieces. Each one lists its parameters below; ones marked **(proposed)** come up in the cases later in this doc and aren't in the spec yet.

### `Page`

One screen of questions. A page points to a question group (`survey.add_question_group(...)`) by the group's name.

```python
Page("consent")            # shows the questions in the "consent" group
```

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `name` | name of a question group | required | The group whose questions appear on this page, in their fixed order. |
| `scenario` | a `Draw` | none | Fills the page with a randomly picked scenario row, which its questions see as `{{ scenario.* }}`. See case 14. |
| `shuffle` **(proposed)** | `True` / `False` | `False` | Shows the group's questions in random order on the same page. See case 10 and the open questions. |
| `sample` **(proposed)** | whole number, 1 to the group's size | none (show all) | Shows only this many of the group's questions, chosen at random, on the same page. See case 11 and the open questions. |

### `Block`

A named list of pages (or other pieces) that are shown in the order written. It keeps things together, so a shuffle moves the whole block as one unit.

```python
Block("task", Page("intro"), Page("task_1"), Page("task_2"))
```

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `name` | any string | required | A label for the block. |
| `*children` | `Page`, `Block`, `Shuffle`, `Sample` | required | The pieces to show, in the order written. |

### `Shuffle`

Shows all its pieces in a random order. It only moves its own direct pieces, so the pages inside a block stay in that block.

```python
Shuffle(Page("a"), Page("b"), Page("c"))              # [b] [a] [c], [c] [b] [a], …
```

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `*children` | `Page`, `Block`, `Shuffle`, `Sample` | required | The pieces to shuffle. Each child moves as one unit. |
| `attach` | a `Page` of extra questions | none | Adds that page's questions to one randomly chosen child, on the same screen. The children must be `Page`s. See case 9. |

### `Sample`

Shows only `k` of its pieces, chosen at random. Pieces that aren't chosen show up in the results as empty answers.

```python
Sample(Page("a"), Page("b"), Page("c"), k=1)          # [b], or [a], or [c]
```

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `*children` | `Page`, `Block`, `Shuffle`, `Sample` | required | The pool to choose from. |
| `k` | whole number, 1 to the number of children | required | How many children each respondent sees. `k=1` assigns one condition (case 7). |
| `order` **(proposed)** | `"random"`, `"written"` | not yet decided | Whether the chosen children appear in random order (as in Qualtrics) or in the order written. See case 2. |
| `assignment` **(proposed)** | `"random"`, `"balanced"` | `"random"` | How each respondent's children are picked. `"random"` picks independently. `"balanced"` gives each new respondent the least-shown children, so every child is shown about equally often. See case 3. |

### `Draw`

Fills a page with one row picked at random from a `ScenarioList`. The page's questions see that row as `{{ scenario.* }}`. Each page draws on its own.

```python
Page("profile", scenario=Draw(profiles))              # a different profile per respondent
```

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `scenarios` | a `ScenarioList` | required | The rows to draw from. |
| `k` **(proposed)** | whole number, 1 to the number of rows | `1` | Draws this many rows and shows one copy of the page for each, named with the loop naming (`profile_q1__loop0__…`). See case 14. |

Because a `Draw` holds its whole `ScenarioList`, the rows are saved inside the survey. Whether that's the right place is an open question.

### Putting them together

The pieces nest inside each other, and a whole flow is usually one `Block`:

```python
survey.flow = Block("main",
    Page("consent"),
    Shuffle(
        Block("task", Page("intro"), Page("task_1"), Page("task_2")),
        Page("opinions"),
    ),
    Page("demographics"),
)
```

A survey with no flow behaves as it does today: every page, in the fixed order.

## Sections in the survey flow

A section is one piece of the flow: a `Page` (one question group) or a `Block` (several question groups shown together). The examples mostly use single pages to keep them short; any of them could be a `Block`.

### 1. Shuffle all sections

**What it does.** Every respondent sees all the sections, in a random order.

```
Sections:  [A Media: 2 pages] [B Shopping] [C Politics]

R1:  [C] [A1 A2] [B]
R2:  [B] [C] [A1 A2]
```

**Today:** not possible. Survey rules can only jump forward. The workaround is to build one survey per order and split respondents between them.

**With the spec:**

```python
Shuffle(
    Block("media", Page("media_1"), Page("media_2")),
    Page("shopping"),
    Page("politics"),
)
```

### 2. Show 2 of 5 sections

**What it does.** Each respondent sees only some of the sections, chosen at random. Qualtrics also shows the chosen ones in random order.

```
Sections:  [A] [B] [C] [D] [E]

R1:  [D] [A]
R2:  [B] [E]
R3:  [E] [B]
```

**Today:** not possible.

**With the spec:**

```python
Sample(Page("a"), Page("b"), Page("c"), Page("d"), Page("e"), k=2)
```

Sections that aren't chosen show up in the results as empty answers. The spec doesn't say what order the chosen sections come in. Qualtrics shows them in random order, so `Sample` should too, or take an option **(proposed)**: `Sample(..., k=2, order="random")`.

### 3. Evenly present

**What it does.** This is an option on any Qualtrics randomizer. Without it, each respondent's pick is independent, so some sections get shown more than others by chance. With it, Qualtrics keeps a count and gives each new respondent the least-shown option. It only matters when a randomizer shows some of its elements: if it shows all of them, every element is already shown to everyone.

```
2 of 5 sections, 100 respondents (200 showings)

Not even:  A 47   B 36   C 41   D 44   E 32
Even:      A 40   B 40   C 40   D 40   E 40
```

**Today:** the only way to balance is to build the assignments yourself in a design list (one row per respondent) and hand the rows out in order. For Humanize, that's `scenario_list_method="ordered"`.

**With the spec (proposed):** an `assignment` option on `Sample`.

```python
Sample(Page("a"), Page("b"), Page("c"), Page("d"), Page("e"), k=2, assignment="balanced")
```

`"balanced"` evens out how often each child is shown. `Shuffle` doesn't take it, since a shuffle shows every child to everyone, the same as a Qualtrics randomizer that shows all its elements.

LLM runs can balance exactly, because the number of interviews is known up front. Humanize would need to keep a running count on the server, as Qualtrics does.

`assignment` is a named option rather than a `True`/`False` flag so it can take more values later without changing saved surveys. In the saved form it's always an object, e.g. `{"assignment": {"type": "balanced"}}`. Possible later values:

- `Weighted(ad_a=0.7, ad_b=0.3)`: unequal probabilities, still drawn independently for each respondent.
- `Quota(ad_a=50, ad_b=50)`: hard targets. This needs a running count, and a decision on what happens once a target is met (stop assigning that option, or end the survey for anyone who would have landed there).
- A Latin square, which would add `assignment` to `Shuffle`: evens out how often each page appears in each position. Qualtrics doesn't offer this.

### 4. Keep sections together

**What it does.** A Qualtrics "Group" bundles several sections, so a randomizer moves them as one unit.

```
Shuffle these:  [Intro + Task 1 + Task 2]  [Attention check]  [Opinions]

R1:  [Opinions] [Intro Task1 Task2] [Attention check]
R2:  [Attention check] [Opinions] [Intro Task1 Task2]
```

The three pages inside the bundle always stay together, in their own order.

**With the spec:** a `Block`.

```python
Shuffle(
    Block("task", Page("intro"), Page("task_1"), Page("task_2")),
    Page("attention"),
    Page("opinions"),
)
```

### 5. Randomizers inside randomizers

**What it does.** A shuffled section can have its own shuffled contents.

```
Shuffle:  [Task section]  [Opinions]
Task section = [Intro] then shuffle [T1] [T2] [T3]

R1:  [Opinions] [Intro] [T3] [T1] [T2]
R2:  [Intro] [T2] [T3] [T1] [Opinions]
```

**With the spec:**

```python
Shuffle(
    Block("task", Page("intro"), Shuffle(Page("t1"), Page("t2"), Page("t3"))),
    Page("opinions"),
)
```

`Shuffle` only moves its own direct children, so T1–T3 never leave the task section.

### 6. Fixed start, random middle, fixed end

**What it does.** Some sections always come first or last, and the ones in between are shuffled.

```
[Consent] → shuffle [A] [B] [C] → [Demographics]
```

**With the spec:**

```python
Block("main",
    Page("consent"),
    Shuffle(Page("a"), Page("b"), Page("c")),
    Page("demographics"),
)
```

### 7. Assign each respondent to one condition

**What it does.** Between-subjects designs: each respondent sees exactly one version of a section, for example one of two ads.

```
Conditions:  [Ad A] [Ad B]

R1:  [Ad A]
R2:  [Ad B]
```

**Today:** put all conditions in the survey, pick one with a compute question, and skip the others.

```python
QuestionCompute(question_name="condition", question_text="{{ ['ad_a', 'ad_b'] | random }}")
survey.add_skip_rule("ad_a_rating", "{{ condition.answer }} != 'ad_a'")
survey.add_skip_rule("ad_b_rating", "{{ condition.answer }} != 'ad_b'")
```

**With the spec:** a `Sample` of one.

```python
Sample(Page("ad_a"), Page("ad_b"), k=1, assignment="balanced")   # assignment is proposed
```

The spec version needs no skip rules, and it can be balanced.

### 8. Assign a random value to use later

**What it does.** Qualtrics can put a random value into a variable, such as a price level or a condition label. Later questions show it in their text, or show or hide questions based on it.

```
price = one of $5, $10, $20

R1:  "Would you buy this for $10?"
R2:  "Would you buy this for $5?"
```

**Today:** a compute question. Later questions pipe its answer or use it in skip rules.

```python
QuestionCompute(question_name="price", question_text="{{ [5, 10, 20] | random }}")
QuestionYesNo(question_name="buy", question_text="Would you buy this for ${{ price.answer }}?")
```

**With the spec:** the same. The compute question just has to stay ahead of anything shuffled that uses its value.

To balance it, put the values in a design list instead (`{{ scenario.price }}`) and hand the rows out in order.

### 9. Add extra questions to one random page

**What it does.** Several pages share the same layout, and exactly one of them, chosen at random, also asks a couple of extra questions. In Qualtrics this is done with case 8: a randomizer puts one page's name into a variable, and the extra questions on every page are shown only if the variable matches that page.

```
Pages: [Product 1] [Product 2] [Product 3] [Product 4]
Extra questions: "What influenced your rating?", "Which feature did this product have?"

R1:  [Product 1] [Product 2 + extras] [Product 3] [Product 4]
R2:  [Product 1] [Product 2] [Product 3] [Product 4 + extras]
```

**Today:** a compute question picks the page, and skip rules hide the extras on every other page. Each page has its own copy of the extra questions.

```python
PRODUCTS = ["p1", "p2", "p3", "p4"]
QuestionCompute(question_name="extras_on", question_text="{{ " + repr(PRODUCTS) + " | random }}")
for p in PRODUCTS:
    survey.add_skip_rule(f"{p}_influence", "{{ extras_on.answer }} != " + repr(p))
    survey.add_skip_rule(f"{p}_feature",   "{{ extras_on.answer }} != " + repr(p))
```

Results show which page got the extras (`answer.extras_on`), and the extra answers stay separate by page (`p2_influence`, …), filled for only one.

**With the spec:** the same. The compute question just has to stay ahead of the pages.

The spec also has an `attach` option on `Shuffle`, which adds a group of extra questions to one randomly chosen page:

```python
Shuffle(
    *[Page(f"product_{p}", scenario=Draw(products[p])) for p in PRODUCTS],
    attach=Page("extras"),   # "extras" group: influence, feature
)
```

```
R1:  [Product 3] [Product 1 + extras] [Product 4] [Product 2]
R2:  [Product 2] [Product 4] [Product 3] [Product 1 + extras]
```

The extras appear on the same screen as the chosen product, so they see that page's drawn row: "Which feature did this product have?" can use `{{ scenario.* }}` like the page's own questions. This needs one copy of the extra questions and no skip rules, and results get one set of columns (`answer.influence`, `answer.feature`). A few details aren't settled yet (see the open questions).

To put the extras on their own screen instead, use the compute approach above, with the extras on a separate page after each product and the whole page skipped unless it's the chosen one.

## Questions within a section

These are Qualtrics' block-level "question randomization" options. Turning any of them on makes Qualtrics ignore the block's page breaks and skip logic: the whole block is shown on one screen (unless Advanced Randomization sets questions per page), and skip logic inside the block doesn't apply.

### 10. Shuffle the questions in a section

**What it does.** The questions in a section appear in random order.

```
Section: [Q1 Trust] [Q2 Fairness] [Q3 Competence]

R1:  Q3, Q1, Q2
R2:  Q2, Q3, Q1
```

Qualtrics shows all of them on one screen.

**With the spec, all on one page (what Qualtrics does):** not covered. `Page` shows a group in its fixed order. Proposed: `Page("battery", shuffle=True)`, or `Shuffle` inside a page (see the open questions).

**With the spec, one question per page:** make each question its own page and shuffle the pages. Qualtrics can't do this layout with its basic option.

```python
Shuffle(Page("trust"), Page("fairness"), Page("competence"))
```

### 11. Show k of n questions

**What it does.** Each respondent answers only some of the questions in a section, chosen at random. Qualtrics' basic option ("Present only N of total questions") shows them on one screen and can't balance. Balancing needs Advanced Randomization's Random subset with "Evenly display questions" (case 12).

```
Pool: [Q1] [Q2] [Q3] [Q4] [Q5] [Q6]   show 2

R1:  Q4, Q1
R2:  Q2, Q6
```

**With the spec, all on one page (what Qualtrics does):** not covered. Proposed: `Page("battery", sample=2)`, or `Sample` inside a page (see the open questions).

**With the spec, one question per page:** this layout can also be balanced.

```python
Sample(*[Page(f"item_{i}") for i in range(1, 7)], k=2, assignment="balanced")
```

### 12. Mix fixed, shuffled, and sampled questions

**What it does.** Qualtrics' "Advanced Randomization" sorts a section's questions into four lists: fixed, shuffled ("Randomize questions"), a random subset, and excluded.

```
Q1 always first · Q2–Q4 shuffled · 2 of Q5–Q8 · Q9 never shown

R1:  Q1, Q3, Q2, Q4, Q7, Q5
R2:  Q1, Q4, Q3, Q2, Q6, Q8
```

**With the spec:** combine the building blocks. Each `Page` here is a question group holding a single question, so every question gets its own screen. An excluded question just doesn't get a page.

```python
Block("section",
    Page("q1"),
    Shuffle(Page("q2"), Page("q3"), Page("q4")),
    Sample(Page("q5"), Page("q6"), Page("q7"), Page("q8"), k=2),
)
```

**Not covered: fixed questions between shuffled ones.** Each shuffled question leaves a `{Randomized}` marker in the fixed list, and the markers can be moved independently, so fixed questions can sit between them. For example, A, B and C are shuffled, but the attention check Q5 is always third:

```
Fixed list:  Q1, {Randomized}, Q5, {Randomized}, {Randomized}

R1:  Q1, B, Q5, C, A
R2:  Q1, A, Q5, B, C
```

The spec can't express this. A `Shuffle` keeps its children next to each other: `Page("q1"), Shuffle(A, B, C), Page("q5")` puts Q5 last, and `Shuffle(A), Page("q5"), Shuffle(B, C)` never moves A out of second place.

**Not covered: Questions per Page.** Qualtrics shuffles first and then cuts the result into pages of N questions, overriding the block's page breaks. With 2 per page:

```
R1:  [C, A]  [F, B]  [D, E]
R2:  [B, E]  [A, D]  [F, C]
```

In the spec, pages are question groups with fixed members, decided before anything is shuffled. For six questions A–F, the closest options are one group of all six (one screen), six groups of one (six screens), or three groups of two (C and D always together). This would need pages cut after the shuffle, something like `Block("section", Shuffle(...), per_page=2)` **(proposed)**. Both gaps are in the open questions.

## Loop & Merge

Loop & Merge repeats one section once per row of a table, filling the row's values into the questions. For example, it can ask the same 3 questions about each of 5 brands.

### 13. Loop over every row, in random order

**What it does.** Every respondent sees every row, in a random order.

```
Rows: Acme, Globex, Initech

R1:  [Rate Globex] [Rate Acme] [Rate Initech]
R2:  [Rate Initech] [Rate Globex] [Rate Acme]
```

**Today:** `Question.loop` makes one copy of the questions for each row, in a fixed order.

```python
brands = ScenarioList.from_list("brand", ["Acme", "Globex", "Initech"])
questions = QuestionLinearScale(
    question_name="rate_{{ brand }}",
    question_text="How much do you trust {{ brand }}?",
    question_options=[1, 2, 3, 4, 5],
).loop(brands)
```

**With the spec:** put each copy on its own page and shuffle the pages.

```python
Shuffle(*[Page(f"rate_{b}") for b in ["Acme", "Globex", "Initech"]])
```

Answers keep one column per brand (`answer.rate_Acme`, …), whatever the order.

### 14. Show only some of the rows

**What it does.** Qualtrics' "present only N of total loops". Each respondent sees a random N rows.

```
Rows: 15 example profiles   show 1

R1:  [Profile #7]
R2:  [Profile #12]
```

**Today:** make a design list with one row per respondent that already holds that respondent's pick, and pipe `{{ scenario.profile }}`.

**With the spec:** `Draw` on the page.

```python
Page("profile", scenario=Draw(profiles))   # 1 of 15, page text uses {{ scenario.profile }}
```

To show several rows, e.g. 3 of 15, each as its own copy of the page: **(proposed)** `Draw(profiles, k=3)`. It would reuse the existing loop naming, `profile_q1__loop0__…`.

**Several pages, each drawing on its own.** A common setup has several pages that each draw from their own list: for example, 10 product categories, each with 15 example products, and every category page shows one product.

```
R1:  [Phones: #7] [Laptops: #3] [Tablets: #11] …
R2:  [Phones: #12] [Laptops: #3] [Tablets: #1] …
```

With 10 pages of 15, that's 15¹⁰ ≈ 577 billion combinations. Neither Qualtrics nor the spec lists them: each page just makes its own pick.

- **Today:** a design list with one row per respondent, holding all 10 picks (`phones_product`, `laptops_product`, …). You need as many rows as respondents, not 577 billion.
- **With the spec:** one `Draw` per page, usually inside a `Shuffle` so the categories also come in random order.

```python
Shuffle(*[Page(c, scenario=Draw(products[c])) for c in CATEGORIES])
```

With `Loop & Merge` in the spec's terms:

- **All rows, random order** (case 13): `loop` + `Shuffle`
- **k rows** (case 14): `Draw(k=…)`

### 15. Loop over a respondent's own answers

**What it does.** Qualtrics' question-based looping. The loop rows are whatever the respondent picked earlier, e.g. "Which brands do you use?", then the same questions for each brand they chose. It can be randomized like the other loops.

**Today:** `Survey.loop_over`, in a fixed order.

```python
survey = Survey([used]).loop_over("used", ask=[rate, recommend], max_items=5)
```

**With the spec:** not covered. The rows aren't known until the respondent answers, so the flow can't shuffle them ahead of time. Shuffling a respondent's answers would need a random order computed at that point in the interview.

## Answer choices

These are Qualtrics' per-question "choice randomization" options.

### 16. Shuffle the choices

**What it does.** A question's answer choices appear in random order.

```
Choices: Coffee, Tea, Juice, Water

R1:  Juice, Coffee, Water, Tea
R2:  Tea, Water, Juice, Coffee
```

**Today:** already supported.

```python
Survey([q], questions_to_randomize=["drink"])
```

The order each respondent saw is recorded in the results.

### 17. Keep some choices fixed

**What it does.** Some choices, like "Other" or "None of these", stay in their place while the rest are shuffled.

```
Choices: Coffee, Tea, Juice, None of these

R1:  Juice, Coffee, Tea, None of these
R2:  Tea, Juice, Coffee, None of these
```

**Today:** already supported. A pinned choice keeps its original position.

```python
Survey([q], questions_to_randomize=["drink"], options_to_pin={"drink": ["None of these"]})
```

### 18. Show k of n choices

**What it does.** Each respondent sees only some of the choices, chosen at random.

```
Choices: A B C D E F   show 3

R1:  D, A, F
R2:  B, E, C
```

**Today and with the spec:** not covered. Proposed: an option next to `options_to_pin`, e.g. `options_to_sample={"drink": 3}`.

### 19. Flip the order of a scale

**What it does.** Half the respondents see the choices in reverse. This is common for agree/disagree scales, to balance out order effects without scrambling the scale.

```
Normal:   Strongly disagree … Strongly agree
Flipped:  Strongly agree … Strongly disagree
```

Qualtrics can also flip every scale the same way for a given respondent.

**Today and with the spec:** not covered. `questions_to_randomize` fully shuffles the choices, which breaks a scale. Proposed: `options_to_flip=["agree_1", "agree_2"]`, with one coin flip per respondent shared by every listed question.

### 20. Evenly present choices

**What it does.** When only some choices are shown (case 18), each choice gets shown about equally often.

**Today and with the spec:** not covered. It would come with case 18, using the same `assignment` option as the flow.

## Open questions

### Randomizing questions within one page

`Page(..., shuffle=True)` and `Page(..., sample=2)` (cases 10 and 11) add a second way to say "shuffle" and "sample", next to the `Shuffle` and `Sample` pieces. The alternative is to let those pieces take questions as children inside a page:

```python
Page("battery", Shuffle(Q("trust"), Q("fairness"), Q("competence")))
Page("battery", Q("q1"), Shuffle(Q("q2"), Q("q3"), Q("q4")), Sample(Q("q5"), Q("q6"), Q("q7"), Q("q8"), k=2))
```

This keeps one way of describing randomization at every level, and it covers case 12 on a single screen, which the flags can't. The costs:

- **Two places define a page's contents.** The question group lists its questions, and the page lists them again. Either the page's list replaces the group, or the two must match. See the next question.
- **More rules about what goes where.** A new `Q` piece is allowed only inside a page, and `Page`, `Block` and `Draw` aren't.
- **Humanize renders a per-respondent order within a page**, instead of a group's fixed order.
- **Results record question order within each page**, not just page order.

### Advanced Randomization gaps

Case 12 has two layouts the building blocks can't express:

1. **Fixed questions between shuffled ones.** A `Shuffle` keeps its children together, so there's no way to keep Q5 third while A, B and C shuffle around it. One option is a `Slot` marker, like Qualtrics' `{Randomized}` (proposed below). It's a new concept that overlaps with `Shuffle`, so it's worth checking how often real surveys need it before adding it. We also haven't checked whether Random subset leaves movable markers the same way.

2. **Questions per page.** Qualtrics paginates after shuffling. Supporting this means a block whose pages are cut after randomization, e.g. `Block("section", Shuffle(...), per_page=2)`, so a page is no longer always a question group. This ties into the next question.

#### Proposed: `Slot`

A placeholder inside a block. A block holds named **pools**, each a `Shuffle` or `Sample`. Each `Slot` is filled with the next piece drawn from its pool, in the order the slots appear, so fixed pieces can sit between the randomized ones. In the example, each `Page` is a question group holding a single question.

```python
Block("section",
    Page("q1"),
    Slot("shuffled"),
    Page("q5"),                       # always third
    Slot("shuffled"),
    Slot("shuffled"),
    Slot("subset"),
    Slot("subset"),
    pools={
        "shuffled": Shuffle(Page("a"), Page("b"), Page("c")),
        "subset":   Sample(Page("d"), Page("e"), Page("f"), Page("g"), k=2),
    },
)
```

```
R1:  Q1, B, Q5, C, A, F, D
R2:  Q1, A, Q5, B, C, E, G
```

This matches Qualtrics' dialog: the fixed list is the block's pieces, each `{Randomized}` marker is a `Slot("shuffled")`, the Random subset is a `Sample` pool, and excluded questions are left out.

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `pool` | name of a pool on the enclosing `Block` | required | Which pool fills this slot. |

It adds one parameter to `Block`:

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `pools` | dict of name → `Shuffle` or `Sample` | none | The pools this block's slots draw from. A pool's pieces are shown only through its slots. |

Rules:

- **Slot count must match the pool.** A `Shuffle` pool needs one slot per child, and a `Sample` pool needs `k` slots. Anything else is an error, so no piece is silently dropped or left unfilled.
- **Slots fill in order.** The pool is drawn once per respondent, and its pieces go into its slots from top to bottom. A `Sample` pool's picks fill its slots in random order, as Qualtrics does.
- **Slots belong to their block.** A `Slot` must be a direct child of the block that defines its pool.
- **Pool pieces appear only in the pool.** A page inside a pool can't appear elsewhere in the flow.
- **Pools take the usual options.** `assignment="balanced"` on a `Sample` pool works as in case 3; it's Qualtrics' "Evenly display questions".

### Keeping the flow in sync with question groups

`Page("consent")` points to a question group by name, so the flow and the groups have to agree:

- **A renamed or dropped group** leaves a broken `Page` reference. Validation can catch this.
- **A group the flow never mentions.** Is it hidden, shown at the end, or an error?
- **Groups are index ranges** (`{name: (start, end)}`), so inserting or moving a question can quietly change what a group holds. The flow only knows the group's name, so it doesn't notice.

The bigger choice is whether the flow should point to groups at all:

- **Point to groups (as now).** Changes to a group's questions carry through to its page automatically, but the three questions above need answers.
- **The flow defines pages itself.** Each `Page` lists its questions, and `question_groups` isn't used for flow pages. There's one place that says what's on a page, and letting `Shuffle` and `Sample` take questions inside a page no longer duplicates anything. But existing grouped surveys, and Humanize's `presentation: "group"`, would need converting.

### Where `Draw`'s rows are stored

A `Draw` holds its whole `ScenarioList`, and the flow is saved as part of the survey, so the rows end up inside the serialized `Survey`. Today, scenarios live on the job (`survey.by(scenarios)`), not the survey. This has a few consequences:

- **Survey reuse.** You can't swap in a different set of profiles without editing the survey.
- **Size.** Any files in the rows (images, PDFs) get embedded in the survey and shipped with it to Humanize.
- **Two scenario sources.** The job's scenarios and the page's draw both fill `{{ scenario.* }}`, so one has to be namespaced or take priority.

The alternative is a new `scenario_list_method="per_page"` on the job, which keeps the lists on the job and has the survey store only which page draws from which list.

### Details of `attach`

Case 9's `attach=Page("extras")` leaves three things open:

1. **The chosen page no longer matches its group.** It shows its own group's questions plus the extras, so a page's contents aren't fixed by its group alone. See the question above about keeping the flow in sync with question groups.
2. **Balancing.** `attach` takes a `Page`, so there's nowhere to put `assignment="balanced"`, and the pick is always random. It could take a wrapper instead: `attach=Attach(Page("extras"), assignment="balanced")`.
3. **Results.** Which page got the extras needs a column, e.g. `flow.attached.extras = "product_2"`. Analyzing answers by product means joining on it.

## Summary

| # | Case | Today | With the spec |
| --- | --- | --- | --- |
| 1 | Shuffle all sections | 1 survey per order | `Shuffle` |
| 2 | Show k of n sections | no | `Sample(k=…)` |
| 3 | Evenly present | build a balanced design list | `assignment="balanced"` (proposed) |
| 4 | Keep sections together | — | `Block` |
| 5 | Randomizers inside randomizers | no | nested `Shuffle` |
| 6 | Fixed start and end | yes (fixed order) | `Block` + `Shuffle` |
| 7 | One condition per respondent | compute + skip rules | `Sample(k=1)` |
| 8 | Random value used later | compute question | same |
| 9 | Extra questions on one random page | compute + skip rules | same |
| 10 | Shuffle questions | no | same page (Qualtrics' layout) proposed; `Shuffle` of pages |
| 11 | k of n questions | no | same page (Qualtrics' layout) proposed; `Sample` of pages |
| 12 | Mixed question slots | no | `Block` + `Shuffle` + `Sample`; fixed questions between shuffled ones and questions per page not covered |
| 13 | Loop all rows, random order | `loop` (fixed order) | `loop` + `Shuffle` |
| 14 | Loop only some rows, incl. one draw per page | design list | `Draw`; `k>1` proposed |
| 15 | Loop over answers | `loop_over` (fixed order) | not covered |
| 16 | Shuffle choices | `questions_to_randomize` | same |
| 17 | Pin choices | `options_to_pin` | same |
| 18 | k of n choices | no | proposed |
| 19 | Flip a scale | no | proposed |
| 20 | Evenly present choices | no | proposed |

## Example: the Applicant Evaluation Study

`Applicant_Evaluation_Study.qsf` uses five of the cases above. Everything it randomizes can be built with the spec's current pieces; it doesn't need `assignment`, `Slot`, or `per_page`.

```
[Consent] [Instructions] [Hiring experience]  →  shuffle [a] [b] [c]  →  [Demographics] [Wrap-up]

a = [Intro 1] [Intro 2] [Baseline] → shuffle [10 profile pages]
b = [Attention check]
c = [General beliefs]
```

Each page below is a question group. The 10 profile types are single misdemeanor, property misdemeanor, drug misdemeanor, violent misdemeanor, property felony, drug felony, violent felony, other felony, pending, and complex mixed record.

### Section order (cases 1 and 4)

**In the QSF:** a randomizer showing 3 of 3 elements. The first element is a Group, so the profile task's intro, baseline, and profile pages move together.

```
R1:  [c Beliefs] [a Profiles] [b Attention]
R2:  [b Attention] [c Beliefs] [a Profiles]
```

**With the spec:**

```python
Shuffle(
    Block("a", Page("intro_1"), Page("intro_2"), Page("baseline"), profile_pages),
    Block("b", Page("attention")),
    Block("c", Page("general_beliefs")),
)
```

### Profile page order (case 5)

**In the QSF:** a randomizer showing 10 of 10 profile blocks, inside the Group after the intro and baseline.

```
R1:  [Intro 1] [Intro 2] [Baseline] [Drug felony] [Pending] [Single misd.] …
R2:  [Intro 1] [Intro 2] [Baseline] [Property misd.] [Complex] [Drug misd.] …
```

**With the spec:**

```python
profile_pages = Shuffle(*[Page(t, scenario=Draw(records[t])) for t in TYPES])
```

### One of 15 records per page (case 14)

**In the QSF:** each profile block has Loop & Merge with 15 rows (a record ID and the record's HTML table), set to show 1. Each page picks on its own.

```
R1:  [Single misd.: #7] [Drug felony: #3] …
R2:  [Single misd.: #12] [Drug felony: #3] …
```

**With the spec:** a `Draw` on each profile page (shown above). The page text uses `{{ scenario.record }}`. The 150 records end up stored inside the survey; see "Where `Draw`'s rows are stored" in the open questions.

### Follow-ups on one random profile page (case 9)

**In the QSF:** two follow-up questions are on every profile page, hidden by display logic unless an embedded data field, `profile_check_pool`, matches that page. A randomizer before the sections sets the field.

- "Which issue, if any, most influenced your recommendation…?"
- "According to the profile you just reviewed, did the applicant have any felony charges?"

```
R1:  … [Drug felony] [Pending + follow-ups] [Single misd.] …
R2:  … [Drug felony + follow-ups] [Pending] [Single misd.] …
```

**With the spec:** `attach` on the profile shuffle. The follow-ups appear on the chosen page and see its drawn record, which the felony-charges question needs.

```python
profile_pages = Shuffle(
    *[Page(t, scenario=Draw(records[t])) for t in TYPES],
    attach=Page("followups"),   # influence, felony_check
)
```

The compute approach also works, and mirrors the QSF directly: a compute question picks the type, and skip rules hide each page's copy of the follow-ups on the other 9 pages.

### Answer choices (cases 16 and 17)

**In the QSF:** five multiple-choice questions shuffle their choices and keep the last two in place: industry ("Unclassified establishments", "Other services"), the two "why background checks" questions ("Other", "Unsure"), and the two "most predictive features" questions ("None of these…", "Unsure").

**With the spec:** today's options.

```python
Survey(questions,
    questions_to_randomize=["industry", "why_checks_own", "why_checks_others", "predict_good", "predict_poor"],
    options_to_pin={
        "industry": ["Unclassified establishments", "Other services (except public administration)"],
        "why_checks_own": ["Other", "Unsure"],
        # … same for the other three
    },
)
```

### Everything together

```python
survey.flow = Block("main",
    Page("consent"), Page("instructions"), Page("hiring_1"), Page("hiring_2"),
    Shuffle(
        Block("a",
            Page("intro_1"), Page("intro_2"), Page("baseline"),
            Shuffle(
                *[Page(t, scenario=Draw(records[t])) for t in TYPES],
                attach=Page("followups"),
            ),
        ),
        Block("b", Page("attention")),
        Block("c", Page("general_beliefs")),
    ),
    Page("demographics"), Page("wrap_up"),
)
```

### Notes

- **Nothing is balanced.** Both the section and profile randomizers have "Evenly Present" on, but each shows all its elements, so the setting has no effect (case 3). The follow-up randomizer doesn't have it on.
- **The follow-up pick works by accident.** Its randomizer is set to show 10 of its 10 elements, each of which sets `profile_check_pool`. All 10 run in random order and the last one wins, which is still a uniformly random pick. "Show 1 of 10" was probably intended.
- **Display logic on General Beliefs** depends on a Hiring Experience question ("Did the firm or organization ever perform criminal background checks…"). That question is fixed and always comes before the shuffled sections, so ordinary skip rules work.
- **The glossary** uses custom JavaScript and embedded data fields. It isn't randomization, so it's left out here.

Sources: [Randomizer](https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/randomizer/), [Question Randomization](https://www.qualtrics.com/support/survey-platform/survey-module/block-options/question-randomization/), [Loop & Merge](https://www.qualtrics.com/support/survey-platform/survey-module/block-options/loop-and-merge/), [Choice Randomization](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/choice-randomization/)
