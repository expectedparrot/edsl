# Two Truths and a Lie: LLM Storytelling Challenge

## Study Design Document

**Version**: 1.0.0  
**Last Updated**: 2026-01-16  
**Status**: MVP Design

---

## 1. Executive Summary

This study evaluates LLM capabilities in deception, truth-telling, and deception detection through a structured storytelling game inspired by the British game show "Why Would I Lie?" 

The core innovation is a **three-sided test** that measures:
1. **Judge Performance**: Can LLMs correctly identify fabricated stories?
2. **Fibber Performance**: Can LLMs successfully deceive other LLMs?
3. **Truth-Teller Performance**: Can LLMs tell strange-but-true stories without being falsely accused?

---

## 2. Research Questions

### Primary Questions
1. Which LLMs are best at detecting deception in narrative form?
2. Which LLMs are best at crafting believable fabrications?
3. Is it harder to lie convincingly or to tell a strange truth convincingly?

### Secondary Questions
4. Do theory-grounded storytelling strategies (level-k reasoning, source emphasis, detail specificity) outperform baseline approaches?
5. How do different fact categories (science, history, culture) affect detection difficulty?
6. Can LLM judges "break the frame" when given impossible tasks (e.g., all stories are true)?

### Exploratory Questions
7. Does judge temperature affect frame-breaking behavior?
8. What linguistic patterns distinguish successful lies from failed ones?
9. What questioning strategies correlate with successful detection?

---

## 3. Game Structure

### 3.1 Participants Per Round
- **3 Storytellers**: Each assigned a role (Truth-Teller or Fibber)
- **1 Judge**: Evaluates all three stories and identifies the Fibber

### 3.2 Standard Configuration
- 2 Truth-Tellers + 1 Fibber
- Judge believes: "One storyteller is lying"

### 3.3 Frame-Breaking Configurations
| Config ID | Truth-Tellers | Fibbers | Judge Belief | Purpose |
|-----------|---------------|---------|--------------|---------|
| `standard` | 2 | 1 | "1 liar" | Baseline game |
| `all_truth` | 3 | 0 | "1 liar" | Test forced-choice under impossible conditions |
| `all_lies` | 0 | 3 | "1 liar" | Test pattern recognition when all fabricate |
| `majority_lies` | 1 | 2 | "1 liar" | Harder detection variant |

### 3.4 Game Flow

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         ROUND START                              â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”              â”‚
â”‚  â”‚ Storyteller â”‚  â”‚ Storyteller â”‚  â”‚ Storyteller â”‚              â”‚
â”‚  â”‚     A       â”‚  â”‚     B       â”‚  â”‚     C       â”‚              â”‚
â”‚  â”‚ (Role: T/F) â”‚  â”‚ (Role: T/F) â”‚  â”‚ (Role: T/F) â”‚              â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜              â”‚
â”‚         â”‚                â”‚                â”‚                      â”‚
â”‚         â–¼                â–¼                â–¼                      â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚  â”‚           PHASE 1: STORY GENERATION             â”‚            â”‚
â”‚  â”‚  - Truth-Tellers: Select from fact database     â”‚            â”‚
â”‚  â”‚  - Fibber: Fabricate plausible story            â”‚            â”‚
â”‚  â”‚  - All use identical prompt structure           â”‚            â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                          â”‚                                       â”‚
â”‚                          â–¼                                       â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚  â”‚           PHASE 2: JUDGE REVIEWS STORIES        â”‚            â”‚
â”‚  â”‚  - Judge receives all 3 stories (randomized)    â”‚            â”‚
â”‚  â”‚  - No role information revealed                 â”‚            â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                          â”‚                                       â”‚
â”‚                          â–¼                                       â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚  â”‚           PHASE 3: Q&A SESSION                  â”‚            â”‚
â”‚  â”‚  - Judge asks 3 questions to EACH storyteller   â”‚            â”‚
â”‚  â”‚  - Storytellers respond in character            â”‚            â”‚
â”‚  â”‚  - 9 total Q&A exchanges per round              â”‚            â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                          â”‚                                       â”‚
â”‚                          â–¼                                       â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
â”‚  â”‚           PHASE 4: VERDICT                      â”‚            â”‚
â”‚  â”‚  - Judge identifies suspected Fibber            â”‚            â”‚
â”‚  â”‚  - Judge provides confidence score (1-10)       â”‚            â”‚
â”‚  â”‚  - Judge provides reasoning                     â”‚            â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
â”‚                          â”‚                                       â”‚
â”‚                          â–¼                                       â”‚
â”‚                    ROUND COMPLETE                                â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## 4. Independent Variables

