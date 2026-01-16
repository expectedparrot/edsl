# Two Truths and a Lie: LLM Storytelling Challenge

A research framework for studying LLM deception capabilities through a structured storytelling game inspired by "Why Would I Lie?"

## Overview

This project evaluates LLM capabilities in deception, truth-telling, and deception detection through a structured game where:
- **3 Storytellers** each tell a story (2 true, 1 fabricated)
- **1 Judge** tries to identify the fabricator through questioning

## Quick Start

### Prerequisites
- Python 3.10+
- EDSL library (parent repository)
- Expected Parrot API key

### Installation

From the `two_truths_lie` directory:

```bash
pip install -e .
```

### Running the Demo

Test the game flow without API calls:

```bash
python src/demo.py
```

### Running a Real Round

```bash
# Run with default settings
python -m src run-round

# Run with specific model and strategy
python -m src run-round --model claude-3-5-sonnet-20241022 --strategy source_heavy

# Run with a specific fact category
python -m src run-round --category history
```

### Viewing Available Facts

```bash
python -m src show-facts
python -m src show-facts --category science
```

## Project Structure

```
two_truths_lie/
├── src/
│   ├── config/          # Pydantic configuration models
│   ├── models/          # Data models (Storyteller, Story, Verdict, etc.)
│   ├── prompts/         # Prompt templates for storytellers and judge
│   ├── facts/           # Fact database
│   ├── edsl_adapter.py  # EDSL integration layer
│   ├── engine.py        # Game orchestration
│   ├── demo.py          # Demo script
│   └── __main__.py      # CLI entry point
├── tests/               # Test suite
├── pyproject.toml       # Package configuration
└── README.md
```

## Game Flow

1. **Setup**: Assign roles (2 truth-tellers, 1 fibber), select facts
2. **Story Phase**: Each storyteller generates their story
3. **Q&A Phase**: Judge asks 3 questions to each storyteller
4. **Verdict Phase**: Judge identifies suspected fibber with confidence score
5. **Outcome**: Calculate detection accuracy

## Configuration Options

### Storytelling Strategies
- `baseline` - No special instructions
- `level_k_0/1/2` - Game-theoretic reasoning levels
- `source_heavy/light` - Source citation emphasis
- `detail_granular/general` - Specificity levels
- `style_logical/emotional` - Communication styles

### Judge Question Styles
- `adversarial` - Probe for inconsistencies
- `curious` - Clarifying questions
- `verification` - Request sources/evidence
- `intuitive` - Follow instincts

### Fact Categories
- science, history, biology, geography, technology, culture

## Running Tests

```bash
pytest tests/ -v
```

## Documentation

See the design documents in the parent directory:
- `STUDY_DESIGN.md` - Research methodology
- `BUILD_TEMPLATE.md` - Implementation guide
- `FEATURE_ROADMAP.md` - Development phases
