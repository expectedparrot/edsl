import base64
import io
import tempfile
import mimetypes
import asyncio
import os
from typing import Dict, IO, Optional
from typing import Union
from uuid import UUID
import time
from typing import List, Literal, TYPE_CHECKING

from .scenario import Scenario
from edsl.utilities import remove_edsl_version
from .file_store_helpers.file_methods import FileMethods

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


class FileStore(Scenario):
    """
    A specialized Scenario subclass for managing file content and metadata.

    FileStore provides functionality for working with files in EDSL, handling various
    file formats with appropriate encoding, storage, and access methods. It extends
    Scenario to allow files to be included in surveys, questions, and other EDSL components.

    FileStore supports multiple file formats including text, PDF, Word documents, images,
    and more. It can load files from local paths or URLs, and provides methods for
    accessing file content, extracting text, and managing file operations.

    Key features:
    - Base64 encoding for portability and serialization
    - Lazy loading through temporary files when needed
    - Automatic MIME type detection
    - Text extraction from various file formats
    - Format-specific operations through specialized handlers

    Attributes:
        _path (str): The original file path.
        _temp_path (str): Path to any generated temporary file.
        suffix (str): File extension.
        binary (bool): Whether the file is binary.
        mime_type (str): The file's MIME type.
        base64_string (str): Base64-encoded file content.
        external_locations (dict): Dictionary of external locations.
        extracted_text (str): Text extracted from the file.

    Examples:
        >>> import tempfile
        >>> # Create a text file
        >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
        ...     _ = f.write("Hello World")
        ...     _ = f.flush()
        ...     fs = FileStore(f.name)

        # The following example works locally but is commented out for CI environments
        # where dependencies like pandoc may not be available:
        # >>> # FileStore supports various formats
        # >>> formats = ["txt", "pdf", "docx", "pptx", "md", "py", "json", "csv", "html", "png", "db"]
        # >>> _ = [FileStore.example(format) for format in formats]
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/filestore.html"

    # Class-level client cache for Google API
    _cached_client = None
    _cached_api_key = None
    _client_lock = None

    @staticmethod
    def _looks_like_coop_address(path: str) -> bool:
        """
        Check if a string looks like a Coop address rather than a file path.

        Coop addresses can be:
        - Full URLs: "https://www.expectedparrot.com/content/username/alias"
        - Short form: "username/alias" (exactly one slash, no path-like prefixes)

        File paths typically:
        - Start with "/" (absolute Unix path)
        - Start with "./" or "../" (relative path)
        - Start with "~" (home directory)
        - Contain ":" after a drive letter (Windows path like "C:\\")
        - Have file extensions with periods
        """
        if not path:
            return False

        # URLs are handled separately but are also Coop addresses
        if path.startswith("http://") or path.startswith("https://"):
            return "expectedparrot.com/content/" in path

        # Definitely a file path
        if path.startswith("/") or path.startswith("./") or path.startswith("../"):
            return False
        if path.startswith("~"):
            return False
        # Windows paths
        if len(path) > 1 and path[1] == ":":
            return False

        # Check for username/alias pattern: exactly one slash, no dots (which suggest file extensions)
        parts = path.split("/")
        if len(parts) == 2:
            username, alias = parts
            # Both parts should be non-empty and look like valid identifiers
            # (alphanumeric, dashes, underscores - no dots suggesting file extensions)
            if username and alias and "." not in path:
                return True

        return False

    def __init__(
        self,
        path: Optional[str] = None,
        mime_type: Optional[str] = None,
        binary: Optional[bool] = None,
        suffix: Optional[str] = None,
        base64_string: Optional[str] = None,
        external_locations: Optional[Dict[str, str]] = None,
        extracted_text: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize a new FileStore object.

        This constructor creates a FileStore object from either a file path or a base64-encoded
        string representation of file content. It handles automatic detection of file properties
        like MIME type, extracts text content when possible, and manages file encoding.

        Args:
            path: Path to the file to load. Can be a local file path, URL, or Coop address.
            mime_type: MIME type of the file. If not provided, will be auto-detected.
            binary: Whether the file is binary. Defaults to False.
            suffix: File extension. If not provided, will be extracted from the path.
            base64_string: Base64-encoded file content. If provided, the file content
                          will be loaded from this string instead of the path.
            external_locations: Dictionary mapping location names to URLs or paths where
                              the file can also be accessed.
            extracted_text: Pre-extracted text content from the file. If not provided,
                          text will be extracted automatically if possible.
            **kwargs: Additional keyword arguments. 'filename' can be used as an
                     alternative to 'path'.

        Note:
            If path is a URL (starts with http:// or https://), the file will be
            downloaded automatically. If path looks like a Coop address (e.g.,
            "username/alias"), the object will be pulled from Coop.
        """
        # Initialize parent class first to ensure self.data exists.
        # This prevents "'FileStore' object has no attribute 'data'" errors
        # if any initialization code below fails.
        super().__init__({})

        if path is None and "filename" in kwargs:
            path = kwargs["filename"]

        # Check if path looks like a Coop address and handle pull
        if path and base64_string is None and self._looks_like_coop_address(path):
            pulled_filestore = self.pull(path)
            # Copy all attributes from the pulled FileStore
            self._path = pulled_filestore._path
            self._temp_path = pulled_filestore._temp_path
            self.suffix = pulled_filestore.suffix
            self.binary = pulled_filestore.binary
            self.mime_type = pulled_filestore.mime_type
            self.base64_string = pulled_filestore.base64_string
            self.external_locations = pulled_filestore.external_locations
            self.extracted_text = pulled_filestore.extracted_text
            self.data.update(pulled_filestore.data)
            return

        # Check if path is a URL and handle download
        if path and (path.startswith("http://") or path.startswith("https://")):
            temp_filestore = self.from_url(path, mime_type=mime_type)
            path = temp_filestore._path
            mime_type = temp_filestore.mime_type

        self._path = path  # Store the original path privately
        self._temp_path = None  # Track any generated temporary file

        self.suffix = suffix or (path.split(".")[-1] if path else "")
        self.binary = binary or False
        self.mime_type = (
            mime_type
            or (mimetypes.guess_type(path)[0] if path else None)
            or "application/octet-stream"
        )
        self.base64_string = base64_string or self.encode_file_to_base64_string(path)
        self.external_locations = external_locations or {}

        self.extracted_text = (
            self.extract_text() if extracted_text is None else extracted_text
        )

        # Update self.data with the initialized values
        self.data.update(
            {
                "path": path,
                "base64_string": self.base64_string,
                "binary": self.binary,
                "suffix": self.suffix,
                "mime_type": self.mime_type,
                "external_locations": self.external_locations,
                "extracted_text": self.extracted_text,
            }
        )

    def to_scenario(self, key_name: Optional[str] = None):
        if key_name is None:
            key_name = "file_store"
        return Scenario({key_name: self})

    def _restore_from_gcs(self) -> None:
        """
        Restore FileStore content from Google Cloud Storage.

        This method is called automatically when accessing an offloaded FileStore's
        path property. It downloads the file content from GCS using the file_uuid
        stored in external_locations["gcs"] and restores the base64_string.

        Raises:
            Exception: If GCS file_uuid is not found or download fails
        """
        import requests

        # Check if GCS information is available
        gcs_info = self.external_locations.get("gcs")
        if not gcs_info or "file_uuid" not in gcs_info:
            raise ValueError(
                "Cannot restore offloaded FileStore: no GCS file_uuid found in external_locations"
            )

        file_uuid = gcs_info["file_uuid"]

        # Request download URL from backend
        try:
            from edsl.coop import Coop

            coop = Coop()

            response = coop._send_server_request(
                uri="api/v0/filestore/download-url",
                method="POST",
                payload={
                    "file_uuid": file_uuid,
                    "suffix": self.suffix,
                },
            )
            response_data = response.json()
            download_url = response_data.get("download_url")

            if not download_url:
                raise ValueError("Backend did not return a download URL")

            # Download file content from GCS
            download_response = requests.get(download_url, timeout=60)
            download_response.raise_for_status()
            file_content = download_response.content

            # Encode to base64 and restore
            self.base64_string = base64.b64encode(file_content).decode("utf-8")

            # Update the Scenario data dict as well
            self["base64_string"] = self.base64_string

            # Mark as restored in GCS info
            self.external_locations["gcs"]["offloaded"] = False

        except Exception as e:
            raise Exception(f"Failed to restore FileStore from GCS: {e}")

    @property
    def path(self) -> str:
        """
        Returns a valid path to the file content, creating a temporary file if needed.

        This property ensures that a valid file path is always available for the file
        content, even if the original file is no longer accessible or if the FileStore
        was created from a base64 string without a path. If the original path doesn't
        exist, it automatically generates a temporary file from the base64 content.

        For offloaded FileStores (uploaded to GCS during push), this property will
        automatically download the file content from GCS and restore the base64_string
        before creating the temporary file.

        Returns:
            A string containing a valid file path to access the file content.

        Examples:
            >>> import tempfile, os
            >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
            ...     _ = f.write("Hello World")
            ...     _ = f.flush()
            ...     fs = FileStore(f.name)
            ...     os.path.isfile(fs.path)
            True


        Notes:
            - The path may point to a temporary file that will be cleaned up when the
              Python process exits
            - Accessing this property may create a new temporary file if needed
            - This property provides a consistent interface regardless of how the
              FileStore was created (from file or from base64 string)
            - For offloaded FileStores, accessing this property will trigger a download
              from GCS, which may take time for large files
        """
        # Check if the FileStore is offloaded and needs to be restored from GCS
        if self.base64_string == "offloaded":
            # Check if we have GCS info before attempting restore
            gcs_info = self.external_locations.get("gcs", {})
            if not gcs_info or "file_uuid" not in gcs_info:
                raise ValueError(
                    f"FileStore content has been offloaded but GCS restoration info is missing. "
                    f"This FileStore cannot be used without the original file content. "
                    f"external_locations: {self.external_locations}"
                )
            self._restore_from_gcs()

        # Check if original path exists and is accessible
        if self._path and os.path.isfile(self._path):
            return self._path

        # If we already have a valid temporary file, use it
        if self._temp_path and os.path.isfile(self._temp_path):
            return self._temp_path

        # Generate a new temporary file from base64 content
        self._temp_path = self.to_tempfile(self.suffix)
        return self._temp_path

    def __str__(self):
        return "FileStore: self.path"

    @classmethod
    def example(cls, example_type="txt"):
        file_methods_class = FileMethods.get_handler(example_type)
        if file_methods_class:
            return cls(file_methods_class().example())
        else:
            print(f"Example for {example_type} is not supported.")

    @classmethod
    async def _async_screenshot(
        cls,
        url: str,
        full_page: bool = True,
        wait_until: Literal[
            "load", "domcontentloaded", "networkidle", "commit"
        ] = "networkidle",
        download_path: Optional[str] = None,
    ) -> "FileStore":
        """Async version of screenshot functionality"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Screenshot functionality requires additional dependencies.\n"
                "Install them with: pip install 'edsl[screenshot]'"
            )

        if download_path is None:
            download_path = os.path.join(
                os.getcwd(), f"screenshot_{int(time.time())}.png"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until=wait_until)
            await page.screenshot(path=download_path, full_page=full_page)
            await browser.close()

        return cls(download_path, mime_type="image/png")

    @classmethod
    def from_url_screenshot(cls, url: str, **kwargs) -> "FileStore":
        """Synchronous wrapper for screenshot functionality"""
        import asyncio

        try:
            # Try using get_event_loop first (works in regular Python)
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If we're in IPython/Jupyter, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(cls._async_screenshot(url, **kwargs))
        finally:
            if not loop.is_running():
                loop.close()

    @classmethod
    def batch_screenshots(cls, urls: List[str], **kwargs) -> "ScenarioList":
        """
        Take screenshots of multiple URLs concurrently.
        Args:
            urls: List of URLs to screenshot
            **kwargs: Additional arguments passed to screenshot function (full_page, wait_until, etc.)
        Returns:
            ScenarioList containing FileStore objects with their corresponding URLs
        """
        # Import here to avoid circular imports
        from .scenario_list import ScenarioList

        try:
            # Try using get_event_loop first (works in regular Python)
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If we're in IPython/Jupyter, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Create tasks for all screenshots
        tasks = [cls._async_screenshot(url, **kwargs) for url in urls]

        try:
            # Run all screenshots concurrently
            results = loop.run_until_complete(
                asyncio.gather(*tasks, return_exceptions=True)
            )

            # Filter out any errors and log them
            successful_results = []
            for url, result in zip(urls, results):
                if isinstance(result, Exception):
                    print(f"Failed to screenshot {url}: {result}")
                else:
                    successful_results.append(
                        Scenario({"url": url, "screenshot": result})
                    )

            return ScenarioList(successful_results)
        finally:
            if not loop.is_running():
                loop.close()

    @property
    def size(self) -> int:
        if self.base64_string is not None:
            return (len(self.base64_string) / 4.0) * 3  # from base64 to char size
        return os.path.getsize(self.path)

    def upload_google(self, refresh: bool = False) -> None:
        try:
            from google import genai
            from google.genai.types import UploadFileConfig
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is required to upload files to Google. "
                "Please install it with: pip install edsl[google] "
                "or: pip install google-genai"
            )
        import time

        method_start = time.time()

        try:
            # Time client creation
            client_start = time.time()
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key is None:
                raise Exception("GOOGLE_API_KEY is not set.")
            client = genai.Client(api_key=google_api_key)
            _client_time = time.time() - client_start
            # print(
            #     f"Google client creation in FileStore took {_client_time:.3f}s",
            #     flush=True,
            # )

            # Time file upload
            upload_start = time.time()
            # print(f"Starting file upload for {self.name}", flush=True)
            google_file = client.files.upload(
                file=self.path, config=UploadFileConfig(mime_type=self.mime_type)
            )
            _upload_time = time.time() - upload_start
            # print(f"File upload completed in {_upload_time:.3f}s", flush=True)

            self.external_locations["google"] = google_file.model_dump(mode="json")

            # Time polling for activation
            polling_start = time.time()
            attempt = 0
            # print(f"File {self.name} uploaded, waiting for activation...", flush=True)
            while True:
                attempt += 1
                status_start = time.time()
                file_metadata = client.files.get(name=google_file.name)
                file_state = file_metadata.state
                _status_time = time.time() - status_start
                # print(
                #     f"Attempt {attempt}: File state={file_state} (check took {_status_time:.3f}s)",
                #     flush=True,
                # )

                if file_state == "ACTIVE":
                    _polling_time = time.time() - polling_start
                    _total_time = time.time() - method_start
                    # print(
                    #     f"File {self.name} activated after {attempt} attempts in {_polling_time:.3f}s (total: {_total_time:.3f}s)",
                    #     flush=True,
                    # )
                    break
                elif file_state == "FAILED":
                    break
                # Add a small delay to prevent busy-wait
                # print(f"Waiting 0.5s before next attempt...", flush=True)
                time.sleep(0.5)
        except Exception:
            _total_time = time.time() - method_start
            # print(f"Error uploading to Google after {_total_time:.3f}s: {e}", flush=True)
            raise

    async def async_upload_google(self, refresh: bool = False) -> dict:
        """
        Async version of upload_google that avoids blocking the event loop.

        This method uploads a file to Google's Generative AI service asynchronously,
        polls for activation status with exponential backoff, and returns the file info.

        Args:
            refresh: If True, force re-upload even if already uploaded

        Returns:
            Dictionary containing the Google file information

        Raises:
            Exception: If upload fails or file activation fails
        """
        try:
            from google import genai
            from google.genai.types import UploadFileConfig
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is required to upload files to Google. "
                "Please install it with: pip install edsl[google] "
                "or: pip install google-genai"
            )
        import asyncio

        # Check if already uploaded and refresh not requested
        if not refresh and "google" in self.external_locations:
            return self.external_locations["google"]

        import time

        method_start = time.time()

        try:
            # Get or create cached client (async method)
            client_start = time.time()
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key is None:
                raise Exception("GOOGLE_API_KEY is not set.")

            # Initialize client lock if needed
            if FileStore._client_lock is None:
                import asyncio

                FileStore._client_lock = asyncio.Lock()

            async with FileStore._client_lock:
                if (
                    FileStore._cached_client is None
                    or FileStore._cached_api_key != google_api_key
                ):
                    # print("Creating new Google client in FileStore...", flush=True)
                    creation_start = time.time()
                    FileStore._cached_client = genai.Client(api_key=google_api_key)
                    FileStore._cached_api_key = google_api_key
                    _creation_time = time.time() - creation_start
                    _client_time = time.time() - client_start
                    # print(
                    #     f"Google client creation took {_creation_time:.3f}s (total with lock: {_client_time:.3f}s)",
                    #     flush=True,
                    # )
                else:
                    _client_time = time.time() - client_start
                    # print(
                    #     f"Using cached Google client in FileStore (took {_client_time:.3f}s)",
                    #     flush=True,
                    # )

            client = FileStore._cached_client

            # Upload file using native async API
            upload_start = time.time()
            # print(f"Starting async file upload for {self.name}", flush=True)
            google_file = await client.aio.files.upload(
                file=self.path, config=UploadFileConfig(mime_type=self.mime_type)
            )
            _upload_time = time.time() - upload_start
            # print(f"Async file upload completed in {_upload_time:.3f}s", flush=True)

            google_file_dict = google_file.model_dump(mode="json")
            # print(f"File {self.name} uploaded, waiting for activation...", flush=True)

            # Poll for file activation with exponential backoff using native async API
            polling_start = time.time()
            max_attempts = 30
            for attempt in range(max_attempts):
                status_start = time.time()
                file_metadata = await client.aio.files.get(name=google_file.name)
                _status_time = time.time() - status_start
                file_state = file_metadata.state
                # print(
                #     f"Attempt {attempt+1}: File state={file_state} (check took {_status_time:.3f}s)",
                #     flush=True,
                # )

                if file_state == "ACTIVE":
                    _polling_time = time.time() - polling_start
                    _total_time = time.time() - method_start
                    # print(
                    #     f"File {self.name} activated after {attempt+1} attempts in {_polling_time:.3f}s (total: {_total_time:.3f}s)",
                    #     flush=True,
                    # )
                    self.external_locations["google"] = google_file_dict
                    return google_file_dict
                elif file_state == "FAILED":
                    raise Exception(f"File upload failed with state: {file_state}")

                # Exponential backoff: 0.5s, 1s, 2s, 4s, ..., max 10s
                wait_time = min(0.5 * (2**attempt), 10.0)
                # print(f"Waiting {wait_time:.1f}s before next attempt...", flush=True)
                await asyncio.sleep(wait_time)

            # If we've exhausted all attempts
            _total_time = time.time() - method_start
            # print(
            #     f"File upload timed out after {max_attempts} attempts (total time: {_total_time:.3f}s)",
            #     flush=True,
            # )
            raise Exception(f"File upload timed out after {max_attempts} attempts")

        except Exception:
            _total_time = time.time() - method_start
            # print(
            #     f"Error in async_upload_google after {_total_time:.3f}s: {e}", flush=True
            # )
            raise

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d):
        # return cls(d["filename"], d["binary"], d["suffix"], d["base64_string"])
        return cls(**d)

    def __repr__(self):
        import reprlib

        r = reprlib.Repr()
        r.maxstring = 20  # Limit strings to 20 chars
        r.maxother = 30  # Limit other types to 30 chars

        params = ", ".join(f"{key}={r.repr(value)}" for key, value in self.data.items())
        return f"{self.__class__.__name__}({params})"

    def _repr_html_(self):
        parent_html = super()._repr_html_()
        from .file_store_helpers.construct_download_link import ConstructDownloadLink

        link = ConstructDownloadLink(self).html_create_link(self.path, style=None)
        return f"{parent_html}<br>{link}"

    def download_link(self):
        from .file_store_helpers.construct_download_link import ConstructDownloadLink

        return ConstructDownloadLink(self).html_create_link(self.path, style=None)

    def encode_file_to_base64_string(self, file_path: str):
        try:
            # Attempt to open the file in text mode
            with open(file_path, "r") as text_file:
                # Read the text data
                text_data = text_file.read()
                # Encode the text data to a base64 string
                base64_encoded_data = base64.b64encode(text_data.encode("utf-8"))
        except UnicodeDecodeError:
            # If reading as text fails, open the file in binary mode
            with open(file_path, "rb") as binary_file:
                # Read the binary data
                binary_data = binary_file.read()
                # Encode the binary data to a base64 string
                base64_encoded_data = base64.b64encode(binary_data)
                self.binary = True
        # Convert the base64 bytes to a string
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            print("Current working directory:", os.getcwd())
            raise
        base64_string = base64_encoded_data.decode("utf-8")

        return base64_string

    def open(self) -> "IO":
        if self.binary:
            return self.base64_to_file(self.base64_string, is_binary=True)
        else:
            return self.base64_to_text_file(self.base64_string)

    def write(self, filename: Optional[str] = None) -> str:
        """
        Write the file content to disk, either to a specified filename or a temporary file.

        Args:
            filename (Optional[str]): The destination filename. If None, creates a temporary file.

        Returns:
            str: The path to the written file.
        """
        # Determine the mode based on binary flag
        mode = "wb" if self.binary else "w"

        # If no filename provided, create a temporary file
        if filename is None:
            from tempfile import NamedTemporaryFile

            with NamedTemporaryFile(delete=False, suffix="." + self.suffix) as f:
                filename = f.name

        # Write the content using the appropriate mode
        try:
            with open(filename, mode) as f:
                content = self.open().read()
                # For text mode, ensure we're writing a string
                if not self.binary and isinstance(content, bytes):
                    content = content.decode("utf-8")
                f.write(content)
                # print(f"File written to {filename}")
        except Exception as e:
            print(f"Error writing file: {e}")
            raise

        # return filename

    @staticmethod
    def base64_to_text_file(base64_string) -> "IO":
        # Decode the base64 string to bytes
        text_data_bytes = base64.b64decode(base64_string)

        # Convert bytes to string
        text_data = text_data_bytes.decode("utf-8")

        # Create a StringIO object from the text data
        text_file = io.StringIO(text_data)

        return text_file

    @staticmethod
    def base64_to_file(base64_string, is_binary=True):
        # Decode the base64 string to bytes
        file_data = base64.b64decode(base64_string)

        if is_binary:
            # Create a BytesIO object for binary data
            return io.BytesIO(file_data)
        else:
            # Convert bytes to string for text data
            text_data = file_data.decode("utf-8")
            # Create a StringIO object for text data
            return io.StringIO(text_data)

    @property
    def text(self):
        if self.binary:
            import warnings

            warnings.warn("This is a binary file.")
        else:
            return self.base64_to_text_file(self.base64_string).read()

    def to_tempfile(self, suffix=None):
        if suffix is None:
            suffix = self.suffix
        if self.binary:
            file_like_object = self.base64_to_file(self.base64_string, is_binary=True)
        else:
            file_like_object = self.base64_to_text_file(self.base64_string)

        # Create a named temporary file
        # We need different parameters for binary vs text mode
        if self.binary:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix="." + suffix, mode="wb"
            )
        else:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix="." + suffix, encoding="utf-8", mode="w"
            )

        if self.binary:
            temp_file.write(file_like_object.read())
        else:
            temp_file.write(file_like_object.read())

        temp_file.close()

        return temp_file.name

    def view(self) -> None:
        handler = FileMethods.get_handler(self.suffix)
        if handler:
            handler(self.path).view()
        else:
            print(f"Viewing of {self.suffix} files is not supported.")

    def extract_text(self) -> str:
        handler = FileMethods.get_handler(self.suffix)
        if handler and hasattr(handler, "extract_text"):
            return handler(self.path).extract_text()

        if not self.binary:
            return self.text

        return None
        # raise TypeError("No text method found for this file type.")

    def to_scenario_list(self):
        handler = FileMethods.get_handler(self.suffix)
        if handler and hasattr(handler, "to_scenario_list"):
            return handler(self.path).to_scenario_list()
        raise TypeError("No scenario list method found for this file type.")

    def push(
        self,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
        expected_parrot_url: Optional[str] = None,
    ) -> dict:
        """
        Push the object to Coop.
        :param description: The description of the object to push.
        :param visibility: The visibility of the object to push.
        """
        scenario_version = Scenario.from_dict(self.to_dict())

        if description is None:
            description = "File: " + self.path
        info = scenario_version.push(
            description=description,
            visibility=visibility,
            expected_parrot_url=expected_parrot_url,
            alias=alias,
        )
        return info

    def offload(self, inplace=False) -> "FileStore":
        """
        Offloads base64-encoded content from the FileStore by replacing 'base64_string'
        with 'offloaded'. This reduces memory usage.

        Args:
            inplace (bool): If True, modify the current FileStore. If False, return a new one.

        Returns:
            FileStore: The modified FileStore (either self or a new instance).
        """
        if inplace:
            if hasattr(self, "base64_string"):
                self.base64_string = "offloaded"
            return self
        else:
            # Create a copy and offload it
            file_store_dict = self.to_dict()
            if "base64_string" in file_store_dict:
                file_store_dict["base64_string"] = "offloaded"
            return self.__class__.from_dict(file_store_dict)

    def save_to_gcs_bucket(self, signed_url: str) -> dict:
        """
        Saves the FileStore's file content to a Google Cloud Storage bucket using a signed URL.

        Args:
            signed_url (str): The signed URL for uploading to GCS bucket

        Returns:
            dict: Response from the GCS upload operation

        Raises:
            ValueError: If base64_string is offloaded or missing
            requests.RequestException: If the upload fails
        """
        import requests
        import base64

        # Check if content is available
        if not hasattr(self, "base64_string") or self.base64_string == "offloaded":
            raise ValueError(
                "File content is not available (offloaded or missing). Cannot upload to GCS."
            )

        # Decode base64 content to bytes
        try:
            file_content = base64.b64decode(self.base64_string)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 content: {e}")

        # Prepare headers with proper content type
        headers = {
            "Content-Type": self.mime_type or "application/octet-stream",
            "Content-Length": str(len(file_content)),
        }

        # Upload to GCS using the signed URL
        response = requests.put(signed_url, data=file_content, headers=headers)
        response.raise_for_status()

        return {
            "status": "success",
            "status_code": response.status_code,
            "file_size": len(file_content),
            "mime_type": self.mime_type,
            "file_extension": self.suffix,
        }

    @classmethod
    def pull(cls, url_or_uuid: Union[str, UUID]) -> "FileStore":
        """
        Pull a FileStore object from Coop.

        Args:
            url_or_uuid: Either a UUID string or a URL pointing to the object
            expected_parrot_url: Optional URL for the Parrot server

        Returns:
            FileStore: The pulled FileStore object
        """
        scenario_version = Scenario.pull(url_or_uuid)
        return cls.from_dict(scenario_version.to_dict())

    @classmethod
    def from_url(
        cls,
        url: str,
        download_path: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "FileStore":
        """
        :param url: The URL of the file to download.
        :param download_path: The path to save the downloaded file.
        :param mime_type: The MIME type of the file. If None, it will be guessed from the file extension.
        """
        import requests
        from urllib.parse import urlparse

        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        # Get the filename from the URL if download_path is not provided
        if download_path is None:
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                filename = "downloaded_file"
            # download_path = filename
            download_path = os.path.join(os.getcwd(), filename)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        # Write the file
        with open(download_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # Create and return a new File instance
        return cls(download_path, mime_type=mime_type)

    def create_link(self, custom_filename=None, style=None):
        from .file_store_helpers.construct_download_link import ConstructDownloadLink

        return ConstructDownloadLink(self).create_link(custom_filename, style)

    def to_pdf(self, output_path: Optional[str] = None, **options) -> "FileStore":
        """
        Convert a markdown FileStore to a PDF and return a new FileStore for the PDF.

        Args:
            output_path: Optional destination path for the generated PDF. If not provided,
                a temporary file will be created.
            **options: Additional conversion options forwarded to the converter, e.g.:
                - margin (str): Page margin (default: "1in")
                - font_size (str): Font size (default: "12pt")
                - font (str): Main font name (optional)
                - toc (bool): Include table of contents (default: False)
                - number_sections (bool): Number sections (default: False)
                - highlight_style (str): Code highlighting style (default: "tango")

        Returns:
            FileStore: A new FileStore referencing the generated PDF file.

        Raises:
            TypeError: If the current file is not a markdown file.
            RuntimeError: If conversion fails.
        """
        if self.suffix.lower() not in ("md", "markdown"):
            raise TypeError("to_pdf() is only supported for markdown FileStore objects")

        import os
        import tempfile
        from edsl.utilities.markdown_to_pdf import MarkdownToPDF

        # Determine output path
        if output_path is None:
            temp_dir = tempfile.mkdtemp()
            base_name = os.path.splitext(os.path.basename(self.path))[0] or "document"
            output_path = os.path.join(temp_dir, f"{base_name}.pdf")

        converter = MarkdownToPDF(
            self.text, filename=os.path.splitext(os.path.basename(output_path))[0]
        )
        success = converter.convert(output_path, **options)
        if not success:
            raise RuntimeError("Failed to convert markdown to PDF")

        return self.__class__(output_path)

    def to_docx(self, output_path: Optional[str] = None, **options) -> "FileStore":
        """
        Convert a markdown FileStore to a DOCX and return a new FileStore for the DOCX.

        Args:
            output_path: Optional destination path for the generated DOCX. If not provided,
                a temporary file will be created.
            **options: Additional conversion options forwarded to the converter, e.g.:
                - reference_doc (str): Path to reference docx for styling
                - toc (bool): Include table of contents (default: False)
                - number_sections (bool): Number sections (default: False)
                - highlight_style (str): Code highlighting style (default: "tango")

        Returns:
            FileStore: A new FileStore referencing the generated DOCX file.

        Raises:
            TypeError: If the current file is not a markdown file.
            RuntimeError: If conversion fails.
        """
        if self.suffix.lower() not in ("md", "markdown"):
            raise TypeError(
                "to_docx() is only supported for markdown FileStore objects"
            )

        import os
        import tempfile
        from edsl.utilities.markdown_to_docx import MarkdownToDocx

        # Determine output path
        if output_path is None:
            temp_dir = tempfile.mkdtemp()
            base_name = os.path.splitext(os.path.basename(self.path))[0] or "document"
            output_path = os.path.join(temp_dir, f"{base_name}.docx")

        converter = MarkdownToDocx(
            self.text, filename=os.path.splitext(os.path.basename(output_path))[0]
        )
        success = converter.convert(output_path, **options)
        if not success:
            raise RuntimeError("Failed to convert markdown to DOCX")

        return self.__class__(output_path)

    def to_pandas(self):
        """
        Convert the file content to a pandas DataFrame if supported by the file handler.

        Returns:
            pandas.DataFrame: The data from the file as a DataFrame

        Raises:
            AttributeError: If the file type's handler doesn't support pandas conversion
        """
        handler = FileMethods.get_handler(self.suffix)
        if handler and hasattr(handler, "to_pandas"):
            return handler(self.path).to_pandas()
        raise AttributeError(
            f"Converting {self.suffix} files to pandas DataFrame is not supported"
        )

    def is_image(self) -> bool:
        """
        Check if the file is an image by examining its MIME type.

        Returns:
            bool: True if the file is an image, False otherwise.

        Examples:
            >>> fs = FileStore.example("png")  # doctest: +SKIP
            >>> fs.is_image()  # doctest: +SKIP
            True  # doctest: +SKIP
            >>> fs = FileStore.example("txt")
            >>> fs.is_image()
            False
        """
        # Check if the mime type starts with 'image/'
        return self.mime_type.startswith("image/")

    def is_video(self) -> bool:
        """
        Check if the file is a video by examining its MIME type.

        Returns:
            bool: True if the file is a video, False otherwise.

        Examples:
            >>> fs = FileStore.example("mp4")
            >>> fs.is_video()
            True
            >>> fs = FileStore.example("webm")
            >>> fs.is_video()
            True
            >>> fs = FileStore.example("txt")
            >>> fs.is_video()
            False
        """
        # Check if the mime type starts with 'video/'
        return self.mime_type.startswith("video/")

    def get_video_metadata(self) -> dict:
        """
        Get metadata about a video file such as duration, dimensions, codec, etc.
        Uses FFmpeg to extract the information if available.

        Returns:
            dict: A dictionary containing video metadata, or a dictionary with
                 error information if metadata extraction fails.

        Raises:
            ValueError: If the file is not a video.

        Example:
            >>> fs = FileStore.example("mp4")
            >>> metadata = fs.get_video_metadata()
            >>> isinstance(metadata, dict)
            True
        """
        if not self.is_video():
            raise ValueError("This file is not a video")

        # We'll try to use ffprobe (part of ffmpeg) to get metadata
        import subprocess
        import json

        try:
            # Run ffprobe to get video metadata in JSON format
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    self.path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse the JSON output
            metadata = json.loads(result.stdout)

            # Extract some common useful fields into a more user-friendly format
            simplified = {
                "format": metadata.get("format", {}).get("format_name", "unknown"),
                "duration_seconds": float(
                    metadata.get("format", {}).get("duration", 0)
                ),
                "size_bytes": int(metadata.get("format", {}).get("size", 0)),
                "bit_rate": int(metadata.get("format", {}).get("bit_rate", 0)),
                "streams": len(metadata.get("streams", [])),
            }

            # Add video stream info if available
            video_streams = [
                s for s in metadata.get("streams", []) if s.get("codec_type") == "video"
            ]
            if video_streams:
                video = video_streams[0]  # Get the first video stream
                simplified["video"] = {
                    "codec": video.get("codec_name", "unknown"),
                    "width": video.get("width", 0),
                    "height": video.get("height", 0),
                    "frame_rate": eval(
                        video.get("r_frame_rate", "0/1")
                    ),  # Convert "30/1" to 30.0
                    "pixel_format": video.get("pix_fmt", "unknown"),
                }

            # Add audio stream info if available
            audio_streams = [
                s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"
            ]
            if audio_streams:
                audio = audio_streams[0]  # Get the first audio stream
                simplified["audio"] = {
                    "codec": audio.get("codec_name", "unknown"),
                    "channels": audio.get("channels", 0),
                    "sample_rate": audio.get("sample_rate", "unknown"),
                }

            # Return both the complete metadata and simplified version
            return {"simplified": simplified, "full": metadata}

        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            # If ffprobe is not available or fails, return basic info
            return {
                "error": str(e),
                "format": self.suffix,
                "mime_type": self.mime_type,
                "size_bytes": self.size,
            }

    def get_image_dimensions(self) -> tuple:
        """
        Get the dimensions (width, height) of an image file.

        Returns:
            tuple: A tuple containing the width and height of the image.

        Raises:
            ValueError: If the file is not an image or PIL is not installed.

        Examples:
            >>> fs = FileStore.example("png")  # doctest: +SKIP
            >>> width, height = fs.get_image_dimensions()  # doctest: +SKIP
            >>> isinstance(width, int) and isinstance(height, int)  # doctest: +SKIP
            True  # doctest: +SKIP
        """
        if not self.is_image():
            raise ValueError("This file is not an image")

        try:
            from PIL import Image
        except ImportError:
            raise ImportError(
                "PIL (Pillow) is required to get image dimensions. Install it with: pip install pillow"
            )

        with Image.open(self.path) as img:
            return img.size  # Returns (width, height)

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the FileStore.

        This representation can be used with eval() to recreate the FileStore object.
        Used primarily for doctests and debugging.
        """
        class_name = self.__class__.__name__
        items = []

        # Include the most essential parameters for recreation
        if self._path:
            items.append(f"path={repr(self._path)}")
        if self.mime_type != "application/octet-stream":  # Only if not default
            items.append(f"mime_type={repr(self.mime_type)}")
        if self.binary:  # Only if True
            items.append(f"binary={self.binary}")
        if self.suffix:
            items.append(f"suffix={repr(self.suffix)}")
        if self.base64_string and self.base64_string != "offloaded":
            # Truncate very long base64 strings for readability
            b64_repr = repr(self.base64_string)
            if len(b64_repr) > 100:
                b64_repr = b64_repr[:47] + "..." + b64_repr[-47:]
            items.append(f"base64_string={b64_repr}")
        if self.external_locations:
            items.append(f"external_locations={repr(self.external_locations)}")
        if self.extracted_text:
            # Truncate long extracted text for readability
            text_repr = repr(self.extracted_text)
            if len(text_repr) > 100:
                text_repr = text_repr[:47] + "..." + text_repr[-47:]
            items.append(f"extracted_text={text_repr}")

        return f"{class_name}({', '.join(items)})"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the FileStore with Rich formatting.

        Returns:
            A Rich-formatted string showing key FileStore information.
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        # Build the Rich text
        output = Text()
        class_name = self.__class__.__name__

        output.append(f"{class_name}(\n", style=RICH_STYLES["primary"])

        # File path
        if self._path:
            output.append("    path=", style=RICH_STYLES["default"])
            path_display = self._path
            if len(path_display) > 50:
                path_display = "..." + path_display[-47:]
            output.append(f'"{path_display}"', style=RICH_STYLES["key"])
            output.append(",\n", style=RICH_STYLES["default"])

        # File size (in human readable format)
        try:
            size_bytes = int(self.size)
            if size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            output.append("    size=", style=RICH_STYLES["default"])
            output.append(size_str, style=RICH_STYLES["secondary"])
            output.append(",\n", style=RICH_STYLES["default"])
        except (ValueError, TypeError):
            pass

        # MIME type
        output.append("    mime_type=", style=RICH_STYLES["default"])
        output.append(f'"{self.mime_type}"', style=RICH_STYLES["secondary"])
        output.append(",\n", style=RICH_STYLES["default"])

        # File extension
        output.append("    suffix=", style=RICH_STYLES["default"])
        output.append(f'"{self.suffix}"', style=RICH_STYLES["secondary"])

        # Binary flag
        if self.binary:
            output.append(",\n    binary=", style=RICH_STYLES["default"])
            output.append("True", style=RICH_STYLES["highlight"])

        # Extracted text availability
        if self.extracted_text:
            text_length = len(self.extracted_text)
            output.append(",\n    ", style=RICH_STYLES["default"])
            output.append(
                f"extracted_text_length={text_length}", style=RICH_STYLES["secondary"]
            )

        # External locations
        if self.external_locations:
            locations = list(self.external_locations.keys())
            output.append(",\n    external_locations=", style=RICH_STYLES["default"])
            output.append(f"{locations}", style=RICH_STYLES["key"])

        # Base64 status
        if self.base64_string == "offloaded":
            output.append(",\n    ", style=RICH_STYLES["default"])
            output.append("status=offloaded", style=RICH_STYLES["dim"])
        elif self.base64_string:
            b64_length = len(self.base64_string)
            output.append(",\n    ", style=RICH_STYLES["default"])
            output.append(f"base64_length={b64_length}", style=RICH_STYLES["dim"])

        output.append("\n)", style=RICH_STYLES["primary"])

        # Render to string
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        console.print(output, end="")
        return string_io.getvalue()

    def __getattr__(self, name):
        """
        Delegate pandas DataFrame methods to the underlying DataFrame if this is a CSV file
        """
        # Special case for pickle protocol
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        # Check for _data directly in __dict__ to avoid recursion
        _data = self.__dict__.get("_data", None)
        if _data and _data.get("suffix") == "csv":
            df = self.to_pandas()
            if hasattr(df, name):
                return getattr(df, name)

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )


