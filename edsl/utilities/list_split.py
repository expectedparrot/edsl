"""Utility function for splitting list-like objects into random groups."""

import random


def list_split(items, frac_left, seed=None):
    """Split a list-like object into two groups randomly.

    Randomly assigns items from a list-like object to two groups (left and right)
    based on a specified fraction. The function attempts to preserve the type of
    the input container.

    Args:
        items: A list-like object that supports list methods (e.g., list, UserList, AgentList)
        frac_left: Fraction (0-1) of items to assign to left group
        seed: Optional random seed for reproducibility

    Returns:
        tuple: (left, right) where left and right are instances of the same type as items
               if possible, otherwise lists

    Raises:
        ValueError: If frac_left is not between 0 and 1

    Examples:
        Basic usage with a regular list:

        >>> items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        >>> left, right = list_split(items, 0.7, seed=42)
        >>> len(left)
        7
        >>> len(right)
        3

        Using with a seed for reproducibility:

        >>> items = ['a', 'b', 'c', 'd', 'e']
        >>> left1, right1 = list_split(items, 0.6, seed=123)
        >>> left2, right2 = list_split(items, 0.6, seed=123)
        >>> left1 == left2
        True

        Edge cases:

        >>> items = [1, 2, 3]
        >>> left, right = list_split(items, 0.0, seed=1)
        >>> len(left), len(right)
        (0, 3)
        >>> left, right = list_split(items, 1.0, seed=1)
        >>> len(left), len(right)
        (3, 0)
    """
    if not 0 <= frac_left <= 1:
        raise ValueError("frac_left must be between 0 and 1")

    # Set random seed if provided
    if seed is not None:
        random.seed(seed)

    # Calculate number of items for left group
    n_total = len(items)
    n_left = round(n_total * frac_left)

    # Create indices and shuffle them
    indices = list(range(n_total))
    random.shuffle(indices)

    # Split indices
    left_indices = set(indices[:n_left])

    # Split items based on indices
    left_items = [item for i, item in enumerate(items) if i in left_indices]
    right_items = [item for i, item in enumerate(items) if i not in left_indices]

    # Try to preserve the type of the input
    try:
        left = type(items)(left_items)
        right = type(items)(right_items)
    except Exception:
        left = left_items
        right = right_items

    return left, right
