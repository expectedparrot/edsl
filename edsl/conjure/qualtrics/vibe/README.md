# Qualtrics Vibe System

The Vibe system provides AI-powered question enhancement for Qualtrics imports, automatically improving question quality through intelligent analysis and cleanup.

## Overview

When importing Qualtrics surveys, questions often contain:
- Grammar and spelling errors
- Abbreviations and informal language
- Poor formatting
- Unclear or ambiguous wording
- Inappropriate question types

The Vibe system uses AI agents to automatically identify and fix these issues, producing cleaner, more professional surveys.

## Key Features

- **AI-Powered Analysis**: Uses EDSL agents to analyze and improve questions
- **Customizable System Prompts**: Configure the AI's behavior for different use cases
- **Async Processing**: Parallel processing for better performance
- **Fallback Safety**: Falls back to original questions if processing fails
- **Configurable Concurrency**: Control processing speed and resource usage

## Basic Usage

```python
from edsl.conjure.qualtrics import ImportQualtrics
from edsl.conjure.qualtrics.vibe import VibeConfig

# Configure vibe processing
vibe_config = VibeConfig(
    enabled=True,
    system_prompt="Clean up and improve survey questions for clarity and professionalism",
    max_concurrent=3,
    temperature=0.1
)

# Import with vibe enhancement
importer = ImportQualtrics("survey.csv", vibe_config=vibe_config)
enhanced_survey = importer.survey
```

## Configuration Options

### VibeConfig Parameters

- `enabled` (bool): Enable/disable vibe processing (default: True)
- `system_prompt` (str): Instructions for the AI agent
- `max_concurrent` (int): Maximum concurrent question processing (default: 5)
- `timeout_seconds` (int): Timeout for each question analysis (default: 30)
- `model` (str): EDSL model to use (default: None, uses system default)
- `temperature` (float): AI creativity level (default: 0.1, conservative)

### System Prompt Examples

**Professional Cleanup:**
```python
system_prompt = """Fix grammar, spelling, and formatting issues.
Make questions clear and professional without changing their meaning."""
```

**Academic Style:**
```python
system_prompt = """Transform questions to meet academic research standards.
Use formal language, avoid bias, ensure precision and neutrality."""
```

**Customer Survey Style:**
```python
system_prompt = """Optimize for customer surveys. Make questions friendly,
clear, and easy to understand. Focus on customer experience language."""
```

## Architecture

### Components

1. **VibeProcessor**: Main orchestrator for question enhancement
2. **QuestionAnalyzer**: AI-powered question analysis and improvement
3. **VibeConfig**: Configuration management

### Processing Flow

1. Questions are extracted from Qualtrics CSV
2. If vibe_config is provided, questions are processed in batches
3. Each question is analyzed by an AI agent with the configured prompt
4. Improvements are applied (text cleanup, option improvements)
5. Enhanced survey is created with improved questions
6. Processing continues with normal import flow

### Error Handling

- Individual question failures don't stop the process
- Timeout protection prevents hanging on slow analyses
- Fallback to original questions ensures import success
- Detailed error logging for debugging

## Advanced Usage

### Custom Processing

```python
from edsl.conjure.qualtrics.vibe import VibeProcessor, VibeConfig
from edsl import Survey

# Direct survey processing
config = VibeConfig(enabled=True)
processor = VibeProcessor(config)

# Async processing
enhanced_survey = await processor.process_survey(original_survey)

# Sync processing
enhanced_survey = processor.process_survey_sync(original_survey)
```

### Performance Tuning

```python
# Fast processing (higher concurrency, shorter timeout)
fast_config = VibeConfig(
    max_concurrent=10,
    timeout_seconds=15,
    temperature=0.2
)

# Conservative processing (lower concurrency, longer timeout)
conservative_config = VibeConfig(
    max_concurrent=2,
    timeout_seconds=60,
    temperature=0.05
)
```

## AI Analysis Format

The AI agent receives questions in this format and returns JSON with improvements:

```json
{
    "improved_text": "What is your name?",
    "improved_options": ["Option 1", "Option 2", "Option 3"],
    "suggested_type": "QuestionMultipleChoice",
    "issues_found": ["Grammar error", "Unclear wording"],
    "recommendations": ["Fix spelling", "Add more options"],
    "confidence": 0.8,
    "reasoning": "Fixed grammar and improved clarity"
}
```

## Integration with ImportQualtrics

The vibe system integrates seamlessly with the existing import process:

1. CSV is read and parsed normally
2. Survey is built from Qualtrics data
3. **Vibe processing is applied here** (if configured)
4. Question mappings and response records are built
5. Agents are created with stored responses

This ensures vibe enhancements don't interfere with other import functionality.

## Best Practices

1. **Start Conservative**: Use low temperature (0.1) and specific prompts
2. **Test First**: Try with a few questions before processing large surveys
3. **Monitor Performance**: Adjust concurrency based on your system and model speed
4. **Custom Prompts**: Tailor system prompts to your specific survey needs
5. **Fallback Planning**: Always have original data available if vibe processing fails

## Limitations

- Requires EDSL model access for AI processing
- Processing time depends on question count and model speed
- Question type changes are suggested but not automatically applied
- Large surveys may take significant time to process
- Model costs apply for each question analysis

## Examples

See `demo_vibe_system.py` for comprehensive examples of different vibe configurations and use cases.