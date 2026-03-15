class DocxScenario:
    def __init__(self, docx_path: str):
        from docx import Document

        self.doc = Document(docx_path)
        self.docx_path = docx_path

    def get_scenario_dict(self) -> dict:
        # Extract all text
        full_text = []
        for para in self.doc.paragraphs:
            full_text.append(para.text)

        # Join the text from all paragraphs
        text = "\n".join(full_text)
        return {"file_path": self.docx_path, "text": text}
