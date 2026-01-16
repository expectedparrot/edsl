# Two Truths and a Lie: Feature Roadmap

**Version**: 1.0.0  
**Last Updated**: 2026-01-16  
**Status**: MVP Development

---

## Overview

This roadmap defines the phased development of the "Two Truths and a Lie" LLM evaluation system. Each phase builds on the previous, with clear dependencies and acceptance criteria.

---

## Development Principles

### 1. Modularity First
Every component should be independently testable and replaceable.

### 2. Configuration Over Code
Experimental conditions should be configurable without code changes.

### 3. Fail Gracefully
Errors in one round should not crash the experiment.

### 4. Data Integrity
Every decision point should be logged for reproducibility.

### 5. Future-Proof
Architecture should accommodate:
- Human-in-the-loop participants
- New models
- New experimental conditions
- Agent mixture optimization (Manning/Horton method)

---

## Phase 0: Foundation (Prerequisites)

### F0.1: Project Scaffolding
**Priority**: Critical  
**Effort**: Small  
**Dependencies**: None

**Deliverables**:
- [ ] Directory structure created
- [ ] `pyproject.toml` with dependencies
- [ ] `.env.example` for API keys
- [ ] `pytest.ini` configuration
- [ ] `.gitignore`

**Acceptance Criteria**:
- `pip install -e .` succeeds
- `pytest` runs (even with no tests)
- EDSL imports without error

---

### F0.2: Configuration System
**Priority**: Critical  
**Effort**: Medium  
**Dependencies**: F0.1

**Deliverables**:
- [ ] `config/` directory with YAML/JSON configs
- [ ] `ExperimentConfig` dataclass
- [ ] `GameConfig` dataclass  
- [ ] `ModelConfig` dataclass
- [ ] Config validation with Pydantic
- [ ] Config loading utilities

**Acceptance Criteria**:
- Configs load and validate correctly
- Invalid configs raise clear errors
- Default configs provided for quick start

**Test Coverage**:
```python
def test_config_loads_valid_yaml():
    """Valid config file loads without error."""

def test_config_rejects_invalid_game_type():
    """Invalid game_config raises ValidationError."""

def test_config_defaults_applied():
    """Missing optional fields get defaults."""
```

---

### F0.3: Logging Infrastructure
**Priority**: Critical  
**Effort**: Small  
**Dependencies**: F0.1

**Deliverables**:
- [ ] Structured logging setup (JSON format)
- [ ] Log levels configurable
- [ ] Round-level logging
- [ ] Error logging with context

**Acceptance Criteria**:
- Logs are machine-parseable
- Each round has unique correlation ID
- Errors include stack traces

---

## Phase 1: Core Game Loop

### F1.1: Data Models
**Priority**: Critical  
**Effort**: Medium  
**Dependencies**: F0.2

**Deliverables**:
- [ ] `Storyteller` dataclass
- [ ] `Judge` dataclass
- [ ] `Story` dataclass
- [ ] `Question` dataclass
- [ ] `Answer` dataclass
- [ ] `Verdict` dataclass
- [ ] `Round` dataclass
- [ ] `RoundOutcome` dataclass

**Key Design Decisions**:
```python
@dataclass
class Storyteller:
    id: str  # "A", "B", "C"
    model: str
    role: Literal["truth_teller", "fibber"]
    strategy: str
    fact_id: Optional[str]  # None for fibbers
    
@dataclass
class Story:
    storyteller_id: str
    content: str
    source_cited: Optional[str]
    word_count: int
    generation_metadata: dict  # tokens, latency, etc.

@dataclass
class Verdict:
    accused_id: str
    confidence: int  # 1-10
    reasoning: str
    frame_break_attempted: bool  # Did judge refuse to accuse?
    raw_response: str  # Full LLM response for debugging
```

**Acceptance Criteria**:
- All dataclasses serialize to/from JSON
- Type validation on construction
- Immutable after creation (frozen=True)

