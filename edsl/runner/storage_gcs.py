"""
Google Cloud Storage Blob Storage Implementation

Provides a GCS-backed implementation of blob storage operations for the
hybrid storage architecture.

Features:
- Standard GCS authentication (service account or ADC)
- Support for fake-gcs-server emulator for local testing
- Custom metadata support on blobs
"""

import base64
import json
import os
import tempfile
from typing import Any

try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound

    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None
    NotFound = Exception


class GCSBlobStorage:
    """
    Google Cloud Storage implementation for blob operations.

    Suitable for:
    - Production deployment on GCP
    - Large binary file storage
    - Scalable blob storage with CDN integration

    Usage:
        # Production with service account
        blob_storage = GCSBlobStorage(
            project="my-project",
            bucket_name="runner-blobs"
        )

        # Local development with fake-gcs-server
        # Set STORAGE_EMULATOR_HOST=http://localhost:4443
        blob_storage = GCSBlobStorage(
            project="test-project",
            bucket_name="test-bucket"
        )
    """

    def __init__(
        self,
        project: str | None = None,
        bucket_name: str = "runner-blobs",
        credentials_path: str | None = None,
    ):
        """
        Initialize GCS blob storage.

        Args:
            project: GCP project ID. If None, uses default from environment.
            bucket_name: Name of the GCS bucket for blob storage.
            credentials_path: Path to service account JSON. If None, uses ADC.
        """
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage package is required for GCSBlobStorage. "
                "Install with: pip install google-cloud-storage"
            )

        # Check for emulator (fake-gcs-server)
        emulator_host = os.environ.get("STORAGE_EMULATOR_HOST")

        # Check for base64-encoded credentials (used in Cloud Run)
        credentials_base64 = os.environ.get("GCS_CREDENTIALS_BASE64")

        # Check for JSON credentials (used in Coopr)
        credentials_json_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")

        if credentials_path:
            self._client = storage.Client.from_service_account_json(
                credentials_path, project=project
            )
        elif credentials_json_str:
            # JSON credentials string (from Coopr's GOOGLE_APPLICATION_CREDENTIALS_JSON)
            from google.oauth2 import service_account as _sa

            creds = _sa.Credentials.from_service_account_info(
                json.loads(credentials_json_str)
            )
            self._client = storage.Client(credentials=creds, project=project)
        elif credentials_base64:
            # Decode base64 credentials and write to temp file
            # (google-cloud-storage requires a file path)
            credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                f.write(credentials_json)
                temp_credentials_path = f.name
            self._client = storage.Client.from_service_account_json(
                temp_credentials_path, project=project
            )
            # Clean up temp file
            os.unlink(temp_credentials_path)
        elif emulator_host:
            # For fake-gcs-server, create anonymous client
            from google.auth.credentials import AnonymousCredentials

            self._client = storage.Client(
                credentials=AnonymousCredentials(),
                project=project or "test-project",
            )
        else:
            # Use Application Default Credentials
            self._client = storage.Client(project=project)

        # Strip gs:// prefix if present
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[5:]

        self._bucket_name = bucket_name
        self._bucket = self._client.bucket(bucket_name)

        # Ensure bucket exists (create if using emulator)
        if emulator_host:
            self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist (useful for emulator)."""
        try:
            self._client.get_bucket(self._bucket_name)
        except NotFound:
            self._client.create_bucket(self._bucket_name)
            self._bucket = self._client.bucket(self._bucket_name)

    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        """
        Write binary blob data to GCS.

        Args:
            blob_id: Unique identifier for the blob (used as object key)
            data: Binary data to store
            metadata: Optional custom metadata dict (stored as GCS metadata)
        """
        blob = self._bucket.blob(blob_id)

        if metadata:
            # GCS metadata values must be strings
            blob.metadata = {
                k: json.dumps(v) if not isinstance(v, str) else v
                for k, v in metadata.items()
            }

        blob.upload_from_string(data, content_type="application/octet-stream")

    def read_blob(self, blob_id: str) -> bytes | None:
        """
        Read binary blob data from GCS.

        Args:
            blob_id: Unique identifier for the blob

        Returns:
            Binary data if blob exists, None otherwise
        """
        blob = self._bucket.blob(blob_id)
        try:
            return blob.download_as_bytes()
        except NotFound:
            return None

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        """
        Read blob metadata without downloading the blob data.

        Args:
            blob_id: Unique identifier for the blob

        Returns:
            Metadata dict if blob exists, None otherwise
        """
        blob = self._bucket.blob(blob_id)
        try:
            blob.reload()  # Fetch metadata from GCS
            if blob.metadata:
                # Decode JSON-encoded values
                return {
                    k: self._decode_metadata_value(v) for k, v in blob.metadata.items()
                }
            return {}
        except NotFound:
            return None

    def _decode_metadata_value(self, value: str) -> Any:
        """Attempt to decode a metadata value from JSON."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def delete_blob(self, blob_id: str) -> None:
        """
        Delete a blob from GCS.

        Args:
            blob_id: Unique identifier for the blob
        """
        blob = self._bucket.blob(blob_id)
        try:
            blob.delete()
        except NotFound:
            pass  # Already deleted or never existed

    def read_blob_as_text(self, blob_id: str) -> str | None:
        """
        Read a blob's content as text.

        Args:
            blob_id: Unique identifier for the blob

        Returns:
            The blob content as a string, or None if not found
        """
        blob = self._bucket.blob(blob_id)
        try:
            return blob.download_as_text()
        except NotFound:
            return None

    def generate_signed_upload_url(
        self,
        blob_id: str,
        expiration_seconds: int = 1800,
        content_type: str = "application/json",
    ) -> str:
        """
        Generate a signed URL for uploading a blob to GCS.

        Args:
            blob_id: Unique identifier for the blob
            expiration_seconds: URL expiration time in seconds (default: 30 minutes)
            content_type: Content type for the upload

        Returns:
            Signed URL for PUT request
        """
        from datetime import timedelta

        blob = self._bucket.blob(blob_id)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="PUT",
            content_type=content_type,
        )
        return url

    def generate_signed_download_url(
        self,
        blob_id: str,
        expiration_seconds: int = 1800,
    ) -> str:
        """
        Generate a signed URL for downloading a blob from GCS.

        Args:
            blob_id: Unique identifier for the blob
            expiration_seconds: URL expiration time in seconds (default: 30 minutes)

        Returns:
            Signed URL for GET request
        """
        from datetime import timedelta

        blob = self._bucket.blob(blob_id)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="GET",
        )
        return url

    def blob_exists(self, blob_id: str) -> bool:
        """
        Check if a blob exists in GCS.

        Args:
            blob_id: Unique identifier for the blob

        Returns:
            True if blob exists, False otherwise
        """
        blob = self._bucket.blob(blob_id)
        return blob.exists()

    def find_blob_by_suffix(self, suffix: str) -> str | None:
        """
        Find a blob by searching for a path suffix.

        This is useful for finding files when the exact path prefix is unknown.
        For example, finding a file by file_uuid when the user_uuid is unknown.

        Args:
            suffix: Path suffix to search for (e.g., "filestores/{file_uuid}.png")

        Returns:
            Full blob path if found, None otherwise
        """
        # List all blobs in the bucket and search for the suffix
        # This is inefficient for large buckets but works for local testing
        blobs = self._client.list_blobs(self._bucket_name, prefix="users/")
        for blob in blobs:
            if suffix in blob.name:
                return blob.name
        return None

    def list_blobs(self, prefix: str | None = None) -> list[str]:
        """
        List blob IDs, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter blobs

        Returns:
            List of blob IDs
        """
        blobs = self._client.list_blobs(self._bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]

    def clear(self, prefix: str | None = None) -> int:
        """
        Delete all blobs, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter which blobs to delete

        Returns:
            Number of blobs deleted
        """
        blobs = list(self._client.list_blobs(self._bucket_name, prefix=prefix))
        for blob in blobs:
            blob.delete()
        return len(blobs)

    def stats(self) -> dict:
        """
        Return storage statistics.

        Returns:
            Dict with blob count and total size
        """
        blobs = list(self._client.list_blobs(self._bucket_name))
        total_size = sum(blob.size or 0 for blob in blobs)
        return {
            "blob_count": len(blobs),
            "total_size_bytes": total_size,
            "bucket": self._bucket_name,
        }

    def close(self) -> None:
        """Close the GCS client connection."""
        self._client.close()
