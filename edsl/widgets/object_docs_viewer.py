"""
EDSL Object Documentation Viewer Widget

An anywidget that displays documentation for public methods of any EDSL object.
"""

import inspect
import re
import math
from collections import Counter
from typing import Any, Dict, List
import traitlets

from .base_widget import EDSLBaseWidget


class SafeObjectTrait(traitlets.Any):
    """A trait that safely handles object comparison without calling __eq__."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _compare(self, old, new):
        """Override comparison to avoid calling __eq__ on objects."""
        # Use 'is' comparison instead of '==' to avoid __eq__ issues
        return old is new


class ObjectDocsViewerWidget(EDSLBaseWidget):
    """
    A widget that displays documentation for public methods of an EDSL object.

    Usage:
        widget = ObjectDocsViewerWidget(my_edsl_object)
        widget
    """

    widget_short_name = "object_docs_viewer"

    # Widget properties
    edsl_object = SafeObjectTrait(allow_none=True)
    object_class_name = traitlets.Unicode("").tag(sync=True)
    methods_data = traitlets.List().tag(sync=True)
    selected_method = traitlets.Unicode("").tag(sync=True)
    method_documentation = traitlets.Dict().tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)

    # Search functionality
    search_query = traitlets.Unicode("").tag(sync=True)
    search_results = traitlets.List().tag(sync=True)
    is_searching = traitlets.Bool(False).tag(sync=True)

    def __init__(self, edsl_object=None, **kwargs):
        super().__init__(**kwargs)
        if edsl_object is not None:
            self.set_edsl_object(edsl_object)

    def set_edsl_object(self, obj: Any):
        """Set the EDSL object and extract its public methods."""
        try:
            self.edsl_object = obj
            self.object_class_name = obj.__class__.__name__ if obj is not None else ""
            self.error_message = ""
            self._extract_methods()
        except Exception as e:
            self.error_message = f"Error setting object: {str(e)}"
            self.methods_data = []
            self.object_class_name = ""

    def _extract_methods(self):
        """Extract public methods from the EDSL object."""
        if not self.edsl_object:
            self.methods_data = []
            return

        try:
            methods = []

            # Get all public methods (not starting with _)
            for name in dir(self.edsl_object):
                if name.startswith("_"):
                    continue

                attr = getattr(self.edsl_object, name)
                if callable(attr):
                    # Get method signature
                    try:
                        sig = inspect.signature(attr)
                        signature_str = f"{name}{sig}"
                    except (ValueError, TypeError):
                        signature_str = f"{name}(...)"

                    # Get docstring
                    docstring = inspect.getdoc(attr) or "No documentation available."

                    methods.append(
                        {
                            "name": name,
                            "signature": signature_str,
                            "docstring": docstring,
                            "has_examples": ">>>" in docstring,
                        }
                    )

            # Sort methods alphabetically
            methods.sort(key=lambda x: x["name"])
            self.methods_data = methods

            # Auto-select first method if available
            if methods and not self.selected_method:
                self.selected_method = methods[0]["name"]
                self._update_method_documentation()

        except Exception as e:
            self.error_message = f"Error extracting methods: {str(e)}"
            self.methods_data = []

    @traitlets.observe("selected_method")
    def _on_method_selected(self, change):
        """Handle method selection change."""
        self._update_method_documentation()

    @traitlets.observe("search_query")
    def _on_search_query_changed(self, change):
        """Handle search query change."""
        query = change["new"].strip()
        if query:
            self.is_searching = True
            self._perform_search(query)
        else:
            self.is_searching = False
            self.search_results = []

    def _update_method_documentation(self):
        """Update the documentation for the selected method."""
        if not self.selected_method or not self.methods_data:
            self.method_documentation = {}
            return

        try:
            # Find the selected method data
            method_data = None
            for method in self.methods_data:
                if method["name"] == self.selected_method:
                    method_data = method
                    break

            if not method_data:
                self.method_documentation = {}
                return

            # Format the documentation
            formatted_doc = self._format_docstring(method_data["docstring"])

            self.method_documentation = {
                "name": method_data["name"],
                "signature": method_data["signature"],
                "formatted_docstring": formatted_doc,
                "has_examples": method_data["has_examples"],
            }

        except Exception as e:
            self.error_message = f"Error updating documentation: {str(e)}"
            self.method_documentation = {}

    def _format_docstring(self, docstring: str) -> Dict[str, Any]:
        """Format a docstring, separating description, parameters, examples, etc."""
        if not docstring:
            return {"description": "No documentation available.", "examples": []}

        lines = docstring.split("\n")

        # Initialize sections
        description_lines = []
        examples = []
        current_example = []
        in_example = False

        for line in lines:
            stripped = line.strip()

            # Check if this is an example line (starts with >>> or ...)
            if stripped.startswith(">>>") or stripped.startswith("..."):
                if not in_example:
                    in_example = True
                    if current_example:
                        examples.append("\n".join(current_example))
                        current_example = []
                current_example.append(line)
            elif (
                in_example
                and stripped
                and not stripped.startswith(">>>")
                and not stripped.startswith("...")
            ):
                # This might be output from the example
                current_example.append(line)
            else:
                # End of example block
                if in_example and current_example:
                    examples.append("\n".join(current_example))
                    current_example = []
                    in_example = False

                # Regular description line
                if not in_example:
                    description_lines.append(line)

        # Add any remaining example
        if current_example:
            examples.append("\n".join(current_example))

        # Clean up description
        description = "\n".join(description_lines).strip()

        # Extract parameters section if present
        params_match = re.search(
            r"Parameters:?\n-+\n(.*?)(?=\n\n|\n[A-Z]|\n-+|$)", description, re.DOTALL
        )
        parameters = params_match.group(1).strip() if params_match else ""

        # Extract returns section if present
        returns_match = re.search(
            r"Returns:?\n-+\n(.*?)(?=\n\n|\n[A-Z]|\n-+|$)", description, re.DOTALL
        )
        returns = returns_match.group(1).strip() if returns_match else ""

        return {
            "description": description,
            "parameters": parameters,
            "returns": returns,
            "examples": examples,
        }

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25."""
        # Convert to lowercase and split on non-alphanumeric characters
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def _calculate_bm25_score(
        self,
        query_tokens: List[str],
        doc_tokens: List[str],
        corpus_stats: Dict[str, Any],
    ) -> float:
        """Calculate BM25 score for a document given query tokens."""
        k1, b = 1.5, 0.75  # BM25 parameters

        doc_len = len(doc_tokens)
        avg_doc_len = corpus_stats["avg_doc_len"]

        doc_term_freq = Counter(doc_tokens)
        score = 0.0

        for term in query_tokens:
            if term in doc_term_freq:
                tf = doc_term_freq[term]
                df = corpus_stats["doc_freq"].get(term, 0)
                idf = math.log((corpus_stats["total_docs"] - df + 0.5) / (df + 0.5))

                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)

        return score

    def _highlight_matches(
        self, text: str, query_tokens: List[str]
    ) -> List[Dict[str, Any]]:
        """Highlight matching terms in text and return as structured data."""
        if not query_tokens:
            return [{"text": text, "highlight": False}]

        # Create pattern to match query terms (case insensitive)
        pattern = r"\b(" + "|".join(re.escape(token) for token in query_tokens) + r")\b"

        result = []
        last_end = 0

        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Add non-matching text before this match
            if match.start() > last_end:
                result.append(
                    {"text": text[last_end : match.start()], "highlight": False}
                )

            # Add the matching text with highlight
            result.append({"text": match.group(), "highlight": True})

            last_end = match.end()

        # Add remaining non-matching text
        if last_end < len(text):
            result.append({"text": text[last_end:], "highlight": False})

        return result

    def _perform_search(self, query: str):
        """Perform BM25 search across all method docstrings."""
        if not self.methods_data or not query.strip():
            self.search_results = []
            return

        try:
            query_tokens = self._tokenize(query)
            if not query_tokens:
                self.search_results = []
                return

            # Prepare corpus for BM25
            documents = []
            doc_tokens_list = []

            for method in self.methods_data:
                # Combine method name, signature, and docstring for search
                searchable_text = (
                    f"{method['name']} {method['signature']} {method['docstring']}"
                )
                documents.append(searchable_text)
                doc_tokens_list.append(self._tokenize(searchable_text))

            # Calculate corpus statistics
            total_docs = len(documents)
            total_tokens = sum(len(tokens) for tokens in doc_tokens_list)
            avg_doc_len = total_tokens / total_docs if total_docs > 0 else 0

            # Calculate document frequency for each term
            doc_freq = Counter()
            for tokens in doc_tokens_list:
                unique_tokens = set(tokens)
                for token in unique_tokens:
                    doc_freq[token] += 1

            corpus_stats = {
                "total_docs": total_docs,
                "avg_doc_len": avg_doc_len,
                "doc_freq": doc_freq,
            }

            # Calculate BM25 scores
            results = []
            for i, (method, doc_tokens) in enumerate(
                zip(self.methods_data, doc_tokens_list)
            ):
                score = self._calculate_bm25_score(
                    query_tokens, doc_tokens, corpus_stats
                )

                if score > 0:  # Only include methods with matches
                    # Highlight matches in different parts
                    highlighted_name = self._highlight_matches(
                        method["name"], query_tokens
                    )
                    highlighted_signature = self._highlight_matches(
                        method["signature"], query_tokens
                    )
                    highlighted_docstring = self._highlight_matches(
                        method["docstring"], query_tokens
                    )

                    results.append(
                        {
                            "method_name": method["name"],
                            "score": score,
                            "highlighted_name": highlighted_name,
                            "highlighted_signature": highlighted_signature,
                            "highlighted_docstring": highlighted_docstring,
                            "has_examples": method["has_examples"],
                        }
                    )

            # Sort by BM25 score (descending)
            results.sort(key=lambda x: x["score"], reverse=True)

            # Limit results to top 20
            self.search_results = results[:20]

        except Exception as e:
            self.error_message = f"Error performing search: {str(e)}"
            self.search_results = []