**Test Coverage**:
```python
def test_storyteller_serialization_roundtrip():
    """Storyteller -> JSON -> Storyteller preserves data."""

def test_verdict_validates_confidence_range():
    """Confidence outside 1-10 raises error."""

def test_round_computes_outcomes_correctly():
    """RoundOutcome correctly identifies detection success."""
```

---

### F1.2: Prompt Templates
**Priority**: Critical  
**Effort**: Medium  
**Dependencies**: F1.1

**Deliverables**:
- [ ] `prompts/` directory
- [ ] `TruthTellerPrompt` class
- [ ] `FibberPrompt` class
- [ ] `JudgeReviewPrompt` class
- [ ] `JudgeQuestionPrompt` class
- [ ] `JudgeVerdictPrompt` class
- [ ] `StorytellerAnswerPrompt` class
- [ ] Strategy-specific prompt variants
- [ ] Prompt template tests

**Critical Requirement**: Truth-teller and Fibber prompts MUST be structurally identical to avoid "tells". Only the role-specific instructions differ.

**Template Structure**:
```python
class BaseStorytellerPrompt:
    """Base template - identical structure for truth/fibber."""
    
    COMMON_STRUCTURE = """
    YOU ARE A STORYTELLER: "WHY WOULD I LIE?"
    
    {role_specific_instructions}
    
    STORYTELLING REQUIREMENTS:
    - Length: 250-500 words
    - Include specific details, dates, names, and locations
    - Create a narrative arc with a clear beginning, surprising middle, and satisfying conclusion
    - Use vivid language that brings the story to life
    - Your tone should be confident and engaging
    
    SOURCE CITATION:
    - End your story by mentioning your source
    - Be prepared to elaborate on this source if questioned
    
    CATEGORY: {category}
    
    {strategy_instructions}
    
    Remember: Your goal is to tell your story so convincingly that the judge believes you!
    """
```

**Acceptance Criteria**:
- Prompts render correctly with all variables
- Truth/Fibber prompts are structurally identical
- Strategy instructions inject cleanly
- No prompt injection vulnerabilities

**Test Coverage**:
```python
def test_truth_fibber_prompts_structurally_identical():
    """Truth and Fibber prompts have same structure minus role instructions."""

def test_prompt_renders_all_variables():
    """All template variables get substituted."""

def test_prompt_strategy_injection():
    """Strategy instructions appear in correct location."""
```

---

### F1.3: EDSL Integration Layer
**Priority**: Critical  
**Effort**: Large  
**Dependencies**: F1.1, F1.2

**Deliverables**:
- [ ] `edsl_adapter.py` - Abstraction over EDSL
- [ ] `StoryGenerationSurvey` - Generate stories from storytellers
- [ ] `JudgeReviewSurvey` - Judge reviews stories
- [ ] `QuestionGenerationSurvey` - Judge generates questions
- [ ] `AnswerGenerationSurvey` - Storytellers answer questions
- [ ] `VerdictSurvey` - Judge makes final decision
- [ ] Result parsing utilities
- [ ] Error handling for EDSL failures

**Key Design**:
```python
class EDSLAdapter:
    """Abstraction layer for EDSL operations."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        
    def generate_story(
        self,
        storyteller: Storyteller,
        prompt: BaseStorytellerPrompt,
        fact: Optional[Fact] = None
    ) -> Story:
        """Generate a single story using EDSL."""
        
    def generate_questions(
        self,
        judge: Judge,
        stories: List[Story],
        prompt: JudgeQuestionPrompt
    ) -> List[Question]:
        """Judge generates questions for storytellers."""
        
    def generate_answer(
        self,
        storyteller: Storyteller,
        story: Story,
        question: Question,
        prompt: StorytellerAnswerPrompt
    ) -> Answer:
        """Storyteller answers a question."""
        
    def generate_verdict(
        self,
        judge: Judge,
        stories: List[Story],
        qa_exchanges: List[QAExchange],
        prompt: JudgeVerdictPrompt
    ) -> Verdict:
        """Judge makes final verdict."""
```

