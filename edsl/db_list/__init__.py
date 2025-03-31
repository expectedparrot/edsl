"""
SQLite-backed list module that behaves like a Python list but with memory usage limits.

This module provides a drop-in replacement for Python's built-in list that automatically 
offloads data to SQLite when memory usage exceeds a configured threshold.
"""

from .sqlite_list import SQLiteList

__all__ = ["SQLiteList"]