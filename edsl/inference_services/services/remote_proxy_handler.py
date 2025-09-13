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
from datetime import datetime

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required for remote proxy. Install with: pip install httpx")

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as Files


class RemoteProxyHandler:
    """Handles remote proxy communication with GCS file upload support."""
    
    def __init__(
        self,
        proxy_url: str,
        model: str,
        api_token: str,
        inference_service: str
    ):
        """Initialize the remote proxy handler.
        
        Args:
            proxy_url: The URL of the remote proxy server
            model: The model name to use
            api_token: The API token for the inference service
            inference_service: The name of the inference service (e.g., "openai")
        """
        self.proxy_url = proxy_url.rstrip("/")
        self.model = model
        self.api_token = api_token
        self.inference_service = inference_service
        self.request_id = str(uuid.uuid4())
        
    async def execute_model_call(
        self,
        user_prompt: str,
        system_prompt: str = "",
        files_list: Optional[List["Files"]] = None,
        **model_params
    ) -> Dict[str, Any]:
        """Execute a model call through the remote proxy.
        
        Args:
            user_prompt: The user message or input prompt
            system_prompt: The system message or context
            files_list: Optional list of files to include
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
            model_params=model_params
        )
        
        # Phase 3: Send execution request to proxy
        return await self._send_execution_request(request_payload)
    
    async def _handle_file_uploads(self, files_list: List["Files"]) -> List[Dict[str, Any]]:
        """Handle file uploads to GCS through signed URLs.
        
        Args:
            files_list: List of files to upload
            
        Returns:
            List of GCS file references with metadata
        """
        # Step 1: Request signed URLs from proxy
        upload_metadata = self._prepare_upload_metadata(files_list)
        signed_urls = await self._request_signed_urls(upload_metadata)
        
        # Step 2: Upload files to GCS
        upload_tasks = []
        for file_entry, url_info in zip(files_list, signed_urls["upload_urls"]):
            upload_tasks.append(
                self._upload_file_to_gcs(file_entry, url_info)
            )
        
        await asyncio.gather(*upload_tasks)
        
        # Step 3: Build GCS file references
        gcs_references = []
        for file_entry, url_info in zip(files_list, signed_urls["upload_urls"]):
            gcs_references.append({
                "type": self._get_file_type(file_entry),
                "gcs_path": url_info["gcs_path"],
                "original_filename": getattr(file_entry, "filename", "unknown"),
                "mime_type": file_entry.mime_type,
                "processing": self._get_processing_type(file_entry)
            })
        
        return gcs_references
    
    def _prepare_upload_metadata(self, files_list: List["Files"]) -> List[Dict[str, Any]]:
        """Prepare metadata for file upload request.
        
        Args:
            files_list: List of files to process
            
        Returns:
            List of file metadata for upload request
        """
        metadata = []
        for file_entry in files_list:
            # Calculate file size from base64
            file_size = len(base64.b64decode(file_entry.base64_string))
            
            metadata.append({
                "filename": getattr(file_entry, "filename", f"file_{len(metadata)}"),
                "size": file_size,
                "mime_type": file_entry.mime_type
            })
        
        return metadata
    
    async def _request_signed_urls(self, upload_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Request signed URLs from the proxy server.
        
        Args:
            upload_metadata: List of file metadata
            
        Returns:
            Response containing signed URLs for upload
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.proxy_url}/prepare-upload",
                json={
                    "files_needed": upload_metadata,
                    "request_id": self.request_id
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Request-ID": self.request_id
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def _upload_file_to_gcs(self, file_entry: "Files", url_info: Dict[str, Any]) -> None:
        """Upload a single file to GCS using a signed URL.
        
        Args:
            file_entry: The file to upload
            url_info: Information containing the signed URL
        """
        # Decode base64 to get raw file bytes
        file_bytes = base64.b64decode(file_entry.base64_string)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.put(
                url_info["signed_url"],
                content=file_bytes,
                headers={
                    "Content-Type": file_entry.mime_type,
                    "Content-Length": str(len(file_bytes))
                }
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
            "application/json", "application/xml", "application/x-yaml"
        ]:
            return "text"
        else:
            # Check by extension if available
            filename = getattr(file_entry, "filename", "").lower()
            text_extensions = [".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", 
                             ".xml", ".html", ".py", ".js", ".java", ".cpp", ".c"]
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
            return "upload_to_openai"
        elif file_type == "image":
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
        model_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the execution request payload for the proxy.
        
        Args:
            user_prompt: The user message
            system_prompt: The system message
            gcs_files: List of GCS file references
            model_params: Model parameters
            
        Returns:
            Complete request payload
        """
        # Extract specific parameters
        omit_system_prompt_if_empty = model_params.pop("omit_system_prompt_if_empty", True)
        
        # Build base messages without files (proxy will handle file integration)
        messages = []
        
        # Add system message if needed
        if system_prompt or not omit_system_prompt_if_empty:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        return {
            "request_id": self.request_id,
            "inference_service": self.inference_service,
            "model": self.model,
            "api_token": self.api_token,
            "messages": messages,
            "parameters": model_params,
            "gcs_files": gcs_files,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "omit_system_prompt_if_empty": omit_system_prompt_if_empty
            }
        }
    
    async def _send_execution_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send the execution request to the proxy server.
        
        Args:
            request_payload: The complete request payload
            
        Returns:
            The model response from the proxy
        """
        timeout = float(os.getenv("REMOTE_PROXY_TIMEOUT", "120"))
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.proxy_url}/execute",
                json=request_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Request-ID": self.request_id
                }
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the actual model response from proxy response
            if "response" in result:
                return result["response"]
            else:
                return result