**Acceptance Criteria**:
- All EDSL calls wrapped in try/except
- Retries with exponential backoff
- Results parsed into dataclasses
- Raw responses preserved for debugging

**Test Coverage**:
```python
def test_story_generation_returns_story_object():
    """generate_story returns properly typed Story."""

def test_edsl_error_wrapped_gracefully():
    """EDSL errors converted to domain exceptions."""

def test_result_parsing_extracts_fields():
    """EDSL Results correctly parsed into dataclasses."""
```

---

### F1.4: Game Engine
**Priority**: Critical  
**Effort**: Large  
**Dependencies**: F1.1, F1.2, F1.3

**Deliverables**:
- [ ] `GameEngine` class
- [ ] Round orchestration logic
- [ ] Role assignment logic
- [ ] Story randomization (hide role from judge)
- [ ] Q&A session management
- [ ] Outcome calculation
- [ ] State management during round

**Key Design**:
```python
class GameEngine:
    """Orchestrates a single round of the game."""
    
    def __init__(
        self,
        config: GameConfig,
        edsl_adapter: EDSLAdapter,
        fact_provider: FactProvider
    ):
        self.config = config
        self.edsl = edsl_adapter
        self.facts = fact_provider
        
    def setup_round(self) -> RoundSetup:
        """Assign roles, select facts, prepare storytellers."""
        
    def execute_story_phase(self, setup: RoundSetup) -> List[Story]:
        """All storytellers generate their stories."""
        
    def execute_review_phase(
        self, 
        judge: Judge, 
        stories: List[Story]
    ) -> JudgeReview:
        """Judge reviews all stories (no verdict yet)."""
        
    def execute_qa_phase(
        self,
        judge: Judge,
        storytellers: List[Storyteller],
        stories: List[Story]
    ) -> List[QAExchange]:
        """Judge asks questions, storytellers answer."""
        
    def execute_verdict_phase(
        self,
        judge: Judge,
        stories: List[Story],
        qa_exchanges: List[QAExchange]
    ) -> Verdict:
        """Judge makes final decision."""
        
    def calculate_outcomes(
        self,
        setup: RoundSetup,
        verdict: Verdict
    ) -> RoundOutcome:
        """Determine who won/lost."""
        
    def run_round(self) -> Round:
        """Execute complete round and return results."""
```

**Acceptance Criteria**:
- Complete round executes end-to-end
- Stories randomized before judge sees them
- Outcomes correctly calculated for all game configs
- State is isolated between rounds

**Test Coverage**:
```python
def test_round_executes_all_phases():
    """run_round completes all phases in order."""

def test_story_order_randomized():
    """Judge receives stories in random order."""

def test_outcome_calculation_standard_config():
    """Correct detection -> correct outcome in standard config."""

def test_outcome_calculation_all_truth_config():
    """All-truth config: any accusation is false accusation."""
```

---

### F1.5: Experiment Runner
**Priority**: Critical  
**Effort**: Medium  
**Dependencies**: F1.4

**Deliverables**:
- [ ] `ExperimentRunner` class
- [ ] Condition iteration logic
- [ ] Progress tracking
- [ ] Checkpoint/resume capability
- [ ] Parallel execution support (optional for MVP)
- [ ] Cost estimation before run

**Key Design**:
```python
class ExperimentRunner:
    """Runs multiple rounds across experimental conditions."""
    
    def __init__(
        self,
        config: ExperimentConfig,
        game_engine: GameEngine,
        result_store: ResultStore
    ):
        self.config = config
        self.engine = game_engine
        self.results = result_store
        
    def generate_conditions(self) -> List[ConditionConfig]:
        """Generate all condition combinations to run."""
        
    def estimate_cost(self, conditions: List[ConditionConfig]) -> CostEstimate:
        """Estimate API costs before running."""
        
    def run_experiment(
        self,
        conditions: Optional[List[ConditionConfig]] = None,
        rounds_per_condition: int = 30
    ) -> ExperimentResults:
        """Run full experiment."""
        
    def resume_experiment(self, checkpoint_path: str) -> ExperimentResults:
        """Resume from checkpoint."""
```