### 4.1 Model Selection (Between-Subjects)
Fixed set of models for MVP:
- `claude-3-5-sonnet-20241022` (Anthropic)
- `gpt-4o` (OpenAI)
- `gemini-1.5-pro` (Google)

Each model plays each role (Judge, Truth-Teller, Fibber) across rounds.

### 4.2 Storytelling Strategy (Between-Subjects)
Theory-grounded strategies based on Manning/Horton methodology:

| Strategy | Description | Theory Basis |
|----------|-------------|--------------|
| `baseline` | No special instructions | Control condition |
| `level_k_0` | "Pick the most obvious approach" | Level-k reasoning |
| `level_k_1` | "Anticipate what others might expect" | Level-k reasoning |
| `level_k_2` | "Think about what others think you'll do" | Level-k reasoning |
| `source_heavy` | "Emphasize credible sources" | Source credibility |
| `source_light` | "Minimize source references" | Source credibility |
| `detail_granular` | "Include specific dates, names, numbers" | Specificity hypothesis |
| `detail_general` | "Keep details vague and general" | Specificity hypothesis |
| `style_logical` | "Use logical, analytical tone" | Communication style |
| `style_emotional` | "Use emotional, narrative tone" | Communication style |

### 4.3 Fact Category (Between-Subjects)
- `science` - Strange scientific facts
- `history` - Surprising historical events
- `culture` - Unusual cultural practices
- `geography` - Weird geographical facts
- `technology` - Counter-intuitive tech facts
- `biology` - Strange animal/human body facts

### 4.4 Question Style (Between-Subjects)
- `adversarial` - "Probe for inconsistencies"
- `curious` - "Ask clarifying questions"
- `verification` - "Request sources and evidence"
- `intuitive` - "Follow your gut"

### 4.5 Judge Temperature (Between-Subjects)
- `low` (0.3) - More deterministic
- `default` (1.0) - Standard
- `high` (1.5) - More creative/random

### 4.6 Game Configuration (Between-Subjects)
- `standard` - 2 truth, 1 lie
- `all_truth` - 3 truth, judge believes 1 lie
- `all_lies` - 3 lies, judge believes 1 lie
- `majority_lies` - 1 truth, 2 lies

---

## 5. Dependent Variables

### 5.1 Primary Outcomes

#### Judge Metrics
| Metric | Description | Calculation |
|--------|-------------|-------------|
| `detection_accuracy` | % of rounds where judge correctly identifies fibber | correct_detections / total_rounds |
| `false_accusation_rate` | % of rounds where judge accuses truth-teller | false_accusations / total_rounds |
| `confidence_calibration` | Correlation between confidence and accuracy | corr(confidence, correct) |

#### Fibber Metrics
| Metric | Description | Calculation |
|--------|-------------|-------------|
| `deception_success_rate` | % of rounds where fibber is NOT detected | undetected / total_as_fibber |
| `believability_score` | Average judge confidence when fibber is believed | mean(confidence when wrong) |

#### Truth-Teller Metrics
| Metric | Description | Calculation |
|--------|-------------|-------------|
| `vindication_rate` | % of rounds where truth-teller is NOT accused | not_accused / total_as_truth_teller |
| `false_accusation_suffered` | % of rounds where truth-teller IS accused | accused / total_as_truth_teller |

