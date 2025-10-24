# EDSL Survey Construction Specification

This document provides a comprehensive guide for constructing basic EDSL surveys without piping or skip logic. It covers all available question types and basic survey construction patterns.

## Table of Contents

1. [Overview](#overview)
2. [Question Types](#question-types)
3. [Survey Construction](#survey-construction)
4. [Basic Examples](#basic-examples)

## Overview

EDSL (Expected Parrot Domain Specific Language) is a framework for creating and administering surveys to language models. A survey consists of one or more questions that can be asked to agents or models.

### Core Concepts

- **Question**: A single question with a specific type and parameters
- **Survey**: A collection of questions presented in order
- **Question Name**: A unique identifier for each question (must be a valid Python variable name)
- **Question Text**: The actual text of the question to be asked

## Question Types

EDSL supports multiple question types, each designed for specific response formats.

### 1. QuestionFreeText

Free-form text responses without constraints.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format
- `include_comment` (bool): Whether to include a comment field (default: True)

**Example:**
```python
from edsl import QuestionFreeText

q = QuestionFreeText(
    question_name="opinion",
    question_text="What do you think about artificial intelligence?"
)
```

### 2. QuestionMultipleChoice

Selection from a predefined list of options.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of options to choose from (can be strings, numbers, or lists)

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `use_code` (bool): If True, return option index; if False, return option text (default: False)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format
- `permissive` (bool): If True, accept answers outside the options list (default: False)

**Example:**
```python
from edsl import QuestionMultipleChoice

q = QuestionMultipleChoice(
    question_name="favorite_color",
    question_text="What is your favorite color?",
    question_options=["Red", "Blue", "Green", "Yellow"]
)
```

### 3. QuestionCheckBox

Selection of multiple options from a predefined list.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of options to choose from

**Optional Parameters:**
- `min_selections` (int): Minimum number of options that must be selected
- `max_selections` (int): Maximum number of options that can be selected
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionCheckBox

q = QuestionCheckBox(
    question_name="interests",
    question_text="Which of the following topics interest you?",
    question_options=["Science", "Technology", "Arts", "Sports"],
    min_selections=1,
    max_selections=3
)
```

### 4. QuestionNumerical

Numeric responses within an optional range.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `min_value` (float): Minimum acceptable value
- `max_value` (float): Maximum acceptable value
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionNumerical

q = QuestionNumerical(
    question_name="age",
    question_text="What is your age?",
    min_value=0,
    max_value=120
)
```

### 5. QuestionLinearScale

Linear scale with customizable range and labels.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of numeric values for the scale

**Optional Parameters:**
- `option_labels` (dict): Dictionary mapping option values to text labels
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionLinearScale

q = QuestionLinearScale(
    question_name="satisfaction",
    question_text="How satisfied are you with our service?",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "Very Dissatisfied", 5: "Very Satisfied"}
)
```

### 6. QuestionLikertFive

Standard 5-point Likert scale (Strongly Disagree to Strongly Agree).

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `question_options` (list): Custom options (defaults to standard Likert scale)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format
- `include_comment` (bool): Whether to include a comment field (default: True)

**Default Options:**
- "Strongly disagree"
- "Disagree"
- "Neutral"
- "Agree"
- "Strongly agree"

**Example:**
```python
from edsl import QuestionLikertFive

q = QuestionLikertFive(
    question_name="climate_concern",
    question_text="I am concerned about climate change."
)
```

### 7. QuestionYesNo

Simple binary yes/no response.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionYesNo

q = QuestionYesNo(
    question_name="owns_car",
    question_text="Do you own a car?"
)
```

### 8. QuestionRank

Ordering of items by preference or other criteria.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of items to rank

**Optional Parameters:**
- `num_selections` (int): Number of items to rank (if not all)
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionRank

q = QuestionRank(
    question_name="food_preferences",
    question_text="Rank these foods from most to least favorite:",
    question_options=["Pizza", "Sushi", "Tacos", "Burgers"]
)
```

### 9. QuestionList

Responses in the form of lists or arrays.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionList

q = QuestionList(
    question_name="hobbies",
    question_text="List three of your hobbies."
)
```

### 10. QuestionDict

Responses with key-value pairs.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionDict

q = QuestionDict(
    question_name="contact_info",
    question_text="Provide your contact information as a dictionary with keys: email, phone, city."
)
```

### 11. QuestionBudget

Allocation of a budget across multiple options.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of budget allocation categories
- `budget_sum` (int/float): Total budget that must be allocated

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionBudget

q = QuestionBudget(
    question_name="time_allocation",
    question_text="Allocate 100 hours across these activities:",
    question_options=["Work", "Sleep", "Exercise", "Leisure"],
    budget_sum=100
)
```

### 12. QuestionMatrix

Grid-based responses with rows and columns.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of column options for each row
- `question_items` (list): List of row items to evaluate

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionMatrix

q = QuestionMatrix(
    question_name="feature_ratings",
    question_text="Rate each feature on the following scale:",
    question_options=["Poor", "Fair", "Good", "Excellent"],
    question_items=["Design", "Usability", "Performance", "Value"]
)
```

### 13. QuestionTopK

Selection of top K items from a list.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of options to choose from
- `min_selections` (int): Minimum number of items to select
- `max_selections` (int): Maximum number of items to select

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionTopK

q = QuestionTopK(
    question_name="top_skills",
    question_text="Select your top 3 skills:",
    question_options=["Python", "JavaScript", "SQL", "R", "Java", "C++"],
    min_selections=3,
    max_selections=3
)
```

### 14. QuestionExtract

Extraction of specific information from text or data.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionExtract

q = QuestionExtract(
    question_name="extract_date",
    question_text="Extract the date mentioned in the following text: 'The meeting is scheduled for March 15, 2024.'"
)
```

### 15. QuestionMultipleChoiceWithOther

Multiple choice with an option to specify "Other" custom response.

**Required Parameters:**
- `question_name` (str): Unique identifier for the question
- `question_text` (str): The question to be asked
- `question_options` (list): List of predefined options

**Optional Parameters:**
- `include_comment` (bool): Whether to include a comment field (default: True)
- `answering_instructions` (str): Custom instructions for how to answer
- `question_presentation` (str): Custom presentation format

**Example:**
```python
from edsl import QuestionMultipleChoiceWithOther

q = QuestionMultipleChoiceWithOther(
    question_name="transportation",
    question_text="What is your primary mode of transportation?",
    question_options=["Car", "Bike", "Public Transit", "Walking"]
)
```

## Survey Construction

### Creating a Survey

There are two main ways to create a survey in EDSL:

#### Method 1: Initialize with a list of questions

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice

q1 = QuestionFreeText(
    question_name="name",
    question_text="What is your name?"
)

q2 = QuestionMultipleChoice(
    question_name="experience",
    question_text="How many years of experience do you have?",
    question_options=["0-2", "3-5", "6-10", "10+"]
)

survey = Survey(questions=[q1, q2])
```

#### Method 2: Start empty and add questions

```python
from edsl import Survey, QuestionFreeText, QuestionMultipleChoice

survey = Survey()

q1 = QuestionFreeText(
    question_name="name",
    question_text="What is your name?"
)

q2 = QuestionMultipleChoice(
    question_name="experience",
    question_text="How many years of experience do you have?",
    question_options=["0-2", "3-5", "6-10", "10+"]
)

survey = survey.add_question(q1)
survey = survey.add_question(q2)
```

### Important Notes

1. **Question Names Must Be Unique**: Each question in a survey must have a unique `question_name`.

2. **Question Names Must Be Valid Python Identifiers**: Question names must follow Python variable naming rules (start with letter or underscore, contain only letters, numbers, and underscores).

3. **Question Order**: Questions are presented in the order they are added to the survey.

4. **Immutability**: Survey methods like `add_question()` return a new Survey object rather than modifying the existing one.

## Basic Examples

### Example 1: Simple Demographics Survey

```python
from edsl import Survey, QuestionFreeText, QuestionNumerical, QuestionMultipleChoice

# Create questions
q_name = QuestionFreeText(
    question_name="name",
    question_text="What is your name?"
)

q_age = QuestionNumerical(
    question_name="age",
    question_text="What is your age?",
    min_value=18,
    max_value=100
)

q_education = QuestionMultipleChoice(
    question_name="education",
    question_text="What is your highest level of education?",
    question_options=[
        "High School",
        "Bachelor's Degree",
        "Master's Degree",
        "PhD"
    ]
)

# Create survey
survey = Survey(questions=[q_name, q_age, q_education])
```

### Example 2: Product Feedback Survey

```python
from edsl import Survey, QuestionLikertFive, QuestionCheckBox, QuestionFreeText

# Overall satisfaction
q_satisfaction = QuestionLikertFive(
    question_name="overall_satisfaction",
    question_text="I am satisfied with this product."
)

# Feature evaluation
q_features = QuestionCheckBox(
    question_name="useful_features",
    question_text="Which features do you find most useful?",
    question_options=[
        "User Interface",
        "Performance",
        "Documentation",
        "Customer Support",
        "Price"
    ]
)

# Open feedback
q_feedback = QuestionFreeText(
    question_name="additional_feedback",
    question_text="Please provide any additional feedback or suggestions."
)

# Create survey
survey = Survey(questions=[q_satisfaction, q_features, q_feedback])
```

### Example 3: Preference Survey

```python
from edsl import Survey, QuestionRank, QuestionLinearScale, QuestionYesNo

# Ranking preferences
q_rank = QuestionRank(
    question_name="vacation_destinations",
    question_text="Rank these vacation destinations from most to least preferred:",
    question_options=["Beach", "Mountains", "City", "Countryside"]
)

# Importance rating
q_importance = QuestionLinearScale(
    question_name="price_importance",
    question_text="How important is price when choosing a vacation destination?",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "Not Important", 3: "Somewhat Important", 5: "Very Important"}
)

# Binary preference
q_travel_alone = QuestionYesNo(
    question_name="travel_alone",
    question_text="Do you prefer to travel alone?"
)

# Create survey
survey = Survey(questions=[q_rank, q_importance, q_travel_alone])
```

### Example 4: Skills Assessment Survey

```python
from edsl import Survey, QuestionTopK, QuestionMatrix, QuestionBudget

# Top skills selection
q_top_skills = QuestionTopK(
    question_name="top_programming_skills",
    question_text="Select your top 3 programming languages:",
    question_options=["Python", "JavaScript", "Java", "C++", "Ruby", "Go"],
    min_selections=3,
    max_selections=3
)

# Skill proficiency matrix
q_proficiency = QuestionMatrix(
    question_name="skill_proficiency",
    question_text="Rate your proficiency in each skill area:",
    question_options=["Beginner", "Intermediate", "Advanced", "Expert"],
    question_items=["Frontend", "Backend", "Database", "DevOps"]
)

# Time allocation
q_time = QuestionBudget(
    question_name="learning_time",
    question_text="How would you allocate 40 hours per week across these learning areas?",
    question_options=["Programming", "System Design", "Testing", "Documentation"],
    budget_sum=40
)

# Create survey
survey = Survey(questions=[q_top_skills, q_proficiency, q_time])
```

### Example 5: Mixed Question Types Survey

```python
from edsl import Survey
from edsl import QuestionFreeText, QuestionMultipleChoice, QuestionCheckBox
from edsl import QuestionNumerical, QuestionLikertFive, QuestionYesNo

# Personal information
q1 = QuestionFreeText(
    question_name="job_title",
    question_text="What is your current job title?"
)

# Work experience
q2 = QuestionNumerical(
    question_name="years_experience",
    question_text="How many years of work experience do you have?",
    min_value=0,
    max_value=50
)

# Work preferences
q3 = QuestionCheckBox(
    question_name="work_preferences",
    question_text="What are your work preferences? (Select all that apply)",
    question_options=["Remote", "Hybrid", "In-office", "Flexible hours"]
)

# Job satisfaction
q4 = QuestionLikertFive(
    question_name="job_satisfaction",
    question_text="I am satisfied with my current job."
)

# Career change
q5 = QuestionYesNo(
    question_name="considering_change",
    question_text="Are you considering a career change?"
)

# Preferred industry
q6 = QuestionMultipleChoice(
    question_name="preferred_industry",
    question_text="Which industry would you most like to work in?",
    question_options=["Technology", "Healthcare", "Finance", "Education", "Manufacturing"]
)

# Create comprehensive survey
survey = Survey(questions=[q1, q2, q3, q4, q5, q6])
```

## Summary

This specification covers the basic construction of EDSL surveys without advanced features like:
- Skip logic (conditional question flow)
- Piping (referencing previous answers in questions)
- Memory management
- Question randomization
- Instructions

For these advanced features, refer to the full EDSL documentation.

### Key Points to Remember

1. Always provide unique `question_name` values for each question
2. `question_text` is required for all question types
3. Each question type has specific required and optional parameters
4. Surveys can be constructed by passing a list of questions or by adding questions one at a time
5. Question order in the survey is determined by the order of addition
