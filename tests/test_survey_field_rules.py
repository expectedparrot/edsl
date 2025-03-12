"""Tests for the Field-based rule expressions in Survey module."""

import pytest
from edsl import Survey, QuestionFreeText, Field
from edsl.surveys.rules.rule import Rule
from edsl.surveys.exceptions import SurveyRuleCannotEvaluateError


def test_rule_with_field_expression_basic():
    """Test creating a rule with a Field-based expression."""
    # Simple equality check
    rule = Rule(
        current_q=1,
        expression=Field('q1.answer') == 'yes',
        next_q=3,
        question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3},
        priority=1
    )
    
    # Verify the expression was converted to Jinja2 format
    assert "{{" in rule.expression
    assert "}}" in rule.expression
    
    # Test evaluation
    assert rule.evaluate({'q1.answer': 'yes'}) is True
    assert rule.evaluate({'q1.answer': 'no'}) is False


def test_rule_with_field_expression_complex():
    """Test creating a rule with a complex Field-based expression."""
    # Complex expression with logical operators
    rule = Rule(
        current_q=2,
        expression=(Field('q1.answer') == 'yes') & (Field('q2.answer') > 5),
        next_q=4,
        question_name_to_index={'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4},
        priority=1
    )
    
    # Verify expression conversion
    assert "{{" in rule.expression
    assert "}}" in rule.expression
    assert "and" in rule.expression
    
    # Test evaluation
    assert rule.evaluate({'q1.answer': 'yes', 'q2.answer': 10}) is True
    assert rule.evaluate({'q1.answer': 'yes', 'q2.answer': 3}) is False
    assert rule.evaluate({'q1.answer': 'no', 'q2.answer': 10}) is False


def test_rule_with_field_string_operations():
    """Test Field-based string operations in rules."""
    # Test startswith
    rule1 = Rule(
        current_q=1,
        expression=Field('q1.answer').startswith('test'),
        next_q=2,
        question_name_to_index={'q1': 1, 'q2': 2},
        priority=1
    )
    assert rule1.evaluate({'q1.answer': 'test123'}) is True
    assert rule1.evaluate({'q1.answer': 'not_test'}) is False
    
    # Test endswith
    rule2 = Rule(
        current_q=1,
        expression=Field('q1.answer').endswith('.txt'),
        next_q=2,
        question_name_to_index={'q1': 1, 'q2': 2},
        priority=1
    )
    assert rule2.evaluate({'q1.answer': 'file.txt'}) is True
    assert rule2.evaluate({'q1.answer': 'file.pdf'}) is False
    
    # Test contains
    rule3 = Rule(
        current_q=1,
        expression=Field('q1.answer').contains('key'),
        next_q=2,
        question_name_to_index={'q1': 1, 'q2': 2},
        priority=1
    )
    assert rule3.evaluate({'q1.answer': 'keyboard'}) is True
    assert rule3.evaluate({'q1.answer': 'mouse'}) is False


def test_rule_with_field_in_survey():
    """Test Field-based rules in a complete Survey."""
    # Create a simple survey with Field-based rules
    survey = Survey(name="Test Survey")
    
    # Create questions with the correct parameters
    q1 = QuestionFreeText(question_name="q1", question_text="What's your favorite color?")
    q2 = QuestionFreeText(question_name="q2", question_text="Do you like red?")
    q3 = QuestionFreeText(question_name="q3", question_text="Do you like blue?")
    q4 = QuestionFreeText(question_name="q4", question_text="Thank you for your input")
    
    # Add questions in sequence without explicit indexes
    survey.add_question(q1)  # Will be index 0
    survey.add_question(q2)  # Will be index 1
    survey.add_question(q3)  # Will be index 2
    survey.add_question(q4)  # Will be index 3
    
    # Add Field-based rule: If favorite color contains 'red', skip q2
    survey.add_skip_rule(q2, Field('q1.answer').contains('red'))
    
    # Add Field-based rule: If q3 answer is 'yes', end survey
    from edsl.surveys.base import EndOfSurvey
    survey.add_rule(q3, Field('q3.answer') == 'yes', EndOfSurvey)
    
    # Don't check the exact number of rules, as default navigation rules are added automatically
    # Just verify our custom rules exist 
    assert any("'red' in {{ q1.answer }}" in rule.expression for rule in survey.rule_collection)
    assert any("{{ q3.answer }} == 'yes'" in rule.expression for rule in survey.rule_collection)
    
    # Test survey flow using gen_path_through_survey with proper generator interaction
    
    # Case 1: User answers "red" to q1 and "yes" to q3
    path = []
    gen = survey.gen_path_through_survey()
    
    try:
        # Get first question
        q = next(gen)
        path.append(q)
        
        # Answer q1 with "red" - this should skip q2
        q = gen.send({f"{q.question_name}.answer": "red"})
        path.append(q)
        
        # Answer q3 with "yes" - this should end the survey
        try:
            q = gen.send({f"{q.question_name}.answer": "yes"})
            path.append(q)  # This won't execute if EndOfSurvey is triggered
        except StopIteration:
            # Expected because of the EndOfSurvey rule
            pass
    except StopIteration:
        pass
    
    # Should skip q2 because q1 answer contains 'red', and stop after q3 due to "yes" answer
    assert [q.question_name for q in path] == ['q1', 'q3']

    # Case 2: User answers "blue" to q1, "yes" to q2, and "no" to q3
    path = []
    gen = survey.gen_path_through_survey()
    
    try:
        # Get first question
        q = next(gen)
        path.append(q)
        
        # Answer q1 with "blue" - should go to q2
        q = gen.send({f"{q.question_name}.answer": "blue"})
        path.append(q)
        
        # Answer q2 with "yes"
        q = gen.send({f"{q.question_name}.answer": "yes"})
        path.append(q)
        
        # Answer q3 with "no" - should not end the survey
        q = gen.send({f"{q.question_name}.answer": "no"})
        path.append(q)
        
        # Q4 should be the end of the survey
        try:
            q = gen.send({f"{q.question_name}.answer": "thanks"})
            path.append(q)  # Should not execute because survey ends after q4
        except StopIteration:
            # Expected at the end of the survey
            pass
    except StopIteration:
        pass
    
    # Should visit all questions since no skips or ends should be triggered
    assert [q.question_name for q in path] == ['q1', 'q2', 'q3', 'q4']


def test_rule_conversion_to_dict():
    """Test serialization of Rule with Field-based expression."""
    # Create a rule with Field expression
    rule = Rule(
        current_q=1,
        expression=Field('q1.answer') == 'yes',
        next_q=2,
        question_name_to_index={'q1': 1, 'q2': 2},
        priority=1
    )
    
    # Convert to dict and back
    rule_dict = rule.to_dict()
    new_rule = Rule.from_dict(rule_dict)
    
    # Verify the expression was preserved
    assert "{{" in new_rule.expression
    assert "}}" in new_rule.expression
    assert new_rule.evaluate({'q1.answer': 'yes'}) is True
    assert new_rule.evaluate({'q1.answer': 'no'}) is False