"""Utilities for creating and using query expressions."""

from typing import Any, Callable, Dict, List, Optional, Union
import operator
from functools import partial


class Field:
    """A class representing a field in a query expression.
    
    This class allows for pandas-like syntax for filtering lists of objects:
    agent_list.filter(Field('age') > 10)
    """
    
    def __init__(self, name: str):
        """Initialize a Field with a name.
        
        Args:
            name: The name of the field to access in the object.
        """
        self.name = name
        
    def __repr__(self) -> str:
        return f"Field('{self.name}')"

    def _apply_operation(self, op: Callable, other: Any) -> 'QueryExpression':
        return QueryExpression(self, op, other)
        
    def __lt__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.lt, other)
        
    def __le__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.le, other)
        
    def __gt__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.gt, other)
        
    def __ge__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.ge, other)
        
    def __eq__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.eq, other)
        
    def __ne__(self, other: Any) -> 'QueryExpression':
        return self._apply_operation(operator.ne, other)
        
    def __contains__(self, item: Any) -> 'QueryExpression':
        return self._apply_operation(lambda a, b: b in a, item)
        
    def contains(self, item: Any) -> 'QueryExpression':
        """Check if the field contains the specified item.
        
        This is useful for string or collection fields.
        
        Args:
            item: The item to check for.
            
        Returns:
            A QueryExpression that evaluates to True if the item is in the field.
        """
        return self._apply_operation(lambda a, b: b in a, item)
        
    def startswith(self, prefix: str) -> 'QueryExpression':
        """Check if the field starts with the specified prefix.
        
        This is useful for string fields.
        
        Args:
            prefix: The prefix to check for.
            
        Returns:
            A QueryExpression that evaluates to True if the field starts with the prefix.
        """
        return self._apply_operation(lambda a, b: a.startswith(b), prefix)
        
    def endswith(self, suffix: str) -> 'QueryExpression':
        """Check if the field ends with the specified suffix.
        
        This is useful for string fields.
        
        Args:
            suffix: The suffix to check for.
            
        Returns:
            A QueryExpression that evaluates to True if the field ends with the suffix.
        """
        return self._apply_operation(lambda a, b: a.endswith(b), suffix)
        
    def matches(self, pattern: str) -> 'QueryExpression':
        """Check if the field matches the specified regex pattern.
        
        This is useful for string fields.
        
        Args:
            pattern: The regex pattern to match against.
            
        Returns:
            A QueryExpression that evaluates to True if the field matches the pattern.
        """
        import re
        return self._apply_operation(lambda a, b: bool(re.search(b, a)), pattern)


class QueryExpression:
    """A class representing a query expression.
    
    This is created when you combine a Field with a value using operators.
    """
    
    def __init__(self, left: Any, op: Callable, right: Any):
        """Initialize a QueryExpression.
        
        Args:
            left: The left operand (typically a Field).
            op: The operator function to apply.
            right: The right operand (typically a value).
        """
        self.left = left
        self.op = op
        self.right = right
        
    def __repr__(self) -> str:
        op_map = {
            operator.lt: '<',
            operator.le: '<=',
            operator.gt: '>',
            operator.ge: '>=',
            operator.eq: '==',
            operator.ne: '!=',
            operator.and_: 'and',
            operator.or_: 'or',
        }
        op_str = op_map.get(self.op, str(self.op))
        return f"({self.left} {op_str} {self.right})"
        
    def _apply_logical_op(self, op: Callable, other: 'QueryExpression') -> 'QueryExpression':
        if not isinstance(other, QueryExpression):
            raise TypeError(f"Cannot combine QueryExpression with {type(other)}")
        return QueryExpression(self, op, other)
        
    def __and__(self, other: 'QueryExpression') -> 'QueryExpression':
        return self._apply_logical_op(operator.and_, other)
        
    def __or__(self, other: 'QueryExpression') -> 'QueryExpression':
        return self._apply_logical_op(operator.or_, other)
        
    def evaluate(self, obj: Dict[str, Any]) -> bool:
        """Evaluate the expression against an object.
        
        Args:
            obj: The object (typically a dict) to evaluate against.
            
        Returns:
            True if the expression is satisfied, False otherwise.
        """
        left_val = self._get_value(self.left, obj)
        right_val = self._get_value(self.right, obj)
        
        try:
            return self.op(left_val, right_val)
        except Exception as e:
            # Handle type mismatches and other errors
            return False
        
    def _get_value(self, operand: Any, obj: Dict[str, Any]) -> Any:
        """Get the actual value from an operand.
        
        If the operand is a Field, get its value from the object.
        If the operand is a QueryExpression, evaluate it against the object.
        Otherwise, return the operand as is.
        
        Args:
            operand: The operand to get the value from.
            obj: The object to get values from.
            
        Returns:
            The actual value of the operand.
        """
        if isinstance(operand, Field):
            # Get the value of the field from the object
            try:
                if hasattr(obj, 'get') and callable(obj.get):
                    # If obj is dict-like, use get()
                    return obj.get(operand.name)
                elif hasattr(obj, operand.name):
                    # If obj has the attribute, access it directly
                    return getattr(obj, operand.name)
                else:
                    # Try dictionary-style access
                    return obj[operand.name]
            except (KeyError, AttributeError):
                # If the field doesn't exist, return None
                return None
        elif isinstance(operand, QueryExpression):
            # Recursively evaluate nested expressions
            return operand.evaluate(obj)
        else:
            # Return literals as is
            return operand


def apply_filter(items: List[Any], expression: QueryExpression) -> List[Any]:
    """Apply a QueryExpression filter to a list of items.
    
    Args:
        items: The list of items to filter.
        expression: The QueryExpression to evaluate for each item.
        
    Returns:
        A new list containing only items that satisfy the expression.
    """
    return [item for item in items if expression.evaluate(item)]