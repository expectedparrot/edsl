# Fact Database Generator

**Version**: 1.0.0  
**Last Updated**: 2026-01-16  
**Status**: Specification for Subagent Implementation

---

## Overview

This document specifies a standalone tool for generating and curating a corpus of unusual-but-true facts. Truth-tellers in the "Two Truths and a Lie" game select facts from this database to craft their stories.

**Design Philosophy**: Create a "Ripley's Believe It or Not" collection—facts that are genuinely true but sound implausible enough that a skilled fibber could fabricate something equally believable.

---

## Fact Categories

### Primary Categories

| Category ID | Description | Example Domain |
|-------------|-------------|----------------|
| `historical_oddities` | Surprising events from history | Wars started over trivial causes, unusual laws |
| `scientific_discoveries` | Counter-intuitive scientific findings | Quantum phenomena, biological anomalies |
| `cultural_traditions` | Unusual customs from around the world | Festival rituals, social norms |
| `natural_phenomena` | Strange occurrences in nature | Weather anomalies, geological formations |
| `animal_behaviors` | Unexpected animal adaptations/actions | Mating rituals, survival mechanisms |
| `food_origins` | Surprising histories of common foods | Accidental inventions, cultural transfers |
| `unlikely_inventions` | Products with unexpected origin stories | Failed experiments that became hits |
| `archaeological_mysteries` | Puzzling discoveries from the past | Artifacts that challenge timelines |
| `forgotten_figures` | Remarkable people lost to history | Unsung heroes, eccentric geniuses |
| `unexpected_connections` | Surprising links between unrelated things | Historical coincidences, six-degrees stories |

### Category Balance Requirements

- **Minimum**: 50 facts per category
- **Target**: 100 facts per category for MVP
- **Distribution**: Even distribution across categories in experiments

---

## Fact Schema

### Required Fields

```python
@dataclass
class Fact:
    id: str                          # Unique identifier (e.g., "hist_001")
    category: str                    # Category ID from table above
    core_claim: str                  # The surprising fact in 1-2 sentences
    supporting_details: dict         # Specific names, dates, numbers, locations
    source_citation: str             # Verifiable source (URL, book, paper)
    verification_status: str         # "verified", "likely_true", "needs_review"
    strangeness_score: int           # 1-10, how implausible it sounds
    specificity_score: int           # 1-10, how many concrete details available
    created_at: str                  # ISO timestamp
    model_generated_by: str          # Which LLM generated this fact
```

### Example Fact

```json
{
  "id": "hist_042",
  "category": "historical_oddities",
  "core_claim": "The Great Emu War of 1932 was an actual military operation where the Australian army deployed soldiers with machine guns against emus—and lost.",
  "supporting_details": {
    "date": "November 1932",
    "location": "Campion district, Western Australia",
    "participants": "Royal Australian Artillery",
    "weapons": "Two Lewis guns, 10,000 rounds of ammunition",
    "outcome": "Emus won; operation deemed ineffective after one month",
    "emu_casualties": "Estimated 986 of 20,000 target population"
  },
  "source_citation": "Australian Parliament Hansard, 1932; 'The Emu War', Museum of Australian Democracy",
  "verification_status": "verified",
  "strangeness_score": 9,
  "specificity_score": 8,
  "created_at": "2026-01-16T10:00:00Z",
  "model_generated_by": "claude-3-5-sonnet-20241022"
}
```

---

## Generation Pipeline

### Phase 1: LLM-Assisted Fact Discovery

