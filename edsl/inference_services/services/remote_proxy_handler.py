"""
Remote proxy handler for inference services.

This module handles communication with a remote proxy server that manages
API calls to various language model providers. It supports file uploads
through Google Cloud Storage signed URLs.
"""

from __future__ import annotations
from typing import Any, List, Optional, Dict, TYPE_CHECKING
import os
import base64
import asyncio
import json
import uuid
from datetime import datetime, timezone

import logging

# Module-level logger using standard Python logging
_logger = logging.getLogger("remote_proxy_handler")

# Global request counter
_request_counter = 0

try:
    import httpx
    import aiohttp
except ImportError:
    raise ImportError(
        "httpx and aiohttp are required for remote proxy. Install with: pip install httpx aiohttp"
    )

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as Files


class RemoteProxyHandler:
    """Handles remote proxy communication with GCS file upload support."""

    # Class-level shared HTTP client with optimized connection pooling
    _shared_client: Optional[httpx.AsyncClient] = None
    _client_lock = asyncio.Lock()

    def __init__(self, model: str, inference_service: str):
        """Initialize the remote proxy handler.

        Args:
            proxy_url: The URL of the remote proxy server
            model: The model name to use
            inference_service: The name of the inference service (e.g., "openai")
        """
        self.proxy_url = os.environ.get("EXPECTED_PARROT_URL", "http://localhost:8000")
        if "chick" in self.proxy_url:
            self.proxy_url = "https://chickapi.expectedparrot.com"
        else:
            if "localhost" not in self.proxy_url:
                self.proxy_url = "https://api.expectedparrot.com"

        self.model = model
        self.inference_service = inference_service
        self.request_id = str(uuid.uuid4())

        # Get Expected Parrot API key for authentication
        from ...coop.ep_key_handling import ExpectedParrotKeyHandler

        self.ep_key_handler = ExpectedParrotKeyHandler()
        self.ep_api_key = self.ep_key_handler.get_ep_api_key()

    @classmethod
    async def get_shared_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with optimized connection pooling."""
        if cls._shared_client is None:
            async with cls._client_lock:
                # Double-check pattern to avoid race conditions
                if cls._shared_client is None:
                    timeout = float(os.getenv("REMOTE_PROXY_TIMEOUT", "120"))
                    max_connections = int(
                        os.getenv("REMOTE_PROXY_MAX_CONNECTIONS", "1000")
                    )
                    max_keepalive = int(os.getenv("REMOTE_PROXY_MAX_KEEPALIVE", "500"))

                    # Create transport with connection limits
                    transport = httpx.AsyncHTTPTransport(
                        limits=httpx.Limits(
                            max_connections=max_connections,
                            max_keepalive_connections=max_keepalive,
                        )
                    )

                    cls._shared_client = httpx.AsyncClient(
                        timeout=timeout, transport=transport
                    )

        return cls._shared_client

    @classmethod
    async def close_shared_client(cls):
        """Close the shared HTTP client."""
        if cls._shared_client is not None:
            await cls._shared_client.aclose()
            cls._shared_client = None

    @property
    def auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for proxy requests."""
        headers = {"Content-Type": "application/json", "X-Request-ID": self.request_id}

        if self.ep_api_key:
            headers["Authorization"] = f"Bearer {self.ep_api_key}"
        else:
            headers["Authorization"] = "Bearer None"

        return headers

    async def execute_model_call(
        self,
        user_prompt: str,
        system_prompt: str = "",
        files_list: Optional[List["Files"]] = None,
        cache_key: Optional[str] = None,
        **model_params,
    ) -> Dict[str, Any]:
        """Execute a model call through the remote proxy.

        Args:
            user_prompt: The user message or input prompt
            system_prompt: The system message or context
            files_list: Optional list of files to include
            cache_key: Optional cache key for tracking
            **model_params: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            The model response from the remote proxy
        """
        # Phase 1: Prepare file uploads if needed
        gcs_file_references = []
        if files_list:
            gcs_file_references = await self._handle_file_uploads(files_list)

        # Phase 2: Prepare the execution request
        request_payload = self._build_execution_request(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            gcs_files=gcs_file_references,
            model_params=model_params,
            cache_key=cache_key,
        )

        # Phase 3: Send execution request to proxy
        result = await self._send_execution_request(request_payload)
        return result

    async def _handle_file_uploads(
        self, files_list: List["Files"]
    ) -> List[Dict[str, Any]]:
        """Handle file uploads to GCS through signed URLs.

        Args:
            files_list: List of files to upload

        Returns:
            List of GCS file references with metadata
        """
        # Step 1: Request signed URLs from proxy
        upload_metadata = self._prepare_upload_metadata(files_list)
        signed_urls = await self._request_signed_urls(upload_metadata)

        # Step 2: Upload files to GCS (only if needed)
        upload_tasks = []
        for file_entry, url_info in zip(files_list, signed_urls["upload_urls"]):
            # Only upload if file doesn't exist (has signed_url and status is upload_required)
            if (
                url_info.get("signed_url")
                and url_info.get("status") == "upload_required"
            ):
                print(f"[UPLOAD] Uploading new file: {url_info.get('filename')}")
                upload_tasks.append(self._upload_file_to_gcs(file_entry, url_info))
            elif url_info.get("status") == "file_exists":
                print(
                    f"[DEDUP] Skipping upload for existing file: {url_info.get('filename')}"
                )

        # Upload only the files that need uploading
        if upload_tasks:
            await asyncio.gather(*upload_tasks)
        else:
            print("[DEDUP] No files need uploading - all were deduplicated")

        # Step 3: Build GCS file references
        gcs_references = []
        for file_entry, url_info in zip(files_list, signed_urls["upload_urls"]):
            filename = getattr(file_entry, "path", "unknown")

            # Log appropriately based on whether file was uploaded or reused
            if url_info.get("status") == "file_exists":
                print(
                    f"[DEDUP] Using existing file {filename} at {url_info['gcs_path']}"
                )
            else:
                print(f"[UPLOAD] File {filename} available at {url_info['gcs_path']}")

            # Extract file extension
            file_extension = ""
            if "." in filename:
                file_extension = filename.rsplit(".", 1)[1].lower()

            # Get file hash for this file entry
            file_hash = file_entry.base64_string[:2000]

            gcs_references.append(
                {
                    "type": self._get_file_type(file_entry),
                    "gcs_path": url_info["gcs_path"],
                    "original_filename": filename,
                    "file_extension": file_extension,
                    "mime_type": file_entry.mime_type,
                    "processing": self._get_processing_type(file_entry),
                    "file_hash": file_hash,  # Include hash for caching after successful processing
                }
            )

        return gcs_references

    def _prepare_upload_metadata(
        self, files_list: List["Files"]
    ) -> List[Dict[str, Any]]:
        """Prepare metadata for file upload request.

        Args:
            files_list: List of files to process

        Returns:
            List of file metadata for upload request
        """
        metadata = []
        for file_entry in files_list:
            # Create file hash from first 2000 chars of base64_string
            file_hash = file_entry.base64_string[:2000]

            metadata.append(
                {
                    "filename": getattr(
                        file_entry, "filename", f"file_{len(metadata)}"
                    ),
                    "mime_type": file_entry.mime_type,
                    "file_hash": file_hash,
                }
            )

        return metadata

    async def _request_signed_urls(
        self, upload_metadata: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Request signed URLs from the proxy server.

        Args:
            upload_metadata: List of file metadata

        Returns:
            Response containing signed URLs for upload
        """
        client = await self.get_shared_client()
        response = await client.post(
            f"{self.proxy_url}/prepare-upload",
            json={"files_needed": upload_metadata, "request_id": self.request_id},
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()

    async def _upload_file_to_gcs(
        self, file_entry: "Files", url_info: Dict[str, Any]
    ) -> None:
        """Upload a single file to GCS using a signed URL.

        Args:
            file_entry: The file to upload
            url_info: Information containing the signed URL
        """
        # Decode base64 to get raw file bytes
        file_bytes = base64.b64decode(file_entry.base64_string)

        client = await self.get_shared_client()
        response = await client.put(
            url_info["signed_url"],
            content=file_bytes,
            headers={
                "Content-Type": file_entry.mime_type,
                "Content-Length": str(len(file_bytes)),
            },
        )
        response.raise_for_status()

    def _get_file_type(self, file_entry: "Files") -> str:
        """Determine the file type category.

        Args:
            file_entry: The file to categorize

        Returns:
            File type string (pdf, image, text, or other)
        """
        mime_type = file_entry.mime_type.lower()

        if "pdf" in mime_type:
            return "pdf"
        elif mime_type.startswith("image/"):
            return "image"
        elif mime_type.startswith("text/") or mime_type in [
            "application/json",
            "application/xml",
            "application/x-yaml",
        ]:
            return "text"
        else:
            # Check by extension if available
            filename = getattr(file_entry, "filename", "").lower()
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
            ]
            if any(filename.endswith(ext) for ext in text_extensions):
                return "text"
            return "other"

    def _get_processing_type(self, file_entry: "Files") -> str:
        """Determine how the file should be processed by the proxy.

        Args:
            file_entry: The file to process

        Returns:
            Processing type string
        """
        file_type = self._get_file_type(file_entry)

        if file_type == "pdf":
            # Use service-specific upload type for PDFs
            if self.inference_service == "google":
                return "upload_to_google"
            elif self.inference_service == "anthropic":
                return "base64_inline"  # Anthropic handles PDFs as base64 documents
            else:
                return "upload_to_openai"
        elif file_type == "image":
            # Use service-specific processing for images
            if self.inference_service == "google":
                return "upload_to_google"
            else:
                return "base64_inline"
        elif file_type == "text":
            return "text_inline"
        else:
            return "text_inline"  # Default to text for unknown types

    def _build_execution_request(
        self,
        user_prompt: str,
        system_prompt: str,
        gcs_files: List[Dict[str, Any]],
        model_params: Dict[str, Any],
        cache_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the execution request payload for the proxy.

        Args:
            user_prompt: The user message
            system_prompt: The system message
            gcs_files: List of GCS file references
            model_params: Model parameters
            cache_key: Optional cache key for tracking

        Returns:
            Complete request payload
        """
        # Extract specific parameters
        omit_system_prompt_if_empty = model_params.pop(
            "omit_system_prompt_if_empty", True
        )

        # Build base messages without files (proxy will handle file integration)
        messages = []

        # Add system message if needed
        if system_prompt or not omit_system_prompt_if_empty:
            messages.append({"role": "system", "content": system_prompt})

        # Add user message
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "request_id": self.request_id,
            "inference_service": self.inference_service,
            "model": self.model,
            "messages": messages,
            "parameters": model_params,
            "gcs_files": gcs_files,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "omit_system_prompt_if_empty": omit_system_prompt_if_empty,
            },
        }

        # Add cache_key if provided
        if cache_key:
            payload["cache_key"] = cache_key

        return payload

    async def _send_execution_request(
        self, request_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send the execution request to the proxy server.

        Args:
            request_payload: The complete request payload

        Returns:
            The model response from the proxy
        """
        global _request_counter
        _request_counter += 1

        timeout = aiohttp.ClientTimeout(
            total=float(os.getenv("REMOTE_PROXY_TIMEOUT", "120"))
        )
        _logger.debug(f"Sending request payload to proxy (Request #{_request_counter})")
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.proxy_url}/execute",
                    json=request_payload,
                    headers=self.auth_headers,
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    # Extract the actual model response from proxy response
                    if "response" in result:
                        return result["response"]
                    else:
                        return result
        except aiohttp.ClientError as e:
            raise
        except Exception as e:
            raise