**Acceptance Criteria**:
- All conditions enumerated correctly
- Progress visible during execution
- Checkpoint saves after each round
- Resume picks up where left off

**Test Coverage**:
```python
def test_condition_generation_complete():
    """All condition combinations generated."""

def test_checkpoint_saves_progress():
    """Checkpoint file created after each round."""

def test_resume_skips_completed_rounds():
    """Resume doesn't re-run completed rounds."""
```

---

### F1.6: Result Storage
**Priority**: Critical  
**Effort**: Medium  
**Dependencies**: F1.1

**Deliverables**:
- [ ] `ResultStore` interface
- [ ] `JSONResultStore` implementation
- [ ] Round-level storage
- [ ] Experiment-level aggregation
- [ ] Query interface for analysis

**Key Design**:
```python
class ResultStore(Protocol):
    """Interface for result storage."""
    
    def save_round(self, round: Round) -> None:
        """Save a completed round."""
        
    def get_round(self, round_id: str) -> Round:
        """Retrieve a round by ID."""
        
    def query_rounds(
        self,
        filters: Optional[RoundFilters] = None
    ) -> List[Round]:
        """Query rounds with optional filters."""
        
    def get_experiment_summary(self) -> ExperimentSummary:
        """Aggregate statistics across all rounds."""


class JSONResultStore(ResultStore):
    """File-based JSON storage implementation."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.rounds_path = base_path / "rounds"
        self.index_path = base_path / "index.json"
```

**Acceptance Criteria**:
- Rounds persist across process restarts
- Query filters work correctly
- Storage is append-only (no data loss)
- Index enables fast queries

**Test Coverage**:
```python
def test_round_save_and_retrieve():
    """Saved round can be retrieved by ID."""

def test_query_filters_by_condition():
    """Query returns only matching rounds."""

def test_storage_survives_process_restart():
    """Data persists after store is recreated."""
```

---

## Phase 2: Analysis & Metrics

### F2.1: Metrics Calculator
**Priority**: High  
**Effort**: Medium  
**Dependencies**: F1.6

**Deliverables**:
- [ ] `MetricsCalculator` class
- [ ] Judge accuracy metrics
- [ ] Fibber success metrics
- [ ] Truth-teller vindication metrics
- [ ] Confidence calibration metrics
- [ ] Per-condition aggregations

**Acceptance Criteria**:
- All metrics from study design implemented
- Confidence intervals calculated
- Handles edge cases (0 rounds, missing data)

---

### F2.2: Linguistic Analyzer
**Priority**: Medium  
**Effort**: Medium  
**Dependencies**: F1.6

**Deliverables**:
- [ ] `LinguisticAnalyzer` class
- [ ] Word count metrics
- [ ] Specificity scoring
- [ ] Hedging detection
- [ ] Source citation detection
- [ ] Question type classification

**Acceptance Criteria**:
- Analyzers work on Story and Answer objects
- Results stored with round data
- Can run retroactively on stored rounds

---

### F2.3: Report Generator
**Priority**: Medium  
**Effort**: Medium  
**Dependencies**: F2.1, F2.2

**Deliverables**:
- [ ] `ReportGenerator` class
- [ ] Summary statistics tables
- [ ] Condition comparison tables
- [ ] Export to CSV/JSON
- [ ] Markdown report generation

**Acceptance Criteria**:
- Reports are human-readable
- Tables are properly formatted
- Data is exportable for external analysis

---

## Phase 3: Frame-Breaking Experiments

### F3.1: Extended Game Configs
**Priority**: Medium  
**Effort**: Small  
**Dependencies**: F1.4

**Deliverables**:
- [ ] `all_truth` configuration
- [ ] `all_lies` configuration
- [ ] `majority_lies` configuration
- [ ] Frame-break detection in verdict parsing

