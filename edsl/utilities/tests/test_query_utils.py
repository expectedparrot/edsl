"""Tests for query utilities."""

import pytest
import operator

from edsl.utilities.query_utils import Field, QueryExpression, apply_filter


def test_field_creation():
    """Test creating Field objects."""
    f = Field('name')
    assert f.name == 'name'
    assert str(f) == "Field('name')"


def test_field_comparison_operators():
    """Test Field comparison operators."""
    f = Field('age')
    
    # Test all comparison operators
    expr = f > 10
    assert isinstance(expr, QueryExpression)
    assert expr.left == f
    assert expr.op == operator.gt
    assert expr.right == 10
    
    expr = f >= 10
    assert expr.op == operator.ge
    
    expr = f < 10
    assert expr.op == operator.lt
    
    expr = f <= 10
    assert expr.op == operator.le
    
    expr = f == 10
    assert expr.op == operator.eq
    
    expr = f != 10
    assert expr.op == operator.ne


def test_field_string_methods():
    """Test Field string methods."""
    f = Field('name')
    
    expr = f.startswith('A')
    assert isinstance(expr, QueryExpression)
    
    expr = f.endswith('z')
    assert isinstance(expr, QueryExpression)
    
    expr = f.contains('abc')
    assert isinstance(expr, QueryExpression)
    
    expr = f.matches(r'[A-Z].*')
    assert isinstance(expr, QueryExpression)


def test_query_expression_logical_operators():
    """Test QueryExpression logical operators."""
    age = Field('age')
    name = Field('name')
    
    expr1 = age > 10
    expr2 = name == 'John'
    
    combined = expr1 & expr2
    assert isinstance(combined, QueryExpression)
    assert combined.left == expr1
    assert combined.op == operator.and_
    assert combined.right == expr2
    
    combined = expr1 | expr2
    assert isinstance(combined, QueryExpression)
    assert combined.left == expr1
    assert combined.op == operator.or_
    assert combined.right == expr2


def test_query_expression_evaluate():
    """Test evaluating QueryExpressions."""
    obj = {'age': 25, 'name': 'John'}
    
    # Test simple comparisons
    expr = Field('age') > 20
    assert expr.evaluate(obj) is True
    
    expr = Field('age') > 30
    assert expr.evaluate(obj) is False
    
    # Test string operations
    expr = Field('name').startswith('J')
    assert expr.evaluate(obj) is True
    
    expr = Field('name').endswith('n')
    assert expr.evaluate(obj) is True
    
    expr = Field('name').matches(r'J.*n')
    assert expr.evaluate(obj) is True
    
    # Test combined expressions
    expr = (Field('age') > 20) & (Field('name') == 'John')
    assert expr.evaluate(obj) is True
    
    expr = (Field('age') > 30) | (Field('name') == 'John')
    assert expr.evaluate(obj) is True
    
    expr = (Field('age') > 30) & (Field('name') == 'John')
    assert expr.evaluate(obj) is False


def test_apply_filter():
    """Test applying filters to lists."""
    items = [
        {'age': 25, 'name': 'John'},
        {'age': 30, 'name': 'Alice'},
        {'age': 20, 'name': 'Bob'},
        {'age': 35, 'name': 'Jane'},
    ]
    
    # Filter by age
    expr = Field('age') > 25
    result = apply_filter(items, expr)
    assert len(result) == 3
    assert result[0]['name'] == 'Alice'
    assert result[1]['name'] == 'Jane'
    
    # Filter by name and age
    expr = (Field('age') <= 25) & (Field('name').startswith('J'))
    result = apply_filter(items, expr)
    assert len(result) == 1
    assert result[0]['name'] == 'John'


def test_attribute_access():
    """Test accessing attributes of objects."""
    class Person:
        def __init__(self, name, age):
            self.name = name
            self.age = age
    
    items = [
        Person('John', 25),
        Person('Alice', 30),
        Person('Bob', 20),
    ]
    
    expr = Field('age') > 25
    result = apply_filter(items, expr)
    assert len(result) == 1
    assert result[0].name == 'Alice'


def test_missing_fields():
    """Test handling of missing fields."""
    items = [
        {'age': 25, 'name': 'John'},
        {'name': 'Alice'},  # Missing 'age'
        {'age': 20},  # Missing 'name'
    ]
    
    # Should not raise errors for missing fields
    expr = Field('age') > 20
    result = apply_filter(items, expr)
    assert len(result) == 1
    assert result[0]['name'] == 'John'
    
    expr = Field('name') == 'Alice'
    result = apply_filter(items, expr)
    assert len(result) == 1
    assert 'age' not in result[0]