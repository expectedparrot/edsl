# Two Truths and a Lie: Build Template

**Version**: 1.0.0  
**Status**: Outline for Subagent Implementation  
**Reference**: See `STUDY_DESIGN.md` and `FEATURE_ROADMAP.md` for full context

---

## Quick Start for Subagents

This document outlines WHAT to build. Each section is a separate task. Build in order—each depends on the previous.

**Key Rule**: Check EDSL docs at `docs.expectedparrot.com` for current API before implementing.

---

## 1. Project Setup (Task 1)

### Deliverables
```
two_truths_lie/
├── pyproject.toml          # Dependencies: edsl, pydantic, pytest
├── pytest.ini              # pytest configuration
├── .env.example            # EXPECTED_PARROT_API_KEY=your_key
├── src/two_truths_lie/
│   └── __init__.py
└── tests/
    └── __init__.py
```

### Acceptance Criteria
- `pip install -e .` succeeds
- `pytest` runs with no errors
- `from edsl import Agent, Model, Survey` works

---

## 2. Configuration (Task 2)

### Files to Create
- `src/two_truths_lie/config/schema.py`
- `src/two_truths_lie/config/defaults.py`

### Schema (Pydantic Models)

```python
# KEY CONFIGS TO DEFINE:

class ModelConfig:
    name: str                    # e.g., "claude-3-5-sonnet-20241022"
    temperature: float = 1.0
    
class GameConfig:
    num_storytellers: int = 3
    num_truth_tellers: int = 2   # implies 1 fibber in standard config
    questions_per_storyteller: int = 3
    story_word_min: int = 250
    story_word_max: int = 500
    answer_word_min: int = 25
    answer_word_max: int = 150
    game_type: Literal["standard", "all_truth", "all_lies", "majority_lies"]

class ExperimentConfig:
    judge_model: ModelConfig
    storyteller_model: ModelConfig
    game: GameConfig
    rounds_per_condition: int = 30
```

### Tests to Write
- Valid config loads without error
- Invalid config raises `ValidationError`
- Defaults are applied for missing optional fields

---

## 3. Data Models (Task 3)

### Files to Create
- `src/two_truths_lie/models/storyteller.py`
- `src/two_truths_lie/models/story.py`
- `src/two_truths_lie/models/qa.py`
- `src/two_truths_lie/models/verdict.py`
- `src/two_truths_lie/models/round.py`

### Core Dataclasses

```python
# All should be frozen=True dataclasses with JSON serialization

@dataclass(frozen=True)
class Storyteller:
    id: str                              # "A", "B", "C"
    model: str
    role: Literal["truth_teller", "fibber"]
    strategy: str                        # e.g., "baseline", "level_k_1"
    fact_id: Optional[str] = None        # Only for truth_tellers

@dataclass(frozen=True)
class Story:
    storyteller_id: str
    content: str
    source_cited: Optional[str]
    word_count: int
    generation_metadata: dict            # tokens, latency, etc.

@dataclass(frozen=True)
class Question:
    judge_model: str
    target_storyteller_id: str
    content: str
    question_number: int                 # 1, 2, or 3

@dataclass(frozen=True)
class Answer:
    storyteller_id: str
    question_number: int
    content: str
    word_count: int

@dataclass(frozen=True)
class Verdict:
    judge_model: str
    accused_id: str
    confidence: int                      # 1-10
    reasoning: str
    frame_break_attempted: bool          # Did judge refuse to accuse?
    raw_response: str

@dataclass(frozen=True)
class RoundOutcome:
    detection_correct: bool
    false_accusation: bool
    fibber_id: str
    accused_id: str
```

### Tests to Write
- Each dataclass serializes to/from JSON
- `Verdict.confidence` validates range 1-10
- `RoundOutcome` correctly computes from verdict + actual roles

---

## 4. Prompt Templates (Task 4)

### Files to Create
- `src/two_truths_lie/prompts/base.py`
- `src/two_truths_lie/prompts/storyteller.py`
- `src/two_truths_lie/prompts/judge.py`
- `src/two_truths_lie/prompts/strategies.py`

### Key Design Requirement

**CRITICAL**: Truth-teller and Fibber prompts MUST be structurally identical to avoid "tells". Only the role-specific task differs.