# class CSVFileStore(FileStore):
#     @classmethod
#     def example(cls):
#         from ..results import Results

#         r = Results.example()
#         import tempfile

#         with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
#             r.to_csv(filename=f.name)

#         return cls(f.name)

#     def view(self):
#         import pandas as pd

#         return pd.read_csv(self.to_tempfile())


# class PDFFileStore(FileStore):
#     def view(self):
#         pdf_path = self.to_tempfile()
#         print(f"PDF path: {pdf_path}")  # Print the path to ensure it exists
#         import os
#         import subprocess

#         if os.path.exists(pdf_path):
#             try:
#                 if os.name == "posix":
#                     # for cool kids
#                     subprocess.run(["open", pdf_path], check=True)  # macOS
#                 elif os.name == "nt":
#                     os.startfile(pdf_path)  # Windows
#                 else:
#                     subprocess.run(["xdg-open", pdf_path], check=True)  # Linux
#             except Exception as e:
#                 print(f"Error opening PDF: {e}")
#         else:
#             print("PDF file was not created successfully.")

#     @classmethod
#     def example(cls):
#         import textwrap

#         pdf_string = textwrap.dedent(
#             """\
#         %PDF-1.4
#         1 0 obj
#         << /Type /Catalog /Pages 2 0 R >>
#         endobj
#         2 0 obj
#         << /Type /Pages /Kids [3 0 R] /Count 1 >>
#         endobj
#         3 0 obj
#         << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
#         endobj
#         4 0 obj
#         << /Length 44 >>
#         stream
#         BT
#         /F1 24 Tf
#         100 700 Td
#         (Hello, World!) Tj
#         ET
#         endstream
#         endobj
#         5 0 obj
#         << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
#         endobj
#         6 0 obj
#         << /ProcSet [/PDF /Text] /Font << /F1 5 0 R >> >>
#         endobj
#         xref
#         0 7
#         0000000000 65535 f
#         0000000010 00000 n
#         0000000053 00000 n
#         0000000100 00000 n
#         0000000173 00000 n
#         0000000232 00000 n
#         0000000272 00000 n
#         trailer
#         << /Size 7 /Root 1 0 R >>
#         startxref
#         318
#         %%EOF"""
#         )
#         import tempfile

