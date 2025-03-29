from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from ..display import HTML
    from ..scenarios import FileStore


class ConstructDownloadLink:
    """Create HTML download links for FileStore objects.

    This class generates downloadable HTML links for FileStore objects that can be
    displayed in Jupyter notebooks or other web interfaces. The links are styled
    and allow for custom filenames and styling options.

    Examples:
        >>> from edsl import FileStore
        >>> fs = FileStore.example("txt")
        >>> link = ConstructDownloadLink(fs)
        >>> new_link = link.create_link()
    """

    def __init__(self, filestore: FileStore):
        """Initialize a new download link constructor.

        Args:
            filestore: A FileStore object containing the file to be made downloadable.
        """
        self.filestore = filestore

    def create_link(
        self, custom_filename: Optional[str] = None, style: Optional[dict] = None
    ) -> HTML:
        """Create an HTML download link wrapped in an HTML display object.

        Args:
            custom_filename: Optional custom name for the downloaded file.
                If None, uses the original filename.
            style: Optional dictionary of CSS styles for the download button.
                If None, uses default styling.

        Returns:
            HTML: A displayable HTML object containing the styled download link.
        """
        from ..display import HTML

        html = self.html_create_link(custom_filename, style)
        return HTML(html)

    def html_create_link(
        self, custom_filename: Optional[str] = None, style: Optional[dict] = None
    ) -> str:
        """Generate an HTML download link string.

        Creates a styled HTML anchor tag that triggers a file download when clicked.
        The file data is embedded as a base64-encoded data URI.

        Args:
            custom_filename: Optional custom name for the downloaded file.
                If None, uses the original filename.
            style: Optional dictionary of CSS styles for the download button.
                If None, uses default styling.

        Returns:
            str: HTML string containing the styled download link.
        """

        # Get filename from path or use custom filename
        original_filename = os.path.basename(self.filestore.path)
        filename = custom_filename or original_filename

        # Use the base64 string already stored in FileStore
        b64_data = self.filestore.base64_string

        # Use mime type from FileStore or guess it
        mime_type = self.filestore.mime_type

        # Default style if none provided
        default_style = {
            "background-color": "#4CAF50",
            "color": "white",
            "padding": "10px 20px",
            "text-decoration": "none",
            "border-radius": "4px",
            "display": "inline-block",
            "margin": "10px 0",
            "font-family": "sans-serif",
            "cursor": "pointer",
        }

        button_style = style or default_style
        style_str = "; ".join(f"{k}: {v}" for k, v in button_style.items())

        html = f"""
        <a download="{filename}" 
           href="data:{mime_type};base64,{b64_data}" 
           style="{style_str}">
            Download {filename}
        </a>
        """
        return html

    def create_multiple_links(
        self,
        files: List["FileStore"],
        custom_filenames: Optional[List[Optional[str]]] = None,
        style: Optional[dict] = None,
    ) -> HTML:
        """Create multiple download links in a horizontal layout.

        Generates a collection of download links arranged horizontally with consistent
        styling. Useful for providing different versions of the same file or related
        files together.

        Args:
            files: List of FileStore objects to create download links for.
            custom_filenames: Optional list of custom filenames for downloads.
                If None, original filenames will be used for all files.
            style: Optional dictionary of CSS styles applied to all download buttons.
                If None, uses default styling.

        Returns:
            HTML: A displayable HTML object containing all download links arranged
                horizontally.
        """
        if custom_filenames is None:
            custom_filenames = [None] * len(files)

        html_parts = []
        for file_obj, custom_name in zip(files, custom_filenames):
            link_creator = ConstructDownloadLink(file_obj)
            html_parts.append(
                link_creator.create_link(
                    custom_filename=custom_name, style=style
                )._repr_html_()
            )

        from ..display import HTML

        return HTML(
            '<div style="display: flex; gap: 10px;">' + "".join(html_parts) + "</div>"
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