### Prompt Classes to Implement

```python
class BasePrompt:
    """All prompts inherit from this. Has render() method."""
    
class TruthTellerPrompt(BasePrompt):
    """Prompt for truth-teller. Takes: category, fact, strategy"""
    
class FibberPrompt(BasePrompt):
    """Prompt for fibber. Takes: category, strategy"""
    # Structure MUST mirror TruthTellerPrompt exactly
    
class JudgeReviewPrompt(BasePrompt):
    """Judge reviews 3 stories. Takes: stories (randomized order)"""
    
class JudgeQuestionPrompt(BasePrompt):
    """Judge asks one question. Takes: story_context, target_id, question_num"""
    
class JudgeVerdictPrompt(BasePrompt):
    """Judge makes final decision. Takes: stories, qa_exchanges"""
```

### Strategy Instructions
Define these in `strategies.py`:
- `baseline` - No special instructions
- `level_k_0` - "Pick the most obvious approach"
- `level_k_1` - "Anticipate what others might expect"
- `source_heavy` - "Emphasize credible sources"
- `detail_granular` - "Include specific dates, names, numbers"

### Tests to Write
- Truth/Fibber prompts are structurally identical (diff only role line)
- All template variables render correctly
- Strategy instructions inject at correct location

---

## 5. EDSL Adapter (Task 5)

### File to Create
- `src/two_truths_lie/edsl_adapter.py`

### Purpose
Wraps all EDSL calls to provide:
- Consistent interface
- Retry logic with exponential backoff
- Result parsing into domain objects
- Raw response preservation

### Methods to Implement

```python
class EDSLAdapter:
    def generate_story(
        self,
        model_name: str,
        temperature: float,
        prompt_text: str,
    ) -> dict:
        """Returns: {content, raw_response, tokens, latency_ms}"""
        # Use: Agent, Model, Survey, QuestionFreeText
        
    def generate_question(
        self,
        model_name: str,
        temperature: float,
        prompt_text: str,
    ) -> dict:
        """Returns: {content, raw_response}"""
        
    def generate_answer(
        self,
        model_name: str,
        temperature: float,
        prompt_text: str,
    ) -> dict:
        """Returns: {content, raw_response, word_count}"""
        
    def generate_verdict(
        self,
        model_name: str,
        temperature: float,
        prompt_text: str,
    ) -> dict:
        """Returns: {accused_id, confidence, reasoning, raw_response, frame_break_attempted}"""
        # Parse structured response from LLM
```

### Error Handling
- Define: `StoryGenerationError`, `VerdictParsingError`
- Implement: `@retry_with_backoff(max_retries=3)`

### Tests to Write
- Mock EDSL calls return expected structure
- Retries work on transient failures
- Parsing extracts fields correctly

---

## 6. Game Engine (Task 6)

### File to Create
- `src/two_truths_lie/engine.py`

### Purpose
Orchestrates a single round of the game.

### Key Methods

```python
class GameEngine:
    def __init__(self, config: GameConfig, edsl: EDSLAdapter):
        pass
    
    def setup_round(self, condition: ConditionConfig) -> RoundSetup:
        """Assign roles, select facts, create storytellers."""
        # Returns: RoundSetup with storytellers, judge, story_order (randomized)
        
    def execute_story_phase(self, setup: RoundSetup) -> list[Story]:
        """Generate all 3 stories."""
        
    def execute_qa_phase(
        self, 
        setup: RoundSetup, 
        stories: list[Story]
    ) -> list[QAExchange]:
        """Judge asks 3 questions to each storyteller, they answer."""
        # Total: 9 Q&A exchanges
        
    def execute_verdict_phase(
        self,
        setup: RoundSetup,
        stories: list[Story],
        qa_exchanges: list[QAExchange]
    ) -> Verdict:
        """Judge makes final decision."""
        
    def calculate_outcome(self, setup: RoundSetup, verdict: Verdict) -> RoundOutcome:
        """Determine who won/lost."""
        
    def run_round(self, condition: ConditionConfig) -> Round:
        """Execute complete round, return all data."""
```

### Tests to Write
- `run_round` executes all phases in order
- Stories are presented to judge in randomized order
- Outcome correctly identifies detection success/failure