#         with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
#             f.write(pdf_string.encode())

#         return cls(f.name)


# class PNGFileStore(FileStore):
#     @classmethod
#     def example(cls):
#         import textwrap

#         png_string = textwrap.dedent(
#             """\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDAT\x08\xd7c\x00\x01"""
#         )
#         import tempfile

#         with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
#             f.write(png_string.encode())

#         return cls(f.name)

#     def view(self):
#         import matplotlib.pyplot as plt
#         import matplotlib.image as mpimg

#         img = mpimg.imread(self.to_tempfile())
#         plt.imshow(img)
#         plt.show()


# class SQLiteFileStore(FileStore):
#     @classmethod
#     def example(cls):
#         import sqlite3
#         import tempfile

#         with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
#             conn = sqlite3.connect(f.name)
#             c = conn.cursor()
#             c.execute("""CREATE TABLE stocks (date text)""")
#             conn.commit()

#             return cls(f.name)

#     def view(self):
#         import subprocess
#         import os

#         sqlite_path = self.to_tempfile()
#         os.system(f"sqlite3 {sqlite_path}")


# class HTMLFileStore(FileStore):
#     @classmethod
#     def example(cls):
#         import tempfile

#         with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
#             f.write("<html><body><h1>Test</h1></body></html>".encode())

#         return cls(f.name)

#     def view(self):
#         import webbrowser

#         html_path = self.to_tempfile()
#         webbrowser.open("file://" + html_path)


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    # formats = FileMethods.supported_file_types()
    # for file_type in formats:
    #     print("Now testinging", file_type)
    #     fs = FileStore.example(file_type)
    #     fs.view()
    #     input("Press Enter to continue...")
