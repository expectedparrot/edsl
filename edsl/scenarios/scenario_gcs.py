"""
Scenario Google Cloud Storage functionality.

This module contains the ScenarioGCS class which handles all Google Cloud Storage
operations for Scenario objects. This includes uploading FileStore objects to GCS
buckets and providing information about FileStore content.

The ScenarioGCS provides:
- FileStore upload functionality to GCS buckets
- FileStore information analysis and reporting
- Support for both single and multiple FileStore scenarios
- Comprehensive error handling and upload status reporting
"""

from __future__ import annotations
import base64
from typing import Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario import Scenario


class ScenarioGCS:
    """
    Handles Google Cloud Storage operations for Scenario objects.
    
    This class provides methods for uploading FileStore objects contained within
    Scenario instances to Google Cloud Storage buckets using signed URLs. It also
    provides information about FileStore objects to help with upload planning.
    """

    def __init__(self, scenario: "Scenario"):
        """
        Initialize the GCS handler with a Scenario instance.
        
        Args:
            scenario: The Scenario instance containing FileStore objects to upload.
        """
        self.scenario = scenario

    def save_to_gcs_bucket(self, signed_url_or_dict: Union[str, Dict[str, str]]) -> dict:
        """
        Saves FileStore objects contained within this Scenario to a Google Cloud Storage bucket.

        This method finds all FileStore objects in the Scenario and uploads them to GCS using
        the provided signed URL(s). If the Scenario itself was created from a FileStore (has
        base64_string as a top-level key), it uploads that content directly.

        Args:
            signed_url_or_dict: Either:
                - str: Single signed URL (for single FileStore or Scenario from FileStore)
                - dict: Mapping of scenario keys to signed URLs for multiple FileStore objects
                        e.g., {"video": "signed_url_1", "image": "signed_url_2"}

        Returns:
            dict: Summary of upload operations performed

        Raises:
            ValueError: If no uploadable content found or content is offloaded
            requests.RequestException: If any upload fails

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"text": "hello"})
            >>> gcs = ScenarioGCS(s)
            >>> info = gcs.get_filestore_info()
            >>> info['total_count']
            0
        """
        from edsl.scenarios import FileStore
        import requests

        upload_results = []

        # Case 1: This Scenario was created from a FileStore (has direct base64_string)
        if "base64_string" in self.scenario and isinstance(self.scenario.get("base64_string"), str):
            if self.scenario["base64_string"] == "offloaded":
                raise ValueError("File content is offloaded. Cannot upload to GCS.")

            # For single FileStore scenario, expect string URL
            if isinstance(signed_url_or_dict, dict):
                raise ValueError(
                    "For Scenario created from FileStore, provide a single signed URL string, not a dictionary."
                )

            signed_url = signed_url_or_dict

            # Get file info from Scenario keys
            mime_type = self.scenario.get("mime_type", "application/octet-stream")
            suffix = self.scenario.get("suffix", "")

            # Decode and upload
            try:
                file_content = base64.b64decode(self.scenario["base64_string"])
            except Exception as e:
                raise ValueError(f"Failed to decode base64 content: {e}")

            headers = {
                "Content-Type": mime_type,
                "Content-Length": str(len(file_content)),
            }

            response = requests.put(signed_url, data=file_content, headers=headers)
            response.raise_for_status()

            upload_results.append(
                {
                    "type": "scenario_filestore_content",
                    "status": "success",
                    "status_code": response.status_code,
                    "file_size": len(file_content),
                    "mime_type": mime_type,
                    "file_extension": suffix,
                }
            )

        # Case 2: Find FileStore objects in Scenario values
        else:
            # Collect all FileStore keys first
            filestore_keys = [
                key for key, value in self.scenario.items() if isinstance(value, FileStore)
            ]

            if not filestore_keys:
                raise ValueError("No FileStore objects found in Scenario to upload.")

            # Handle URL parameter
            if isinstance(signed_url_or_dict, str):
                # Single URL provided for multiple FileStore objects - this will cause overwrites
                if len(filestore_keys) > 1:
                    raise ValueError(
                        f"Multiple FileStore objects found ({filestore_keys}) but only one signed URL provided. "
                        f"Provide a dictionary mapping keys to URLs to avoid overwrites: "
                        f"{{'{filestore_keys[0]}': 'url1', '{filestore_keys[1]}': 'url2', ...}}"
                    )

                # Single FileStore object, single URL is fine
                url_mapping = {filestore_keys[0]: signed_url_or_dict}

            elif isinstance(signed_url_or_dict, dict):
                # Dictionary of URLs provided
                missing_keys = set(filestore_keys) - set(signed_url_or_dict.keys())
                if missing_keys:
                    raise ValueError(
                        f"Missing signed URLs for FileStore keys: {list(missing_keys)}"
                    )

                extra_keys = set(signed_url_or_dict.keys()) - set(filestore_keys)
                if extra_keys:
                    raise ValueError(
                        f"Signed URLs provided for non-FileStore keys: {list(extra_keys)}"
                    )

                url_mapping = signed_url_or_dict

            else:
                raise ValueError(
                    "signed_url_or_dict must be either a string or a dictionary"
                )

            # Upload each FileStore object
            for key, value in self.scenario.items():
                if isinstance(value, FileStore):
                    try:
                        result = value.save_to_gcs_bucket(url_mapping[key])
                        result["scenario_key"] = key
                        result["type"] = "filestore_object"
                        upload_results.append(result)
                    except Exception as e:
                        upload_results.append(
                            {
                                "scenario_key": key,
                                "type": "filestore_object",
                                "status": "error",
                                "error": str(e),
                            }
                        )

        return {
            "total_uploads": len(upload_results),
            "successful_uploads": len(
                [r for r in upload_results if r.get("status") == "success"]
            ),
            "failed_uploads": len(
                [r for r in upload_results if r.get("status") == "error"]
            ),
            "upload_details": upload_results,
        }

    def get_filestore_info(self) -> dict:
        """
        Returns information about FileStore objects present in this Scenario.

        This method is useful for determining how many signed URLs need to be generated
        and what file extensions/types are present before calling save_to_gcs_bucket().

        Returns:
            dict: Information about FileStore objects containing:
                - total_count: Total number of FileStore objects
                - filestore_keys: List of scenario keys that contain FileStore objects
                - file_extensions: Dictionary mapping keys to file extensions
                - file_types: Dictionary mapping keys to MIME types
                - is_filestore_scenario: Boolean indicating if this Scenario was created from a FileStore
                - summary: Human-readable summary of files

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"text": "hello"})
            >>> gcs = ScenarioGCS(s)
            >>> info = gcs.get_filestore_info()
            >>> info['total_count']
            0
            >>> info['summary']
            'No FileStore objects found'
        """
        from edsl.scenarios import FileStore

        # Check if this Scenario was created from a FileStore
        is_filestore_scenario = "base64_string" in self.scenario and isinstance(
            self.scenario.get("base64_string"), str
        )

        if is_filestore_scenario:
            # Single FileStore scenario
            return {
                "total_count": 1,
                "filestore_keys": ["filestore_content"],
                "file_extensions": {"filestore_content": self.scenario.get("suffix", "")},
                "file_types": {
                    "filestore_content": self.scenario.get(
                        "mime_type", "application/octet-stream"
                    )
                },
                "is_filestore_scenario": True,
                "summary": f"Single FileStore content with extension '{self.scenario.get('suffix', 'unknown')}'",
            }

        # Regular Scenario with FileStore objects as values
        filestore_info = {}
        file_extensions = {}
        file_types = {}

        for key, value in self.scenario.items():
            if isinstance(value, FileStore):
                filestore_info[key] = {
                    "extension": getattr(value, "suffix", ""),
                    "mime_type": getattr(
                        value, "mime_type", "application/octet-stream"
                    ),
                    "binary": getattr(value, "binary", True),
                    "path": getattr(value, "path", "unknown"),
                }
                file_extensions[key] = getattr(value, "suffix", "")
                file_types[key] = getattr(
                    value, "mime_type", "application/octet-stream"
                )

        # Generate summary
        if filestore_info:
            ext_summary = [f"{key}({ext})" for key, ext in file_extensions.items()]
            summary = (
                f"{len(filestore_info)} FileStore objects: {', '.join(ext_summary)}"
            )
        else:
            summary = "No FileStore objects found"

        return {
            "total_count": len(filestore_info),
            "filestore_keys": list(filestore_info.keys()),
            "file_extensions": file_extensions,
            "file_types": file_types,
            "is_filestore_scenario": False,
            "detailed_info": filestore_info,
            "summary": summary,
        }

    def requires_upload(self) -> bool:
        """
        Check if this Scenario contains any content that can be uploaded to GCS.

        Returns:
            bool: True if the Scenario contains FileStore objects or base64 content,
                  False otherwise.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"text": "hello"})
            >>> gcs = ScenarioGCS(s)
            >>> gcs.requires_upload()
            False
        """
        info = self.get_filestore_info()
        return info["total_count"] > 0

    def get_upload_summary(self) -> str:
        """
        Get a human-readable summary of what would be uploaded.

        Returns:
            str: A summary describing the FileStore content ready for upload.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"text": "hello"})
            >>> gcs = ScenarioGCS(s)
            >>> gcs.get_upload_summary()
            'No FileStore objects found'
        """
        info = self.get_filestore_info()
        return info["summary"]

    def validate_signed_urls(self, signed_url_or_dict: Union[str, Dict[str, str]]) -> dict:
        """
        Validate that the provided signed URLs match the FileStore objects in the Scenario.

        Args:
            signed_url_or_dict: The signed URL(s) to validate against the Scenario content.

        Returns:
            dict: Validation results containing any errors or warnings.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"text": "hello"})
            >>> gcs = ScenarioGCS(s)
            >>> result = gcs.validate_signed_urls("https://example.com")
            >>> result['valid']
            False
        """
        info = self.get_filestore_info()
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "expected_keys": info["filestore_keys"],
            "total_filestore_objects": info["total_count"]
        }

        if info["total_count"] == 0:
            validation_result["valid"] = False
            validation_result["errors"].append("No FileStore objects found in Scenario to upload")
            return validation_result

        if info["is_filestore_scenario"]:
            # Single FileStore scenario - expect string URL
            if isinstance(signed_url_or_dict, dict):
                validation_result["valid"] = False
                validation_result["errors"].append(
                    "For Scenario created from FileStore, provide a single signed URL string, not a dictionary"
                )
        else:
            # Multiple FileStore objects - validate URL mapping
            filestore_keys = info["filestore_keys"]
            
            if isinstance(signed_url_or_dict, str):
                if len(filestore_keys) > 1:
                    validation_result["valid"] = False
                    validation_result["errors"].append(
                        f"Multiple FileStore objects found ({filestore_keys}) but only one signed URL provided"
                    )
            elif isinstance(signed_url_or_dict, dict):
                missing_keys = set(filestore_keys) - set(signed_url_or_dict.keys())
                if missing_keys:
                    validation_result["valid"] = False
                    validation_result["errors"].append(
                        f"Missing signed URLs for FileStore keys: {list(missing_keys)}"
                    )

                extra_keys = set(signed_url_or_dict.keys()) - set(filestore_keys)
                if extra_keys:
                    validation_result["warnings"].append(
                        f"Signed URLs provided for non-FileStore keys: {list(extra_keys)}"
                    )
            else:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    "signed_url_or_dict must be either a string or a dictionary"
                )

        return validation_result 