---

## 7. Experiment Runner (Task 7)

### File to Create
- `src/two_truths_lie/runner.py`

### Purpose
Runs multiple rounds across conditions with checkpointing.

### Key Methods

```python
class ExperimentRunner:
    def __init__(self, config: ExperimentConfig, engine: GameEngine, store: ResultStore):
        pass
        
    def generate_conditions(self) -> list[ConditionConfig]:
        """Generate all condition combinations."""
        
    def estimate_cost(self, conditions: list[ConditionConfig]) -> CostEstimate:
        """Estimate API costs before running."""
        
    def run_experiment(self, rounds_per_condition: int = 30) -> ExperimentResults:
        """Run full experiment with progress logging."""
        # Checkpoint after each round
        
    def resume_experiment(self, checkpoint_path: str) -> ExperimentResults:
        """Resume from checkpoint."""
```

### Tests to Write
- Conditions are enumerated correctly
- Checkpoint saves after each round
- Resume skips completed rounds

---

## 8. Result Storage (Task 8)

### File to Create
- `src/two_truths_lie/storage.py`

### Purpose
Persist rounds to JSON files with query capability.

### Interface

```python
class ResultStore:
    def save_round(self, round: Round) -> None:
        """Save completed round."""
        
    def get_round(self, round_id: str) -> Round:
        """Retrieve by ID."""
        
    def query_rounds(self, filters: RoundFilters) -> list[Round]:
        """Query with filters (model, strategy, outcome, etc.)."""
        
    def get_summary(self) -> ExperimentSummary:
        """Aggregate statistics."""
```

### Storage Format
```
results/
├── index.json           # Round IDs and metadata for fast queries
└── rounds/
    ├── round_001.json
    ├── round_002.json
    └── ...
```

---

## 9. Analysis Module (Task 9)

### File to Create
- `src/two_truths_lie/analysis.py`

### Metrics to Compute

```python
class MetricsCalculator:
    def judge_accuracy(self, rounds: list[Round]) -> float:
        """% correct detections"""
        
    def fibber_success_rate(self, rounds: list[Round]) -> float:
        """% undetected"""
        
    def false_accusation_rate(self, rounds: list[Round]) -> float:
        """% truth-tellers accused"""
        
    def confidence_calibration(self, rounds: list[Round]) -> float:
        """Correlation between confidence and accuracy"""
        
    def by_condition(self, rounds: list[Round], group_by: str) -> dict:
        """Group metrics by model/strategy/category"""
```

---

## 10. CLI Entry Point (Task 10)

### File to Create
- `src/two_truths_lie/__main__.py`

### Commands

```bash
# Run single round (for testing)
python -m two_truths_lie run-round --config config.yaml

# Run full experiment
python -m two_truths_lie run-experiment --config config.yaml --rounds 30

# Resume from checkpoint
python -m two_truths_lie resume --checkpoint results/checkpoint.json

# Generate report
python -m two_truths_lie report --results results/ --output report.md
```

---

## Build Order

1. **Task 1**: Project Setup → verify EDSL imports
2. **Task 2**: Configuration → verify config loads
3. **Task 3**: Data Models → verify serialization
4. **Task 4**: Prompts → verify rendering
5. **Task 5**: EDSL Adapter → verify mock calls work
6. **Task 6**: Game Engine → verify single round runs
7. **Task 7**: Experiment Runner → verify multi-round
8. **Task 8**: Result Storage → verify persistence
9. **Task 9**: Analysis → verify metrics compute
10. **Task 10**: CLI → verify commands run

Each task should be **fully tested** before proceeding to the next.

---

## Key EDSL Patterns

```python
# Basic survey execution
from edsl import Agent, Model, Survey, QuestionFreeText

agent = Agent(traits={"role": "storyteller"})
model = Model("claude-3-5-sonnet-20241022", temperature=1.0)
question = QuestionFreeText(question_name="story", question_text="...")
survey = Survey([question])
results = survey.by(agent).by(model).run()
answer = results.select("answer.story").to_list()[0]
```

Check `docs.expectedparrot.com` for:
- Current model names
- Rate limit handling
- Result parsing methods

---

## End of Template

This document provides the WHAT. Subagents implement the HOW.