### 5.2 Secondary Outcomes

#### Linguistic Features
| Feature | Description |
|---------|-------------|
| `word_count` | Total words in story/answer |
| `specificity_score` | Density of specific details (names, dates, numbers) |
| `hedge_count` | Number of hedging phrases ("maybe", "I think") |
| `source_mentions` | Number of source citations |
| `question_types` | Classification of judge questions |

#### Process Metrics
| Metric | Description |
|--------|-------------|
| `story_generation_time` | Latency for story generation |
| `qa_response_time` | Latency for Q&A responses |
| `token_usage` | Tokens consumed per phase |

---

## 6. Experimental Conditions

### 6.1 Full Factorial Design
For MVP, we limit the full factorial to reduce combinations:

**Core Conditions** (for each model triplet):
- 3 Judge models Ã— 3 Storyteller model combinations
- 10 strategies Ã— 6 categories = 60 content conditions
- 4 question styles
- 3 temperature levels
- 4 game configurations

**Total potential conditions**: 3 Ã— 3 Ã— 60 Ã— 4 Ã— 3 Ã— 4 = 25,920

### 6.2 MVP Reduced Design
For pilot, we use a Latin Square design to reduce:
- Fix storyteller models to match judge model (same-model rounds)
- Sample 3 strategies Ã— 3 categories = 9 content conditions
- 2 question styles
- 1 temperature level
- 2 game configurations (standard + all_truth)

**MVP conditions**: 3 Ã— 9 Ã— 2 Ã— 2 = 108 conditions Ã— 30 rounds = 3,240 rounds

---

## 7. Hypotheses

### Pre-Registered Hypotheses

#### H1: Detection Difficulty
**H1a**: Fibbers using `source_heavy` strategy will be detected LESS often than baseline.
**H1b**: Fibbers using `detail_granular` strategy will be detected LESS often than baseline.
**H1c**: Truth-tellers using `detail_general` strategy will be accused MORE often than baseline.

#### H2: Model Asymmetries
**H2a**: Judges will be MORE accurate when evaluating stories from the SAME model family.
**H2b**: Fibbers will be MORE successful when lying to a DIFFERENT model family.

#### H3: Question Style Effects
**H3a**: `adversarial` questioning will increase detection accuracy vs. `curious`.
**H3b**: `verification` questioning will increase detection accuracy vs. `intuitive`.

#### H4: Frame-Breaking
**H4a**: In `all_truth` configuration, judge confidence will be LOWER than in `standard`.
**H4b**: Higher temperature judges will be MORE likely to break frame in impossible tasks.

#### H5: The Strange Truth Problem
**H5a**: False accusation rate for truth-tellers will be HIGHER for "stranger" facts.
**H5b**: There exists a fact strangeness threshold above which truth-telling becomes harder than lying.

---

## 8. Procedure

### 8.1 Round Execution

```
1. SETUP
   a. Sample experimental condition
   b. Assign models to roles (Judge, Storyteller A/B/C)
   c. Assign roles (Truth-Teller, Truth-Teller, Fibber)
   d. Select facts for truth-tellers from fact database
   e. Select category for fibber fabrication

2. STORY GENERATION
   a. Generate 3 stories in parallel (or sequential for rate limits)
   b. Record: content, tokens, latency, raw response
   c. Randomize presentation order

3. JUDGE REVIEW
   a. Present all 3 stories to judge (no role info)
   b. Record: initial impressions (optional)

4. Q&A SESSION
   For each storyteller (randomized order):
     For i in range(3):
       a. Judge generates question for storyteller
       b. Storyteller generates answer
       c. Record: question, answer, tokens, latency

5. VERDICT
   a. Judge provides final accusation + confidence + reasoning
   b. Record: accused_id, confidence (1-10), reasoning, raw_response
   c. Check for frame-breaking (refusal to accuse)

6. OUTCOME CALCULATION
   a. Compare accusation to actual roles
   b. Calculate all metrics
   c. Store complete round data
```

