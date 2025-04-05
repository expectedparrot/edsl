import tempfile
from ..file_methods import FileMethods


class WebmMethods(FileMethods):
    """
    Handler for WebM video files.
    
    This class provides methods to handle WebM video files in both notebook
    and system environments, including viewing and creating example videos.
    WebM is an open, royalty-free video format designed for the web.
    """
    suffix = "webm"

    def view_system(self):
        """
        Open the WebM file with the system's default video player.
        """
        import os
        import subprocess

        if os.path.exists(self.path):
            try:
                if (os_name := os.name) == "posix":
                    subprocess.run(["open", self.path], check=True)  # macOS
                elif os_name == "nt":
                    os.startfile(self.path)  # Windows
                else:
                    subprocess.run(["xdg-open", self.path], check=True)  # Linux
            except Exception as e:
                print(f"Error opening WebM: {e}")
        else:
            print("WebM file was not found.")

    def view_notebook(self):
        """
        Display the WebM video in a Jupyter notebook using IPython's HTML display.
        """
        from IPython.display import HTML, display
        import base64
        
        # Read the video file and encode it as base64
        with open(self.path, 'rb') as f:
            video_data = f.read()
        
        video_base64 = base64.b64encode(video_data).decode('utf-8')
        
        # Create an HTML5 video element with the base64-encoded video
        video_html = f"""
        <video width="640" height="360" controls>
            <source src="data:video/webm;base64,{video_base64}" type="video/webm">
            Your browser does not support the video tag.
        </video>
        """
        
        display(HTML(video_html))

    def extract_text(self):
        """
        Extract text from the video using subtitle extraction (if available).
        Currently returns a message that text extraction is not supported for videos.
        
        Returns:
            str: Message indicating text extraction is not supported
        """
        return "Text extraction is not supported for video files."

    def example(self):
        """
        Create a simple example WebM file.
        
        Uses FFmpeg to generate a test video pattern in WebM format if available,
        otherwise creates a minimal WebM header.
        
        Returns:
            str: Path to the created example WebM file
        """
        import os
        import subprocess
        
        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
            output_path = f.name
        
        try:
            # Try to use ffmpeg to generate a test pattern video in WebM format
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=30", 
                    "-c:v", "libvpx", "-b:v", "1M", output_path
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return output_path
        except (subprocess.SubprocessError, FileNotFoundError):
            # If ffmpeg is not available, create a minimal WebM file
            with open(output_path, 'wb') as f:
                # WebM starts with EBML header (1A 45 DF A3)
                f.write(b'\x1A\x45\xDF\xA3')  # EBML signature
                f.write(b'\x00' * 1000)  # Fill with zeros
            
            return output_path