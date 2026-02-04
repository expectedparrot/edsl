"""
Transcript module for generating human-readable interview transcripts.

This module provides classes for displaying Result objects as formatted
transcripts with support for terminal (Rich), plain text, and HTML output.
"""

from .transcript import Transcript, generate_transcript
from .transcripts import Transcripts

__all__ = ["Transcript", "Transcripts", "generate_transcript"]