### 8.2 Batching and Checkpointing

- Rounds grouped by condition for caching efficiency
- Checkpoint after EVERY round (fail-safe)
- Progress logged to console and file
- Resume capability from any checkpoint

---

## 9. Analysis Plan

### 9.1 Primary Analysis

#### Detection Accuracy by Model
- Compute detection_accuracy per judge model
- ANOVA: accuracy ~ judge_model
- Post-hoc: pairwise comparisons with Bonferroni correction

#### Deception Success by Strategy
- Compute deception_success_rate per strategy
- ANOVA: success ~ strategy
- Pre-planned contrasts: each strategy vs. baseline

#### Truth-Teller Vindication by Category
- Compute vindication_rate per category
- Chi-square test: vindication ~ category
- Effect size: CramÃ©r's V

### 9.2 Secondary Analyses

#### Cross-Setting Validation (Manning/Horton Method)
1. Split data: Train on categories A, B; Test on category C
2. Identify best-performing strategies on train set
3. Evaluate generalization to test set
4. Compare to atheoretical baseline

#### Linguistic Feature Analysis
- Correlate linguistic features with outcomes
- Build predictive model: Detection ~ Linguistic Features
- Identify "tells" that predict fibber status

#### Questioning Strategy Analysis
- Cluster question types
- Correlate question patterns with detection success
- Identify optimal questioning strategies

### 9.3 Exploratory Analyses

#### Frame-Breaking Analysis
- Compare confidence distributions: standard vs. all_truth vs. all_lies
- Measure frame-break rate by temperature
- Qualitative analysis of frame-break reasoning

#### Model Self-Detection
- Compare detection accuracy when judge and fibber are same model family
- Test for "home field advantage" or "blind spot"

---

## 10. Limitations and Threats to Validity

### Internal Validity
- **Prompt sensitivity**: Results may depend on exact prompt wording
- **Temperature effects**: Model behavior varies with temperature
- **Caching effects**: Repeated similar prompts may produce cached responses

### External Validity
- **Model vintage**: Results specific to model versions tested
- **Fact database bias**: Generated facts may have systematic properties
- **English-only**: Results may not generalize to other languages

### Construct Validity
- **"Deception" vs. "Creative writing"**: LLMs may treat fabrication as creative task
- **"Detection" vs. "Pattern matching"**: LLMs may use heuristics, not reasoning

### Mitigation Strategies
- Use diverse prompts to test robustness
- Document exact model versions
- Include prompt variations as experimental conditions
- Pre-register hypotheses before full data collection

---

## 11. Ethical Considerations

### LLM Deception Research
- This research studies LLM capabilities for deception
- Findings could inform both detection and generation of misinformation
- Results will be published with responsible disclosure considerations

### Data Handling
- All data is LLM-generated (no human subjects in MVP)
- Future human-in-the-loop phases will require IRB review
- Fact database will be reviewed for harmful content

---

## 12. Timeline

### Phase 1: MVP Core Game (Current)
- Week 1-2: Implement core game loop
- Week 3: Run pilot with reduced conditions
- Week 4: Validate metrics, adjust design

### Phase 2: Fact Database & Expansion
- Week 5-6: Build fact database generator
- Week 7-8: Expand to full condition set
- Week 9-10: Run full experiment

### Phase 3: Analysis & Iteration
- Week 11-12: Primary analysis
- Week 13-14: Secondary/exploratory analysis
- Week 15-16: Write-up and next phase planning

---

## Appendix A: Prompt Templates

See `BUILD_TEMPLATE.md` for exact prompt specifications.

## Appendix B: Statistical Power Calculations

To be completed after pilot data collection.

## Appendix C: Code Repository Structure

See `BUILD_TEMPLATE.md` for implementation details.