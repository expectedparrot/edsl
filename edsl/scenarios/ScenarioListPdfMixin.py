import fitz  # PyMuPDF
import os
import copy
import subprocess
import requests
import tempfile
import os

# import urllib.parse as urlparse
from urllib.parse import urlparse

# from edsl import Scenario

import requests
import re
import tempfile
import os
import atexit
from urllib.parse import urlparse, parse_qs


class GoogleDriveDownloader:
    _temp_dir = None
    _temp_file_path = None

    @classmethod
    def fetch_from_drive(cls, url, filename=None):
        # Extract file ID from the URL
        file_id = cls._extract_file_id(url)
        if not file_id:
            raise ValueError("Invalid Google Drive URL")

        # Construct the download URL
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        # Send a GET request to the URL
        session = requests.Session()
        response = session.get(download_url, stream=True)
        response.raise_for_status()

        # Check for large file download prompt
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                params = {"id": file_id, "confirm": value}
                response = session.get(download_url, params=params, stream=True)
                break

        # Create a temporary file to save the download
        if not filename:
            filename = "downloaded_file"

        if cls._temp_dir is None:
            cls._temp_dir = tempfile.TemporaryDirectory()
            atexit.register(cls._cleanup)

        cls._temp_file_path = os.path.join(cls._temp_dir.name, filename)

        # Write the content to the temporary file
        with open(cls._temp_file_path, "wb") as f:
            for chunk in response.iter_content(32768):
                if chunk:
                    f.write(chunk)

        print(f"File saved to: {cls._temp_file_path}")

        return cls._temp_file_path

    @staticmethod
    def _extract_file_id(url):
        # Try to extract file ID from '/file/d/' format
        file_id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        if file_id_match:
            return file_id_match.group(1)

        # If not found, try to extract from 'open?id=' format
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if "id" in query_params:
            return query_params["id"][0]

        return None

    @classmethod
    def _cleanup(cls):
        if cls._temp_dir:
            cls._temp_dir.cleanup()

    @classmethod
    def get_temp_file_path(cls):
        return cls._temp_file_path


def fetch_and_save_pdf(url, filename):
    # Send a GET request to the URL
    response = requests.get(url)

    # Check if the request was successful
    response.raise_for_status()

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Construct the full path for the file
        temp_file_path = os.path.join(temp_dir, filename)

        # Write the content to the temporary file
        with open(temp_file_path, "wb") as file:
            file.write(response.content)

        print(f"PDF saved to: {temp_file_path}")

        # Here you can perform operations with the file
        # The file will be automatically deleted when you exit this block

    return temp_file_path


# Example usage:
# url = "https://example.com/sample.pdf"
# fetch_and_save_pdf(url, "sample.pdf")


class ScenarioListPdfMixin:
    @classmethod
    def from_pdf(cls, filename_or_url, collapse_pages=False):
        # Check if the input is a URL
        if cls.is_url(filename_or_url):
            # Check if it's a Google Drive URL
            if "drive.google.com" in filename_or_url:
                temp_filename = GoogleDriveDownloader.fetch_from_drive(
                    filename_or_url, "temp_pdf.pdf"
                )
            else:
                # For other URLs, use the previous fetch_and_save_pdf function
                temp_filename = fetch_and_save_pdf(filename_or_url, "temp_pdf.pdf")

            scenarios = list(cls.extract_text_from_pdf(temp_filename))
        else:
            # If it's not a URL, assume it's a local file path
            scenarios = list(cls.extract_text_from_pdf(filename_or_url))
        if not collapse_pages:
            return cls(scenarios)
        else:
            txt = ""
            for scenario in scenarios:
                txt += scenario["text"]
            from edsl.scenarios import Scenario

            base_scenario = copy.copy(scenarios[0])
            base_scenario["text"] = txt
        return base_scenario

    @staticmethod
    def is_url(string):
        try:
            result = urlparse(string)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    @classmethod
    def _from_pdf_to_image(cls, pdf_path, image_format="jpeg"):
        """
        Convert each page of a PDF into an image and create Scenario instances.

        :param pdf_path: Path to the PDF file.
        :param image_format: Format of the output images (default is 'jpeg').
        :return: ScenarioList instance containing the Scenario instances.
        """
        import tempfile
        from pdf2image import convert_from_path
        from edsl.scenarios import Scenario

        with tempfile.TemporaryDirectory() as output_folder:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            scenarios = []

            # Save each page as an image and create Scenario instances
            for i, image in enumerate(images):
                image_path = os.path.join(output_folder, f"page_{i+1}.{image_format}")
                image.save(image_path, image_format.upper())

                scenario = Scenario._from_filepath_image(image_path)
                scenarios.append(scenario)

            # print(f"Saved {len(images)} pages as images in {output_folder}")
            return cls(scenarios)

    @staticmethod
    def extract_text_from_pdf(pdf_path):
        from edsl import Scenario

        # TODO: Add test case
        # Ensure the file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file {pdf_path} does not exist.")

        # Open the PDF file
        document = fitz.open(pdf_path)

        # Get the filename from the path
        filename = os.path.basename(pdf_path)

        # Iterate through each page and extract text
        for page_num in range(len(document)):
            page = document.load_page(page_num)
            text = page.get_text()

            # Create a dictionary for the current page
            page_info = {"filename": filename, "page": page_num + 1, "text": text}
            yield Scenario(page_info)

    def create_hello_world_pdf(pdf_path):
        # LaTeX content
        latex_content = r"""
        \documentclass{article}
        \title{Hello World}
        \author{John}
        \date{\today}
        \begin{document}
        \maketitle
        \section{Hello, World!}
        This is a simple hello world example created with LaTeX and Python.
        \end{document}
        """

        # Create a .tex file
        tex_filename = pdf_path + ".tex"
        with open(tex_filename, "w") as tex_file:
            tex_file.write(latex_content)

        # Compile the .tex file to PDF
        subprocess.run(["pdflatex", tex_filename], check=True)

        # Optionally, clean up auxiliary files generated by pdflatex
        aux_files = [pdf_path + ext for ext in [".aux", ".log"]]
        for aux_file in aux_files:
            try:
                os.remove(aux_file)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    pass

    # from edsl import ScenarioList

    # class ScenarioListNew(ScenarioList, ScenaroListPdfMixin):
    #     pass

    # #ScenarioListNew.create_hello_world_pdf('hello_world')
    # #scenarios = ScenarioListNew.from_pdf('hello_world.pdf')
    # #print(scenarios)

    # from edsl import ScenarioList, QuestionFreeText
    # homo_silicus = ScenarioList.from_pdf('w31122.pdf')
    # q = QuestionFreeText(question_text = "What is the key point of the text in {{ text }}?", question_name = "key_point")
    # results = q.by(homo_silicus).run(progress_bar = True)
    # results.select('scenario.page', 'answer.key_point').order_by('page').print()