```
┌─────────────────────────────────────────────────────────────┐
│                    FACT GENERATION                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Source    │───▶│     LLM     │───▶│   Parsed    │     │
│  │   Prompt    │    │  Generation │    │    Facts    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  Sources to mine:                                           │
│  - Wikipedia "Did You Know" archives                        │
│  - QI (Quite Interesting) fact collections                  │
│  - Guinness World Records oddities                          │
│  - Science Daily "Strange But True"                         │
│  - Library of Congress unusual collections                  │
│  - Smithsonian "Surprising History" articles                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    VERIFICATION                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Source    │───▶│   Cross-    │───▶│  Verified   │     │
│  │   Lookup    │    │  Reference  │    │    Facts    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  Verification methods:                                      │
│  - Web search for corroborating sources                     │
│  - Second LLM review for plausibility                       │
│  - Human spot-check for sample (future)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SCORING & STORAGE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Strangeness│───▶│    Merge    │───▶│    JSON     │     │
│  │   Scoring   │    │  & Dedup    │    │  Database   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Quality Filtering

Facts must pass these filters:

1. **Verifiability**: Source citation must be checkable
2. **Strangeness Threshold**: Score ≥ 6 to be sufficiently surprising
3. **Specificity Threshold**: Score ≥ 5 to have enough detail for storytelling
4. **No Duplicates**: Semantic deduplication across categories
5. **Content Safety**: No facts involving harm, minors, or sensitive content

---

## Generation Prompts

### Primary Fact Generation Prompt

```
SYSTEM:
You are an expert curator of unusual but TRUE facts, like a researcher 
for Ripley's Believe It or Not. Your facts must be:
- Genuinely TRUE and verifiable
- Surprising, counter-intuitive, or little-known
- Rich in specific details (dates, names, numbers, locations)
- Sourced from reputable references

IMPORTANT: Never fabricate facts. If you're uncertain, say so.

USER:
Generate {count} fascinating TRUE facts in the category: {category}

For each fact, provide:
1. The core claim (1-2 sentences, the surprising part)
2. Supporting details (specific names, dates, numbers, locations)
3. Source citation (book, paper, museum, reputable website)
4. Why it sounds unbelievable (what makes it strange)

Format as JSON array.
```

### Verification Prompt

```
SYSTEM:
You are a fact-checker. Your job is to assess whether a claimed fact 
is likely true, and identify any red flags.

USER:
Please verify this claimed fact:

CLAIM: {core_claim}
DETAILS: {supporting_details}
CITED SOURCE: {source_citation}

Provide:
1. Verification status: "verified", "likely_true", "uncertain", "likely_false"
2. Confidence (1-10)
3. Red flags (if any)
4. Alternative sources found (if any)
5. Reasoning for your assessment
```

### Strangeness Scoring Prompt

```
SYSTEM:
You assess how "strange" or "unbelievable" a true fact sounds to the 
average person. This helps calibrate difficulty for a deception game.

USER:
Rate the strangeness of this fact on a scale of 1-10:

FACT: {core_claim}

Scoring guide:
1-3: Mildly interesting but not surprising
4-6: Notably unusual, might raise eyebrows  
7-9: Sounds almost too strange to be true
10: Completely defies common sense expectations

Provide:
1. Strangeness score (1-10)
2. Brief reasoning (why this score)
```

---

## CLI Interface

### Commands

```bash
# Generate new facts for a category
python -m fact_generator generate \
  --category historical_oddities \
  --count 20 \
  --model claude-3-5-sonnet-20241022 \
  --output facts/raw/

# Verify generated facts
python -m fact_generator verify \
  --input facts/raw/historical_oddities.json \
  --output facts/verified/ \
  --model gpt-4o

# Score facts for strangeness
python -m fact_generator score \
  --input facts/verified/ \
  --output facts/scored/

# Build final database
python -m fact_generator build \
  --input facts/scored/ \
  --output data/fact_database.json \
  --min-strangeness 6 \
  --min-specificity 5

# Statistics on database
python -m fact_generator stats \
  --database data/fact_database.json
```

### Example Output

```
$ python -m fact_generator stats --database data/fact_database.json

Fact Database Statistics
========================
Total facts: 847
Verified: 712 (84.1%)
Likely true: 135 (15.9%)

