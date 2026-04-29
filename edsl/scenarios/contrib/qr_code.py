"""
QR Code generation and display for URLs in scenarios.

This module provides QRCode class for generating QR codes from URLs,
with context-aware display for both Jupyter notebooks and terminal environments.
"""

import re
from typing import TYPE_CHECKING, List
from io import BytesIO

if TYPE_CHECKING:
    from .scenario import Scenario


class QRCode:
    """
    A class representing a QR code with context-aware display capabilities.

    This class generates QR codes from URLs and provides different display
    methods depending on the context (Jupyter notebook vs terminal).

    Attributes:
        url: The URL encoded in the QR code
        _image: Cached PIL Image object of the QR code
    """

    def __init__(self, url: str):
        """
        Initialize a QRCode instance.

        Args:
            url: The URL to encode as a QR code
        """
        self.url = url
        self._image = None

    @property
    def image(self):
        """
        Lazy-load and cache the QR code image.

        Returns:
            PIL.Image: The QR code as a PIL Image object
        """
        if self._image is None:
            try:
                import qrcode
            except ImportError:
                raise ImportError(
                    "qrcode library is required for QR code generation. "
                    'Install it with: pip install "qrcode[pil]"'
                )

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.url)
            qr.make(fit=True)
            self._image = qr.make_image(fill_color="black", back_color="white")

        return self._image

    def _repr_html_(self) -> str:
        """
        HTML representation for Jupyter notebooks.

        Returns:
            str: HTML string with embedded base64 image and URL caption
        """
        import base64

        # Convert image to base64
        buffer = BytesIO()
        self.image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        # Create HTML with image and caption
        html = f"""
        <div style="display: inline-block; margin: 10px; text-align: center;">
            <img src="data:image/png;base64,{img_str}" style="max-width: 200px;">
            <div style="margin-top: 5px; font-size: 12px; word-wrap: break-word; max-width: 200px;">
                <a href="{self.url}" target="_blank">{self.url}</a>
            </div>
        </div>
        """
        return html

    def __repr__(self) -> str:
        """
        String representation for terminal/console.

        Returns:
            str: String representation of the QR code
        """
        # Check if we're in a Jupyter environment
        try:
            get_ipython()
            # In IPython/Jupyter, _repr_html_ will be called instead
            return f"QRCode({self.url})"
        except NameError:
            # In terminal, display as ASCII or save to file
            return f"QRCode for: {self.url}"

    def save(self, filepath: str) -> None:
        """
        Save the QR code as a PNG file.

        Args:
            filepath: Path where the PNG file should be saved
        """
        self.image.save(filepath)

    def display_terminal(self) -> None:
        """
        Display the QR code in the terminal as ASCII art (if supported).
        """
        try:
            import qrcode

            qr = qrcode.QRCode()
            qr.add_data(self.url)
            qr.make()
            qr.print_ascii()
        except ImportError:
            print(f"QR Code for: {self.url}")
            print(
                'Install qrcode library to display QR codes: pip install "qrcode[pil]"'
            )


class QRCodeList:
    """
    A collection of QR codes with context-aware batch display.

    This class holds multiple QRCode objects and provides methods to display
    them appropriately based on the environment (Jupyter notebook vs terminal).
    """

    def __init__(self, qr_codes: List[QRCode]):
        """
        Initialize a QRCodeList.

        Args:
            qr_codes: List of QRCode objects
        """
        self.qr_codes = qr_codes

    def _repr_html_(self) -> str:
        """
        HTML representation for Jupyter notebooks showing all QR codes.

        Returns:
            str: HTML string with all QR codes in a grid layout
        """
        html_parts = ['<div style="display: flex; flex-wrap: wrap;">']
        for qr in self.qr_codes:
            html_parts.append(qr._repr_html_())
        html_parts.append("</div>")
        return "".join(html_parts)

    def __repr__(self) -> str:
        """
        String representation for terminal/console.

        Returns:
            str: String listing all URLs
        """
        # Check if we're in a Jupyter environment
        try:
            get_ipython()
            return f"QRCodeList({len(self.qr_codes)} QR codes)"
        except NameError:
            # In terminal, just list the URLs
            return f"QRCodeList with {len(self.qr_codes)} QR code(s):\n" + "\n".join(
                f"  - {qr.url}" for qr in self.qr_codes
            )

    def __len__(self) -> int:
        """Return the number of QR codes."""
        return len(self.qr_codes)

    def __getitem__(self, index: int) -> QRCode:
        """Get a QR code by index."""
        return self.qr_codes[index]

    def save_all(self, directory: str, prefix: str = "qr_") -> List[str]:
        """
        Save all QR codes to a directory.

        Args:
            directory: Directory path where files should be saved
            prefix: Prefix for filenames (default: "qr_")

        Returns:
            List of file paths where QR codes were saved
        """
        import os

        os.makedirs(directory, exist_ok=True)

        saved_paths = []
        for i, qr in enumerate(self.qr_codes):
            filepath = os.path.join(directory, f"{prefix}{i}.png")
            qr.save(filepath)
            saved_paths.append(filepath)

        return saved_paths

    def display_terminal(self) -> None:
        """
        Display all QR codes in the terminal.
        """
        for i, qr in enumerate(self.qr_codes):
            print(f"\n--- QR Code {i+1}/{len(self.qr_codes)} ---")
            print(f"URL: {qr.url}")
            qr.display_terminal()


def extract_urls_from_scenario(scenario: "Scenario") -> List[str]:
    """
    Extract all URLs from a Scenario's values.

    Args:
        scenario: A Scenario object to extract URLs from

    Returns:
        List of URLs found in the scenario values
    """
    # Pattern to match http://, https://, ftp:// URLs
    url_pattern = r'https?://[^\s<>"\'\)]+|ftp://[^\s<>"\'\)]+'

    urls = []
    for value in scenario.values():
        if isinstance(value, str):
            # Find all URLs in the string
            found_urls = re.findall(url_pattern, value)
            urls.extend(found_urls)

    return urls
