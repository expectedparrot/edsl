"""
Module for generating transcripts from Results objects (multiple Result objects).

This module provides the Transcripts class (plural) which displays interview transcripts
across multiple Results, allowing navigation between different respondents while keeping
the same question in focus.

Note: This module re-exports from the transcript subpackage for backward compatibility.
"""

from .transcript import Transcripts

__all__ = ["Transcripts"]
