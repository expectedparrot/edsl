"""
The DocumentChunker module provides functionality for splitting text into manageable chunks.

This module implements the DocumentChunker class, which is responsible for chunking
text content in Scenarios based on word or line counts. This is particularly useful
when working with large text documents that need to be processed in smaller pieces,
such as for summarization, analysis, or when dealing with models that have token
limits.
"""

from __future__ import annotations
from typing import Optional, Generator
import copy
import hashlib

from .scenario import Scenario
from .scenario_list import ScenarioList


class DocumentChunker:
    """
    A utility class for splitting text in a Scenario into manageable chunks.
    
    DocumentChunker provides methods to split text content from a Scenario field into
    smaller chunks based on either word count or line count. It's primarily used by the
    Scenario.chunk() method but can also be used directly for more control over the
    chunking process.
    
    Attributes:
        scenario: The Scenario object containing the text to be chunked.
    """
    
    def __init__(self, scenario: "Scenario"):
        """
        Initialize a DocumentChunker for a specific Scenario.
        
        Args:
            scenario: The Scenario object containing the text field to be chunked.
        """
        self.scenario = scenario

    @staticmethod
    def _line_chunks(text: str, num_lines: int) -> Generator[str, None, None]:
        """
        Split text into chunks based on a specified number of lines per chunk.
        
        This method divides a text string into chunks, where each chunk contains
        at most the specified number of lines. It processes the text by splitting
        on newline characters and then groups the lines into chunks.
        
        Args:
            text: The text string to split into chunks.
            num_lines: The maximum number of lines to include in each chunk.
            
        Yields:
            String chunks containing at most num_lines lines each.
            
        Examples:
            >>> list(DocumentChunker._line_chunks("This is a test.\\nThis is a test. This is a test.", 1))
            ['This is a test.', 'This is a test. This is a test.']
            
            >>> list(DocumentChunker._line_chunks("Line 1\\nLine 2\\nLine 3\\nLine 4", 2))
            ['Line 1\\nLine 2', 'Line 3\\nLine 4']
        """
        lines = text.split("\n")
        for i in range(0, len(lines), num_lines):
            chunk = "\n".join(lines[i : i + num_lines])
            yield chunk

    @staticmethod
    def _word_chunks(text: str, num_words: int) -> Generator[str, None, None]:
        """
        Split text into chunks based on a specified number of words per chunk.
        
        This method divides a text string into chunks, where each chunk contains
        at most the specified number of words. It processes the text by splitting
        on whitespace and then groups the words into chunks.
        
        Args:
            text: The text string to split into chunks.
            num_words: The maximum number of words to include in each chunk.
            
        Yields:
            String chunks containing at most num_words words each.
            
        Examples:
            >>> list(DocumentChunker._word_chunks("This is a test.", 2))
            ['This is', 'a test.']
            
            >>> list(DocumentChunker._word_chunks("One two three four five", 3))
            ['One two three', 'four five']
        """
        words = text.split()
        for i in range(0, len(words), num_words):
            chunk = " ".join(words[i : i + num_words])
            yield chunk

    def chunk(
        self,
        field: str,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original: bool = False,
        hash_original: bool = False,
    ) -> ScenarioList:
        """
        Split a text field in the Scenario into chunks and create a ScenarioList.
        
        This method takes a field containing text from the Scenario and divides it into
        smaller chunks based on either word count or line count. For each chunk, it creates
        a new Scenario with additional metadata about the chunk.
        
        Args:
            field: The key name of the field in the Scenario to split.
            num_words: The number of words to include in each chunk. Mutually exclusive
                      with num_lines.
            num_lines: The number of lines to include in each chunk. Mutually exclusive
                      with num_words.
            include_original: If True, includes the original complete text in each chunk
                             with a "_original" suffix.
            hash_original: If True and include_original is True, stores a hash of the
                          original text instead of the full text.
        
        Returns:
            A ScenarioList containing multiple Scenarios, each with a chunk of the
            original text and metadata about the chunk.
            
        Raises:
            ValueError: If neither num_words nor num_lines is specified, or if both are.
            KeyError: If the specified field doesn't exist in the Scenario.
            
        Notes:
            - Each chunk is assigned a sequential index in the '{field}_chunk' field
            - Character and word counts for each chunk are included in '{field}_char_count'
              and '{field}_word_count' fields
            - When include_original is True, the original text is preserved in each chunk
              in the '{field}_original' field
            - The hash_original option is useful to save space while maintaining traceability
        """
        # Check if field exists in the scenario
        if field not in self.scenario:
            raise KeyError(f"Field '{field}' not found in the scenario")

        # Validate parameters
        if num_words is None and num_lines is None:
            raise ValueError("You must specify either num_words or num_lines.")

        if num_words is not None and num_lines is not None:
            raise ValueError(
                "You must specify either num_words or num_lines, but not both."
            )
            
        # Get appropriate chunks based on the specified chunking method
        if num_words is not None:
            chunks = list(self._word_chunks(self.scenario[field], num_words))
        else:  # num_lines is not None
            chunks = list(self._line_chunks(self.scenario[field], num_lines))

        # Create a new scenario for each chunk with metadata
        scenarios = []
        for i, chunk in enumerate(chunks):
            new_scenario = copy.deepcopy(self.scenario)
            new_scenario[field] = chunk
            new_scenario[field + "_chunk"] = i
            new_scenario[field + "_char_count"] = len(chunk)
            new_scenario[field + "_word_count"] = len(chunk.split())
            
            # Include the original text if requested
            if include_original:
                if hash_original:
                    # Use MD5 hash for brevity, not for cryptographic security
                    new_scenario[field + "_original"] = hashlib.md5(
                        self.scenario[field].encode()
                    ).hexdigest()
                else:
                    new_scenario[field + "_original"] = self.scenario[field]
                    
            scenarios.append(new_scenario)
            
        return ScenarioList(scenarios)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
