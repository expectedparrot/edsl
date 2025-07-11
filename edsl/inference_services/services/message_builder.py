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
    ):
        self.model = model
        self.files_list = files_list or []
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt
        self.omit_system_prompt_if_empty = omit_system_prompt_if_empty

        # Model type detection
        self.is_reasoning_model = "o1" in self.model or "o3" in self.model
        self.is_o1_mini = "o1-mini" in self.model

    def get_messages(self, sync_client=None) -> List[Dict[str, Any]]:
        """Construct the messages array for the OpenAI API call."""
        content = self._build_content(sync_client)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content},
        ]

        # Remove system message for reasoning models or when system prompt is empty
        if (
            self.system_prompt == "" and self.omit_system_prompt_if_empty
        ) or self.is_reasoning_model:
            messages = messages[1:]

        return messages

    def _build_content(self, sync_client=None) -> Union[str, List[Dict[str, Any]]]:
        """Build the content for the user message, handling files appropriately for different model types."""
        if self.is_reasoning_model:
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
            elif file_entry.mime_type.startswith("image/"):
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
            else:
                content.append(self._process_image_for_regular_model(file_entry))

        return content

    def _is_pdf_file(self, file_entry: "Files") -> bool:
        """Check if a file is a PDF based on MIME type or filename."""
        return (
            file_entry.mime_type == "application/pdf"
            or file_entry.mime_type == "application/x-pdf"
            or file_entry.mime_type == "text/pdf"
            or "pdf" in file_entry.mime_type.lower()
            or (
                hasattr(file_entry, "filename")
                and getattr(file_entry, "filename", "").lower().endswith(".pdf")
            )
        )

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
        """Process PDF files for regular models using file upload."""
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
            # Fallback approach: Try base64 PDF format (some users report this working)
            try:
                return {
                    "type": "text",
                    "text": f"Here is a PDF document (base64): data:application/pdf;base64,{file_entry.base64_string[:100]}... [truncated for brevity]",
                }
            except Exception as fallback_error:
                # Final fallback: add error message explaining the issue
                return {
                    "type": "text",
                    "text": f"[PDF file could not be processed. Upload error: {str(e)}. Fallback error: {str(fallback_error)}. Please ensure the file is a valid PDF and OpenAI API supports PDF uploads.]",
                }

    def _process_image_for_regular_model(self, file_entry: "Files") -> Dict[str, Any]:
        """Process image files for regular models."""
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{file_entry.mime_type};base64,{file_entry.base64_string}"
            },
        }
