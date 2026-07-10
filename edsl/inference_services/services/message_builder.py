from __future__ import annotations
from typing import Any, List, Optional, Dict, Union, TYPE_CHECKING
import base64
import io

if TYPE_CHECKING:
    from ....scenarios.file_store import FileStore as Files


class MessageBuilder:
    """Handles construction of messages for OpenAI API calls, including file processing and model-specific logic."""

    def __init__(
        self,
        model: str,
        files_list: Optional[List["Files"]] = None,
        user_prompt: str = "",
        system_prompt: str = "",
        omit_system_prompt_if_empty: bool = True,
        supports_files_api: bool = True,
    ):
        self.model = model
        self.files_list = files_list or []
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt
        self.omit_system_prompt_if_empty = omit_system_prompt_if_empty
        self.supports_files_api = supports_files_api

        # Model type detection
        self.is_reasoning_model = "o1" in self.model or "o3" in self.model
        self.is_o1_mini = "o1-mini" in self.model

        # Some reasoning models have no image/file (vision) input and must
        # receive text-only content with the system prompt folded into the user
        # turn. Vision-capable reasoning models (o1, o3, o4-mini) accept raw
        # files — e.g. PDFs uploaded via the Files API, which preserves images
        # and tables — exactly like regular models, so they use the normal path.
        self._text_only_reasoning_model = any(
            marker in self.model for marker in ("o1-mini", "o3-mini", "o1-preview")
        )

    def get_file_metadata(self) -> List[Dict[str, Any]]:
        """Extract metadata about files for proxy mode.

        Returns:
            List of file metadata dictionaries
        """
        metadata = []
        for file_entry in self.files_list:
            metadata.append(
                {
                    "filename": getattr(
                        file_entry, "filename", f"file_{len(metadata)}"
                    ),
                    "mime_type": file_entry.mime_type,
                    "is_pdf": self._is_pdf_file(file_entry),
                    "is_docx": self._is_docx_file(file_entry),
                    "is_text": self._is_text_file(file_entry),
                    "is_image": self._is_image_file(file_entry),
                    "has_extracted_text": hasattr(file_entry, "extracted_text")
                    and file_entry.extracted_text,
                }
            )
        return metadata

    def get_messages(self, sync_client=None) -> List[Dict[str, Any]]:
        """Construct the messages array for the OpenAI API call."""
        content = self._build_content(sync_client)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content},
        ]

        # Remove the system message when it's empty, or for text-only reasoning
        # models that fold it into the user turn instead. Vision-capable
        # reasoning models keep the system message like regular models.
        if (
            self.system_prompt == "" and self.omit_system_prompt_if_empty
        ) or self._text_only_reasoning_model:
            messages = messages[1:]

        return messages

    def _build_content(self, sync_client=None) -> Union[str, List[Dict[str, Any]]]:
        """Build the content for the user message, handling files appropriately for different model types."""
        if self._text_only_reasoning_model:
            return self._build_reasoning_model_content()
        elif not self.files_list:
            return self.user_prompt
        else:
            return self._build_regular_model_content(sync_client)

    def _build_reasoning_model_content(self) -> str:
        """Build text-only content for reasoning models (o1/o3) that don't support files."""
        content_parts = []

        # Prepend system prompt to user prompt for reasoning models
        if self.system_prompt:
            content_parts.append(self.system_prompt)

        content_parts.append(self.user_prompt)

        for file_entry in self.files_list:
            if self._is_pdf_file(file_entry):
                content_parts.append(self._process_pdf_for_reasoning_model(file_entry))
            elif self._is_docx_file(file_entry):
                content_parts.append(
                    self._process_docx_for_reasoning_model(file_entry)
                )
            elif self._is_text_file(file_entry):
                content_parts.append(self._process_text_for_reasoning_model(file_entry))
            elif self._is_image_file(file_entry):
                content_parts.append(
                    self._process_image_for_reasoning_model(file_entry)
                )
            else:
                content_parts.append(
                    self._process_other_file_for_reasoning_model(file_entry)
                )

        return "\n".join(content_parts)

    def _build_regular_model_content(self, sync_client=None) -> List[Dict[str, Any]]:
        """Build structured content for regular models that support files and images."""
        content = [{"type": "text", "text": self.user_prompt}]

        for file_entry in self.files_list:
            if self._is_pdf_file(file_entry):
                content.append(
                    self._process_pdf_for_regular_model(file_entry, sync_client)
                )
            elif self._is_docx_file(file_entry):
                content.append(self._process_docx_for_regular_model(file_entry))
            elif self._is_text_file(file_entry):
                content.append(self._process_text_for_regular_model(file_entry))
            elif self._is_image_file(file_entry):
                content.append(self._process_image_for_regular_model(file_entry))
            else:
                # Unsupported file type - add as text with warning
                filename = getattr(file_entry, "filename", "unknown")
                content.append(
                    {
                        "type": "text",
                        "text": f"[Unsupported file '{filename}' of type '{file_entry.mime_type}'. File content cannot be processed.]",
                    }
                )

        return content

    def _has_extension(self, file_entry: "Files", extensions) -> bool:
        """Check a file's extension via its ``suffix`` or ``filename``.

        FileStore objects expose ``suffix`` (e.g. ``"docx"``) rather than a
        ``filename``, and their ``mime_type`` can fall back to
        ``application/octet-stream`` when the type can't be guessed (Python's
        mimetypes registry misses .docx on some platforms). Checking the suffix
        keeps file-type detection working in that case; the filename check
        covers other file-like inputs.
        """
        exts = tuple(e.lower().lstrip(".") for e in extensions)

        suffix = (getattr(file_entry, "suffix", "") or "").lower().lstrip(".")
        if suffix in exts:
            return True

        filename = (getattr(file_entry, "filename", "") or "").lower()
        return any(filename.endswith("." + e) for e in exts)

    def _is_pdf_file(self, file_entry: "Files") -> bool:
        """Check if a file is a PDF based on MIME type, suffix, or filename."""
        return (
            file_entry.mime_type == "application/pdf"
            or file_entry.mime_type == "application/x-pdf"
            or file_entry.mime_type == "text/pdf"
            or "pdf" in file_entry.mime_type.lower()
            or self._has_extension(file_entry, ["pdf"])
        )

    def _is_docx_file(self, file_entry: "Files") -> bool:
        """Check if a file is a Word .docx document by MIME type, suffix, or filename."""
        return (
            file_entry.mime_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or self._has_extension(file_entry, ["docx"])
        )

    def _is_text_file(self, file_entry: "Files") -> bool:
        """Check if a file is a text-based file that should be included as text."""
        # Check by MIME type
        text_mime_prefixes = [
            "text/",
            "application/json",
            "application/xml",
            "application/x-yaml",
        ]
        if any(
            file_entry.mime_type.startswith(prefix) for prefix in text_mime_prefixes
        ):
            return True

        # Check by file extension
        text_extensions = [
            ".txt",
            ".md",
            ".csv",
            ".log",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".py",
            ".js",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".tex",
            ".bib",
            ".cls",
            ".sty",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".rs",
            ".go",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".ts",
            ".jsx",
            ".tsx",
            ".vue",
            ".css",
            ".scss",
            ".less",
            ".sql",
            ".r",
            ".m",
            ".jl",
            ".scala",
            ".clj",
            ".ini",
            ".cfg",
            ".conf",
            ".toml",
            ".env",
            ".properties",
        ]

        return self._has_extension(file_entry, text_extensions)

    def _is_image_file(self, file_entry: "Files") -> bool:
        """Check if a file is an image based on MIME type."""
        return file_entry.mime_type.startswith("image/")

    def decode_text_file(self, file_entry: "Files", max_chars: int = 100000) -> str:
        """Decode a text file from base64 to string. Can be used by other services."""
        filename = getattr(file_entry, "filename", "text_file")

        # If the file has extracted_text attribute, use it
        if hasattr(file_entry, "extracted_text") and file_entry.extracted_text:
            text_content = file_entry.extracted_text
        else:
            # Decode base64 content to text
            try:
                text_bytes = base64.b64decode(file_entry.base64_string)
                # Try UTF-8 first, then fall back to latin-1
                try:
                    text_content = text_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = text_bytes.decode("latin-1", errors="replace")
            except Exception as e:
                return f"[Text file '{filename}' could not be decoded: {str(e)}]"

        # Truncate very long text files
        if len(text_content) > max_chars:
            text_content = (
                text_content[:max_chars]
                + f"\n\n[Text file truncated after {max_chars} characters due to length limits]"
            )

        return text_content

    def _extract_docx_content(self, docx_bytes: bytes) -> str:
        """Extract paragraphs and tables from a .docx, preserving document order.

        The FileStore's pre-computed ``extracted_text`` only captures paragraph
        text, so we walk the document body here to also render tables (which are
        stored separately from paragraphs in the docx format).
        """
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        document = Document(io.BytesIO(docx_bytes))

        parts = []
        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                parts.append(Paragraph(child, document).text)
            elif child.tag == qn("w:tbl"):
                table = Table(child, document)
                for row in table.rows:
                    # Flatten each cell to a single line so rows stay readable.
                    cells = [" ".join(cell.text.split()) for cell in row.cells]
                    parts.append("| " + " | ".join(cells) + " |")

        return "\n".join(parts)

    def decode_docx_text(self, file_entry: "Files", max_chars: int = 100000) -> str:
        """Extract the text of a Word .docx document. Can be used by other services.

        Parses the base64 payload with python-docx to capture both paragraphs and
        tables in document order. Falls back to the FileStore's pre-computed
        ``extracted_text`` (paragraph-only) if the document can't be parsed.
        """
        filename = getattr(file_entry, "filename", "document.docx")

        try:
            docx_bytes = base64.b64decode(file_entry.base64_string)
            text_content = self._extract_docx_content(docx_bytes)
        except Exception:
            # Fall back to the precomputed paragraph text (misses tables) if the
            # payload is unavailable or python-docx can't parse it.
            if hasattr(file_entry, "extracted_text") and file_entry.extracted_text:
                text_content = file_entry.extracted_text
            else:
                return f"[DOCX file '{filename}' could not be processed.]"

        # Truncate very long documents
        if len(text_content) > max_chars:
            text_content = (
                text_content[:max_chars]
                + f"\n\n[DOCX truncated after {max_chars} characters due to length limits]"
            )

        return text_content

    def _process_docx_for_regular_model(self, file_entry: "Files") -> Dict[str, Any]:
        """Process .docx files for regular models by including their extracted text."""
        filename = getattr(file_entry, "filename", "document.docx")
        text_content = self.decode_docx_text(file_entry, max_chars=100000)

        return {
            "type": "text",
            "text": f"\n--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---\n",
        }

    def _process_docx_for_reasoning_model(self, file_entry: "Files") -> str:
        """Process .docx files for reasoning models by including their extracted text."""
        filename = getattr(file_entry, "filename", "document.docx")
        text_content = self.decode_docx_text(
            file_entry, max_chars=50000
        )  # Lower limit for reasoning models

        return f"\n--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---\n"

    def _process_pdf_for_reasoning_model(self, file_entry: "Files") -> str:
        """Process PDF files for reasoning models by extracting text content."""
        filename = getattr(file_entry, "filename", "document.pdf")

        if hasattr(file_entry, "extracted_text") and file_entry.extracted_text:
            # Truncate very long PDFs to avoid overwhelming reasoning models
            extracted_text = file_entry.extracted_text
            max_chars = 50000  # Limit to ~50k chars (roughly 12-15k tokens)
            if len(extracted_text) > max_chars:
                extracted_text = (
                    extracted_text[:max_chars]
                    + f"\n\n[PDF truncated after {max_chars} characters due to length limits]"
                )

            return f"\n--- PDF Content from '{filename}' ---\n{extracted_text}\n--- End of PDF Content ---\n"
        else:
            return f"\n[PDF file '{filename}' could not be processed - no extracted text available. Please extract the text content manually and include it in your prompt.]"

    def _process_image_for_reasoning_model(self, file_entry: "Files") -> str:
        """Process image files for reasoning models (not supported)."""
        filename = getattr(file_entry, "filename", "image")
        return f"\n[Image file '{filename}' provided but o1 models do not support image inputs. Please describe the image content in text form.]"

    def _process_other_file_for_reasoning_model(self, file_entry: "Files") -> str:
        """Process other file types for reasoning models."""
        filename = getattr(file_entry, "filename", "unknown")
        return f"\n[File '{filename}' of type '{file_entry.mime_type}' provided but o1 models only support text inputs. Please extract relevant content and include as text.]"

    def _process_pdf_for_regular_model(
        self, file_entry: "Files", sync_client=None
    ) -> Dict[str, Any]:
        """Process PDF files for regular models using file upload or base64 inline."""
        # For services that don't support the OpenAI Files API (e.g., xAI),
        # send the PDF as base64-encoded document content inline.
        if not self.supports_files_api:
            return self._process_pdf_as_base64(file_entry)

        try:
            # Convert base64 back to bytes for upload
            pdf_bytes = base64.b64decode(file_entry.base64_string)
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_file.name = getattr(file_entry, "filename", "document.pdf")

            # Use sync client for file upload (files.create is not async in OpenAI client)
            if sync_client is None:
                raise Exception("Sync client required for PDF upload")

            uploaded_file = sync_client.files.create(file=pdf_file, purpose="user_data")

            return {
                "type": "file",
                "file": {
                    "file_id": uploaded_file.id,
                },
            }
        except Exception as e:
            # Fallback to base64 inline
            return self._process_pdf_as_base64(file_entry)

    def _process_pdf_as_base64(self, file_entry: "Files") -> Dict[str, Any]:
        """Send a PDF as base64-encoded content for services without Files API support."""
        try:
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:application/pdf;base64,{file_entry.base64_string}",
                },
            }
        except Exception:
            # Final fallback: extract text if possible
            filename = getattr(file_entry, "filename", "document.pdf")
            return {
                "type": "text",
                "text": f"[PDF file '{filename}' could not be processed.]",
            }

    def _process_text_for_regular_model(self, file_entry: "Files") -> Dict[str, Any]:
        """Process text files for regular models by including their content as text."""
        filename = getattr(file_entry, "filename", "text_file")
        text_content = self.decode_text_file(file_entry, max_chars=100000)

        return {
            "type": "text",
            "text": f"\n--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---\n",
        }

    def _process_text_for_reasoning_model(self, file_entry: "Files") -> str:
        """Process text files for reasoning models."""
        filename = getattr(file_entry, "filename", "text_file")
        text_content = self.decode_text_file(
            file_entry, max_chars=50000
        )  # Lower limit for reasoning models

        return f"\n--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---\n"

    def _process_image_for_regular_model(self, file_entry: "Files") -> Dict[str, Any]:
        """Process image files for regular models."""
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{file_entry.mime_type};base64,{file_entry.base64_string}"
            },
        }