By Category:
  historical_oddities:     92 facts (avg strangeness: 7.2)
  scientific_discoveries:  88 facts (avg strangeness: 7.8)
  cultural_traditions:     85 facts (avg strangeness: 6.9)
  natural_phenomena:       81 facts (avg strangeness: 7.4)
  animal_behaviors:        89 facts (avg strangeness: 7.1)
  food_origins:           84 facts (avg strangeness: 6.5)
  unlikely_inventions:     78 facts (avg strangeness: 6.8)
  archaeological_mysteries: 86 facts (avg strangeness: 8.1)
  forgotten_figures:       82 facts (avg strangeness: 6.7)
  unexpected_connections:  82 facts (avg strangeness: 7.5)

Strangeness Distribution:
  6: ████████████ 156
  7: ██████████████████ 234
  8: ████████████████ 198
  9: ██████████ 142
  10: █████ 117
```

---

## Data Model Implementation

### Core Classes

```python
# src/two_truths_lie/facts/schema.py

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import json

@dataclass
class Fact:
    id: str
    category: str
    core_claim: str
    supporting_details: dict
    source_citation: str
    verification_status: str = "needs_review"
    strangeness_score: Optional[int] = None
    specificity_score: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_generated_by: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "core_claim": self.core_claim,
            "supporting_details": self.supporting_details,
            "source_citation": self.source_citation,
            "verification_status": self.verification_status,
            "strangeness_score": self.strangeness_score,
            "specificity_score": self.specificity_score,
            "created_at": self.created_at,
            "model_generated_by": self.model_generated_by
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        """Deserialize from dictionary."""
        return cls(**data)


