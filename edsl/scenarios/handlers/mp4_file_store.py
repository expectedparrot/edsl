import tempfile
from ..file_methods import FileMethods


class Mp4Methods(FileMethods):
    """
    Handler for MP4 video files.
    
    This class provides methods to handle MP4 video files in both notebook
    and system environments, including viewing and creating example videos.
    """
    suffix = "mp4"

    def view_system(self):
        """
        Open the MP4 file with the system's default video player.
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
                print(f"Error opening MP4: {e}")
        else:
            print("MP4 file was not found.")

    def view_notebook(self):
        """
        Display the MP4 video in a Jupyter notebook using IPython's HTML display.
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
            <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
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
        Create a simple example MP4 file.
        
        Uses FFmpeg to generate a test video pattern if available, 
        otherwise creates a minimal MP4 header.
        
        Returns:
            str: Path to the created example MP4 file
        """
        import os
        import subprocess
        
        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            output_path = f.name
        
        try:
            # Try to use ffmpeg to generate a test pattern video
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=30", 
                    "-vcodec", "libx264", "-pix_fmt", "yuv420p", output_path
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return output_path
        except (subprocess.SubprocessError, FileNotFoundError):
            # If ffmpeg is not available, create a tiny placeholder MP4 file
            # Using a simple empty binary file with the .mp4 extension
            with open(output_path, 'wb') as f:
                # Just write a simple 1KB file with MP4 signature
                f.write(b'\x00\x00\x00\x18\x66\x74\x79\x70\x6D\x70\x34\x32')  # MP4 file signature
                f.write(b'\x00' * 1000)  # Fill with zeros
            
            return output_path