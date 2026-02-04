"""
Module for generating transcripts from Result objects.

This module provides functionality to convert Result objects into human-readable
transcripts showing questions, options (if any), and answers. The Transcript class
provides different display formats for terminal (rich formatting) vs Jupyter
notebooks (HTML).

Note: This module re-exports from the transcript subpackage for backward compatibility.
"""

from .transcript import Transcript, generate_transcript

__all__ = ["Transcript", "generate_transcript"]
