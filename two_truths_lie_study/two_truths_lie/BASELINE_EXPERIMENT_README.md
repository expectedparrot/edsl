# Baseline Experiment: Model Category Comparison

## Overview

This experiment systematically compares LLM performance across different model categories (older, small/fast, flagship) in the Two Truths and a Lie deception detection task. The experiment uses a **sequential testing approach** to optimize costs while maintaining statistical rigor.

## Experimental Design

### Model Categories

**Phase 1: Older/Legacy Models** (~$0.94 for 180 rounds)
- `gpt-3.5-turbo` - OpenAI legacy model
- `claude-3-haiku-20240307` - Early Claude model
- `gemini-1.5-pro` - First-gen Gemini

**Phase 2: Small/Fast Models** (~$1.67 for 240 rounds)
- `claude-3-7-sonnet-20250219` - Fast Claude
- `gemini-2.5-flash` - Fast Gemini
- `gpt-4o-mini` - Small OpenAI
- `claude-3-5-haiku-20241022` - Smallest Claude

**Phase 3: Flagship Models** (~$6.47 for 240 rounds) [OPTIONAL]
- `claude-opus-4-5-20251101` - Latest Claude flagship
- `gpt-4-turbo` - OpenAI flagship
- `claude-sonnet-4-5-20250929` - High-quality Claude
- `chatgpt-4o-latest` - OpenAI latest

### Experimental Conditions

Each model is tested in **two roles**:
1. **Judge** (detective): Trying to identify the fibber
2. **Storyteller** (potential fibber): Playing the game

This creates **6 conditions per category** (judge + storyteller for each model).

### Fixed Parameters

- **Game type**: Standard (2 truth-tellers, 1 fibber)
- **Questions per storyteller**: 1 (1-shot detection)
- **Story length**: 250-500 words
- **Answer length**: 25-150 words
- **Temperature**: 1.0 (for both judge and storyteller)
- **Fact selection**: Random sampling from all 99 facts (no category restriction)
- **Rounds per condition**: 30 (provides 80% power to detect 15pp effect)

### Statistical Power

- **Baseline accuracy**: 33% (random chance with 3 storytellers)
- **Target effect size**: 15 percentage points (33% → 48% accuracy)
- **Statistical power**: 80% (β = 0.20)
- **Significance level**: α = 0.05
- **Sample size per condition**: 30 rounds

## Quick Start

### Prerequisites

- Python 3.10 or later (required for EDSL)
- EDSL library (should be in parent `edsl_wwil` directory)
- API keys configured for:
  - Anthropic (Claude models)
  - OpenAI (GPT models)
  - Google (Gemini models)

### Installation

No installation needed if you have the edsl_wwil repository cloned. The helper script handles PYTHONPATH setup.

### Running the Experiment

#### Option 1: Using Helper Script (Recommended)

```bash
# Make script executable
chmod +x run_baseline.sh

# Estimate costs for Phase 1
./run_baseline.sh --phase 1 --dry-run

# Run Phase 1 (older models, ~$0.94)
./run_baseline.sh --phase 1

# Run Phase 2 (small models, ~$1.67)
./run_baseline.sh --phase 2

# Run Phase 3 (flagship models, ~$6.47) - optional
./run_baseline.sh --phase 3
```

#### Option 2: Direct Python Execution

```bash
# Set Python path and run
export PYTHONPATH=/path/to/edsl_wwil:$PYTHONPATH
python3.11 run_baseline_experiment.py --phase 1
```

### Command-Line Options

```
--phase {1,2,3,all}    Which phase to run
--rounds N             Rounds per condition (default: 30)
--cost-limit X         Maximum cost in USD (default: 100.0)
--dry-run              Estimate costs only, don't run
```

### Examples

```bash
# Pilot run with fewer rounds
./run_baseline.sh --phase 1 --rounds 15 --dry-run

# Run with custom cost limit
./run_baseline.sh --phase 2 --cost-limit 2.0

# Run all phases (not recommended - expensive!)
./run_baseline.sh --phase all --cost-limit 20.0
```

## Analyzing Results

### Basic Analysis

```bash
# Analyze Phase 1 results
python3.11 analyze_baseline_results.py results/phase1_older

# Analyze Phase 2 results
python3.11 analyze_baseline_results.py results/phase2_small

# Analyze combined Phase 1+2
python3.11 analyze_baseline_results.py results/phase1_older results/phase2_small
```

### Output Files

The analysis script generates:

1. **Console Report**: Summary statistics by category and model
2. **Visualization**: `baseline_comparison.png` with 4 plots:
   - Judge accuracy by category
   - Fibber evasion by category
   - Confidence distribution
   - Top model performance
3. **CSV Export**: `baseline_results.csv` for external analysis

### Analysis Options

```
--output-dir DIR    Output directory (default: current)
--no-plots          Skip generating visualizations
```

## Expected Outcomes

### Performance Hypotheses

**H1: Category Performance Ranking**
- Newer/flagship models should outperform older models as judges
- Expected spread: Flagship ~50-60%, Small ~40-50%, Older ~35-45%

**H2: Role Effects**
- Flagship models perform better as judges (detection)
- Smaller models may be sufficient as storytellers

**H3: Confidence Calibration**
- Flagship models should show better calibration (confidence ≈ accuracy)
- Older models may be overconfident

### Success Criteria