**Acceptance Criteria**:
- All configs work with existing engine
- Frame-break attempts detected and logged
- Outcomes calculated correctly for each config

---

### F3.2: Temperature Experiments
**Priority**: Low  
**Effort**: Small  
**Dependencies**: F1.3

**Deliverables**:
- [ ] Temperature configuration per role
- [ ] High-temperature judge variants
- [ ] Temperature impact analysis

**Acceptance Criteria**:
- Temperature configurable independently for judge
- Results comparable across temperature settings

---

## Phase 4: Future Extensions (Post-MVP)

### F4.1: Human-in-the-Loop
**Priority**: Future  
**Effort**: Large  
**Dependencies**: All Phase 1

**Deliverables**:
- [ ] Web interface for human participants
- [ ] Human storyteller integration
- [ ] Human judge integration
- [ ] Mixed human/LLM rounds

---

### F4.2: Agent Mixture Optimization
**Priority**: Future  
**Effort**: Large  
**Dependencies**: F2.1

**Deliverables**:
- [ ] Selection method implementation (Manning/Horton)
- [ ] Strategy mixture optimization
- [ ] Cross-setting validation framework

---

### F4.3: Coop Integration
**Priority**: Future  
**Effort**: Medium  
**Dependencies**: All Phase 1

**Deliverables**:
- [ ] Results upload to Coop
- [ ] Experiment sharing
- [ ] Collaborative analysis

---

## Dependency Graph

```
F0.1 (Scaffolding)
  │
  ├──► F0.2 (Config) ──────┬──► F1.1 (Data Models) ──┬──► F1.2 (Prompts)
  │                        │                         │
  └──► F0.3 (Logging) ─────┘                         └──► F1.3 (EDSL Adapter)
                                                              │
                                                              ▼
                                                     F1.4 (Game Engine)
                                                              │
                                                              ▼
                                                     F1.5 (Experiment Runner)
                                                              │
                                                              ▼
                                                     F1.6 (Result Storage)
                                                              │
                      ┌───────────────────────────────────────┼───────────────────┐
                      │                                       │                   │
                      ▼                                       ▼                   ▼
              F2.1 (Metrics)                          F3.1 (Frame-Break)   F3.2 (Temperature)
                      │
                      ▼
              F2.2 (Linguistic)
                      │
                      ▼
              F2.3 (Reports)
                      │
                      ▼
              F4.x (Future)
```

---

## Milestones

### M1: First Round Runs (End of Week 2)
- [ ] F0.1, F0.2, F0.3 complete
- [ ] F1.1, F1.2 complete
- [ ] F1.3 complete (basic)
- [ ] F1.4 complete (basic)
- [ ] Single round executes end-to-end

### M2: Pilot Experiment (End of Week 3)
- [ ] F1.5 complete
- [ ] F1.6 complete
- [ ] 10 rounds run successfully
- [ ] Results stored and retrievable

### M3: MVP Complete (End of Week 4)
- [ ] F2.1 complete
- [ ] 100 rounds across multiple conditions
- [ ] Basic metrics calculated
- [ ] Ready for expanded experiment

### M4: Full Experiment (End of Week 8)
- [ ] F2.2, F2.3 complete
- [ ] F3.1, F3.2 complete
- [ ] Full condition matrix run
- [ ] Analysis complete

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| EDSL API changes | Medium | High | Abstract EDSL behind adapter layer |
| Model rate limits | High | Medium | Implement backoff, checkpoint frequently |
| Cost overrun | Medium | Medium | Estimate costs before running, run in batches |
| Prompt injection | Low | High | Sanitize all inputs to prompts |
| Result data loss | Low | Critical | Append-only storage, frequent checkpoints |

---

## Definition of Done

A feature is "Done" when:
1. ✅ Code implemented and passing linter
2. ✅ Unit tests written and passing
3. ✅ Integration test (if applicable) passing
4. ✅ Documentation updated
5. ✅ Code reviewed (self-review for solo dev)
6. ✅ Works with existing features (no regressions)
