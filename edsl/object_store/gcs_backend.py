"""Google Cloud Storage implementation of :class:`StorageBackend`.

Requires ``google-cloud-storage`` (install with ``pip install edsl[gcp]``).
"""

from __future__ import annotations

from typing import Iterator


class GCSBackend:
    """StorageBackend backed by a GCS bucket.

    Keys are stored under ``{prefix}/`` inside the bucket, so each
    object UUID gets its own key namespace (e.g. ``my-prefix/<uuid>/HEAD``).

    Parameters:
        bucket_name: GCS bucket name.
        prefix: Key prefix (typically the object UUID, optionally with a
                leading namespace).
    """

    def __init__(self, bucket_name: str, prefix: str) -> None:
        from google.cloud import storage as gcs

        self._client = gcs.Client()
        self._bucket = self._client.bucket(bucket_name)
        # Normalise: strip trailing slashes
        self._prefix = prefix.rstrip("/")

    def _blob(self, key: str):
        """Return a GCS Blob for the given relative key."""
        full_key = f"{self._prefix}/{key}" if self._prefix else key
        return self._bucket.blob(full_key)

    def read(self, key: str) -> str:
        """Read content at *key*.  Raises :class:`KeyError` if not found."""
        from google.cloud.exceptions import NotFound

        blob = self._blob(key)
        try:
            return blob.download_as_text()
        except NotFound:
            raise KeyError(key)

    def write(self, key: str, content: str) -> None:
        """Write *content* at *key*."""
        self._blob(key).upload_from_string(content, content_type="text/plain")

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        return self._blob(key).exists()

    def delete(self, key: str) -> None:
        """Delete *key*.  No-op if not found."""
        from google.cloud.exceptions import NotFound

        try:
            self._blob(key).delete()
        except NotFound:
            pass

    def list_prefix(self, prefix: str) -> Iterator[str]:
        """Yield all keys that start with *prefix* (relative to this backend's prefix)."""
        full_prefix = f"{self._prefix}/{prefix}" if self._prefix else prefix
        for blob in self._bucket.list_blobs(prefix=full_prefix):
            # Return the key relative to this backend's prefix
            if self._prefix:
                yield blob.name[len(self._prefix) + 1:]
            else:
                yield blob.name

    def delete_tree(self, prefix: str) -> None:
        """Delete all keys under *prefix*."""
        for key in list(self.list_prefix(prefix)):
            self.delete(key)