| Metric | Target |
|--------|--------|
| Completion rate | >95% of rounds |
| Cost adherence | Within 20% of estimate |
| Statistical power | 80% achieved |
| Data quality | <5% invalid responses |

## Sequential Testing Strategy

The experiment is designed to be run in phases, allowing early assessment:

### Recommended Execution Flow

1. **Run Phase 1** (Older models, ~$0.94)
   - Establishes baseline performance floor
   - Validates experimental setup
   - Low cost for initial data

2. **Analyze Phase 1**
   - Check data quality
   - Verify experimental setup
   - Look for any issues

3. **Run Phase 2** (Small/fast models, ~$1.67)
   - Tests efficiency/cost-effectiveness
   - Builds comparison dataset
   - Total cost so far: ~$2.61

4. **Analyze Phase 1+2 Combined**
   - Compare older vs small models
   - Assess if patterns are meaningful
   - Decide whether to run Phase 3

5. **Optional: Run Phase 3** (Flagship models, ~$6.47)
   - Only run if Phase 1+2 show promising results
   - Measures ceiling performance
   - Most expensive phase

### Decision Points

After Phase 1+2 (~$2.61):
- ✅ **Continue to Phase 3** if:
  - Small models show >40% accuracy as judges
  - Clear improvement over older models
  - Experimental setup working well

- ⏸️ **Skip Phase 3** if:
  - Results near random chance (~33%)
  - High error rates or quality issues
  - Budget constraints

## File Structure

```
two_truths_lie/
├── run_baseline_experiment.py      # Main experiment runner
├── analyze_baseline_results.py     # Results analysis script
├── run_baseline.sh                 # Helper script
├── BASELINE_EXPERIMENT_README.md   # This file
└── results/
    ├── phase1_older/
    │   ├── rounds/                 # Individual round JSON files
    │   └── index.json              # Round metadata
    ├── phase2_small/
    └── phase3_flagship/
```

## Troubleshooting

### Python Version Issues

**Error**: `TypeError: unsupported operand type(s) for |`

**Solution**: You need Python 3.10+. Check your version:
```bash
python3 --version
```

Install Python 3.11:
```bash
# macOS (Homebrew)
brew install python@3.11

# Linux (apt)
sudo apt install python3.11
```

### Module Not Found: edsl

**Error**: `ModuleNotFoundError: No module named 'edsl'`

**Solution**: Set PYTHONPATH to parent directory:
```bash
export PYTHONPATH=/path/to/edsl_wwil:$PYTHONPATH
```

Or use the helper script `run_baseline.sh` which handles this automatically.

### API Key Issues

**Error**: `Authentication failed`

**Solution**: Ensure API keys are configured:
```bash
# Check environment variables
env | grep -E "ANTHROPIC|OPENAI|GOOGLE"

# Or add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
export GOOGLE_API_KEY="your-key-here"
```

### Cost Overrun

**Error**: `ValueError: Estimated cost exceeds limit`

**Solution**: Increase cost limit or reduce rounds:
```bash
# Increase limit
./run_baseline.sh --phase 1 --cost-limit 5.0

# Reduce rounds (pilot run)
./run_baseline.sh --phase 1 --rounds 15
```

## Data Format

### Round Data Structure

Each round is saved as JSON with:
```json
{
  "setup": {
    "round_id": "abc123",
    "condition_id": "phase1_older_gpt-3.5-turbo_judge",
    "storytellers": [...],
    "judge": {...},
    "fact_category": null
  },
  "stories": [...],
  "qa_exchanges": [...],
  "intermediate_guesses": [...],
  "verdict": {
    "accused_id": "B",
    "confidence": 7,
    "reasoning": "..."
  },
  "outcome": {
    "detection_correct": true,
    "fibber_id": "B",
    "accused_id": "B"
  },
  "timestamp": "2026-01-22T14:00:00",
  "duration_seconds": 12.5
}
```

### CSV Export Format

The analysis script exports CSV with columns:
- `round_id`: Unique round identifier
- `phase`: Phase number (1, 2, or 3)
- `model_category`: older, small, or flagship
- `test_model`: Model being tested
- `test_role`: judge or storyteller
- `judge_model`: Model used as judge
- `storyteller_model`: Model used for storytellers
- `fact_category`: Fact category (or "random")
- `detection_correct`: Boolean, judge identified fibber
- `judge_confidence`: 1-10 scale
- `fibber_evasion`: Boolean, fibber evaded detection
- `num_qa_exchanges`: Number of Q&A exchanges
- `duration_seconds`: Round duration
- `timestamp`: ISO timestamp

## Next Steps

After completing the baseline experiment:

1. **Analyze Results**: Look for significant differences between categories
2. **Statistical Tests**: Run ANOVA or Chi-square tests for significance
3. **Extended Experiments**: Based on baseline findings:
   - Test different temperatures
   - Vary question counts (n-shot analysis)
   - Test specific fact categories
   - Try different game types

## References

- Full Plan: See `.claude/plans/mellow-humming-biscuit.md`
- Project Documentation: See main project README
- EDSL Documentation: https://docs.expectedparrot.com

## Support

For issues or questions:
1. Check this README first
2. Review error messages carefully
3. Check the troubleshooting section
4. Review the full plan in `.claude/plans/`

---

**Last Updated**: January 22, 2026
**Version**: 1.0
**Status**: Ready for execution
