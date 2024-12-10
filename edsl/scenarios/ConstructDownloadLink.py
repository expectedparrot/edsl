from IPython.display import HTML
import os
import mimetypes


class ConstructDownloadLink:
    """
    A class to create HTML download links for FileStore objects.
    The links can be displayed in Jupyter notebooks or other web interfaces.
    """

    def __init__(self, filestore):
        """
        Initialize with a FileStore object.

        Args:
            filestore: A FileStore object containing the file to be made downloadable
        """
        self.filestore = filestore

    def create_link(self, custom_filename=None, style=None):
        """
        Create an HTML download link for the file.

        Args:
            custom_filename (str, optional): Custom name for the downloaded file.
                                          If None, uses original filename.
            style (dict, optional): Custom CSS styles for the download button.
                                  If None, uses default styling.

        Returns:
            IPython.display.HTML: HTML object containing the download link
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

        return HTML(html)

    def create_multiple_links(self, files, custom_filenames=None, style=None):
        """
        Create multiple download links at once.
        Useful when you want to provide different versions of the same file
        or related files together.

        Args:
            files (list): List of FileStore objects
            custom_filenames (list, optional): List of custom filenames for downloads
            style (dict, optional): Custom CSS styles for the download buttons

        Returns:
            IPython.display.HTML: HTML object containing all download links
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

        return HTML(
            '<div style="display: flex; gap: 10px;">' + "".join(html_parts) + "</div>"
        )


# Example usage:
"""
# Create download link with default styling
filestore_obj = FileStore.example()  # Your FileStore object
download_link = ConstructDownloadLink(filestore_obj)
display(download_link.create_link())

# Create download link with custom styling
custom_style = {
    'background-color': '#007bff',
    'color': 'white',
    'padding': '12px 24px',
    'border-radius': '8px'
}
display(download_link.create_link(
    custom_filename='my_file.txt',
    style=custom_style
))

# Create multiple download links
files = [FileStore.example(), FileStore.example('csv')]
custom_names = ['file1.txt', 'data.csv']
display(download_link.create_multiple_links(
    files,
    custom_filenames=custom_names
))
"""