@dataclass  
class FactDatabase:
    facts: list[Fact] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def add_fact(self, fact: Fact) -> None:
        """Add a fact to the database."""
        self.facts.append(fact)
    
    def get_by_category(self, category: str) -> list[Fact]:
        """Get all facts in a category."""
        return [f for f in self.facts if f.category == category]
    
    def get_by_strangeness(self, min_score: int, max_score: int = 10) -> list[Fact]:
        """Get facts within a strangeness range."""
        return [f for f in self.facts 
                if f.strangeness_score and min_score <= f.strangeness_score <= max_score]
    
    def sample(self, n: int, category: Optional[str] = None) -> list[Fact]:
        """Random sample of facts, optionally filtered by category."""
        import random
        pool = self.get_by_category(category) if category else self.facts
        return random.sample(pool, min(n, len(pool)))
    
    def save(self, path: str) -> None:
        """Save database to JSON file."""
        data = {
            "metadata": self.metadata,
            "facts": [f.to_dict() for f in self.facts]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "FactDatabase":
        """Load database from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        db = cls(metadata=data.get("metadata", {}))
        db.facts = [Fact.from_dict(f) for f in data.get("facts", [])]
        return db
```

### Generator Class

```python
# src/two_truths_lie/facts/generator.py

from edsl import Agent, Model, Survey, QuestionFreeText
import json

CATEGORIES = [
    "historical_oddities",
    "scientific_discoveries", 
    "cultural_traditions",
    "natural_phenomena",
    "animal_behaviors",
    "food_origins",
    "unlikely_inventions",
    "archaeological_mysteries",
    "forgotten_figures",
    "unexpected_connections"
]

class FactGenerator:
    """Generates unusual-but-true facts using LLMs."""
    
    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        self.model_name = model_name
        self.model = Model(model_name)
    
    def generate_facts(self, category: str, count: int = 10) -> list[dict]:
        """Generate facts for a category."""
        prompt = self._build_generation_prompt(category, count)
        
        agent = Agent(traits={"role": "fact_curator"})
        question = QuestionFreeText(
            question_name="facts",
            question_text=prompt
        )
        survey = Survey([question])
        results = survey.by(agent).by(self.model).run()
        
        response = results.select("answer.facts").to_list()[0]
        return self._parse_facts(response, category)
    
    def verify_fact(self, fact: dict) -> dict:
        """Verify a fact and return verification results."""
        prompt = self._build_verification_prompt(fact)
        # ... implementation
        pass
    
    def score_strangeness(self, fact: dict) -> int:
        """Score how strange a fact sounds."""
        prompt = self._build_strangeness_prompt(fact)
        # ... implementation
        pass
    
    def _build_generation_prompt(self, category: str, count: int) -> str:
        """Build the fact generation prompt."""
        return f"""Generate {count} fascinating TRUE facts in the category: {category}

For each fact, provide a JSON object with:
- "core_claim": The surprising fact in 1-2 sentences
- "supporting_details": Object with specific names, dates, numbers, locations
- "source_citation": Verifiable source (book, paper, museum, website)
- "why_strange": Brief note on what makes it unbelievable

Return as a JSON array. Only include facts you are confident are TRUE."""
    
    def _parse_facts(self, response: str, category: str) -> list[dict]:
        """Parse LLM response into structured facts."""
        try:
            # Find JSON array in response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                facts = json.loads(response[start:end])
                for i, fact in enumerate(facts):
                    fact['category'] = category
                    fact['id'] = f"{category[:4]}_{i:03d}"
                return facts
        except json.JSONDecodeError:
            return []
        return []
```

---

## Integration with Game Engine

### Fact Provider Interface

```python
# src/two_truths_lie/facts/provider.py

from typing import Optional
import random

class FactProvider:
    """Provides facts to truth-tellers during rounds."""
    
    def __init__(self, database_path: str):
        self.database = FactDatabase.load(database_path)
        self.used_fact_ids: set[str] = set()
    
    def get_fact(
        self, 
        category: Optional[str] = None,
        min_strangeness: int = 6,
        exclude_used: bool = True
    ) -> Fact:
        """Get a random fact meeting criteria."""
        candidates = self.database.facts
        
        if category:
            candidates = [f for f in candidates if f.category == category]
        
        candidates = [f for f in candidates 
                     if f.strangeness_score and f.strangeness_score >= min_strangeness]
        
        if exclude_used:
            candidates = [f for f in candidates if f.id not in self.used_fact_ids]
        
        if not candidates:
            raise ValueError("No facts available matching criteria")
        
        fact = random.choice(candidates)
        self.used_fact_ids.add(fact.id)
        return fact
    
    def reset_used(self) -> None:
        """Reset the used facts tracker."""
        self.used_fact_ids.clear()
```

### Usage in Game Engine

```python
# In GameEngine.setup_round()

def setup_round(self, condition: ConditionConfig) -> RoundSetup:
    """Assign roles, select facts, create storytellers."""
    
    storytellers = []
    for i, role in enumerate(["truth_teller", "truth_teller", "fibber"]):
        fact_id = None
        if role == "truth_teller":
            # Get a fact for truth-tellers
            fact = self.fact_provider.get_fact(
                category=condition.fact_category,
                min_strangeness=condition.min_strangeness
            )
            fact_id = fact.id
        
        storyteller = Storyteller(
            id=chr(65 + i),  # "A", "B", "C"
            model=condition.storyteller_model,
            role=role,
            strategy=condition.strategy,
            fact_id=fact_id
        )
        storytellers.append(storyteller)
    
    # Randomize order for judge
    random.shuffle(storytellers)
    
    return RoundSetup(
        storytellers=storytellers,
        judge_model=condition.judge_model,
        fact_category=condition.fact_category
    )
```

---

## Content Safety Guidelines

### Prohibited Content

Facts must NOT involve:

- Violence against specific individuals
- Child endangerment or exploitation
- Detailed instructions for harmful activities
- Unverified medical claims that could cause harm
- Politically divisive content presented as fact
- Conspiracy theories without mainstream verification
- Content that could enable discrimination
- Explicit sexual content
- Personal information about living private individuals

### Review Process

1. **Automated Filter**: Keyword and pattern matching for prohibited content
2. **LLM Review**: Secondary model assesses appropriateness
3. **Human Spot-Check**: Random 5% sample reviewed by human (future phase)

---

## Testing

### Unit Tests

```python
def test_fact_serialization():
    """Fact serializes and deserializes correctly."""
    fact = Fact(
        id="test_001",
        category="historical_oddities",
        core_claim="Test claim",
        supporting_details={"date": "2020"},
        source_citation="Test source"
    )
    data = fact.to_dict()
    restored = Fact.from_dict(data)
    assert restored.id == fact.id
    assert restored.category == fact.category

def test_database_filtering():
    """Database filters by category and strangeness."""
    db = FactDatabase()
    db.add_fact(Fact(id="1", category="history", core_claim="A", 
                     supporting_details={}, source_citation="",
                     strangeness_score=5))
    db.add_fact(Fact(id="2", category="history", core_claim="B",
                     supporting_details={}, source_citation="",
                     strangeness_score=8))
    db.add_fact(Fact(id="3", category="science", core_claim="C",
                     supporting_details={}, source_citation="",
                     strangeness_score=9))
    
    assert len(db.get_by_category("history")) == 2
    assert len(db.get_by_strangeness(7)) == 2

def test_provider_excludes_used():
    """FactProvider doesn't return already-used facts."""
    # ... test implementation
```

### Integration Tests

```python
def test_generation_pipeline():
    """Full pipeline generates valid facts."""
    generator = FactGenerator(model_name="claude-3-5-sonnet-20241022")
    facts = generator.generate_facts("historical_oddities", count=5)
    
    assert len(facts) > 0
    for fact in facts:
        assert "core_claim" in fact
        assert "supporting_details" in fact
        assert "source_citation" in fact
```

---

## Storage Format

### Directory Structure

```
data/
├── fact_database.json          # Final curated database
├── raw/                        # Raw generated facts (pre-verification)
│   ├── historical_oddities.json
│   ├── scientific_discoveries.json
│   └── ...
├── verified/                   # Facts that passed verification
│   └── ...
└── rejected/                   # Facts that failed verification (for analysis)
    └── ...
```

### Database JSON Format

```json
{
  "metadata": {
    "version": "1.0.0",
    "created_at": "2026-01-16T10:00:00Z",
    "total_facts": 847,
    "categories": ["historical_oddities", "..."],
    "generation_models": ["claude-3-5-sonnet-20241022", "gpt-4o"],
    "min_strangeness": 6,
    "min_specificity": 5
  },
  "facts": [
    {
      "id": "hist_001",
      "category": "historical_oddities",
      "core_claim": "...",
      "supporting_details": {},
      "source_citation": "...",
      "verification_status": "verified",
      "strangeness_score": 8,
      "specificity_score": 7,
      "created_at": "2026-01-16T10:00:00Z",
      "model_generated_by": "claude-3-5-sonnet-20241022"
    }
  ]
}
```

---

## Build Order

This tool can be built independently of the main game engine:

1. **Schema** (`facts/schema.py`) - Fact and FactDatabase dataclasses
2. **Generator** (`facts/generator.py`) - LLM-based fact generation
3. **Verifier** (`facts/verifier.py`) - Fact verification pipeline
4. **Scorer** (`facts/scorer.py`) - Strangeness/specificity scoring
5. **Provider** (`facts/provider.py`) - Interface for game engine
6. **CLI** (`facts/__main__.py`) - Command-line interface

---

## Future Enhancements

### Phase 2: Human Curation

- Web interface for human reviewers
- Crowdsourced verification (multiple reviewers per fact)
- Quality scoring based on human agreement

### Phase 3: Dynamic Generation

- Generate facts on-demand during experiments
- Category expansion based on what works well
- Adaptive difficulty (adjust strangeness based on detection rates)

### Phase 4: Multi-Modal

- Facts with image evidence
- Video/audio clip references
- Interactive source verification

---

## Acceptance Criteria

The fact database generator is complete when:

- [ ] Can generate 100+ facts per category via CLI
- [ ] Verification pipeline rejects obviously false claims
- [ ] Strangeness scoring produces reasonable distributions
- [ ] Database loads/saves correctly
- [ ] FactProvider integrates with game engine
- [ ] All unit tests pass
- [ ] Content safety filters implemented
