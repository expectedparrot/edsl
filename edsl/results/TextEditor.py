try:
    import gradio as gr
except ImportError:
    print("Gradio is not installed. Please install it using `pip install gradio`")

import time


class TextEditor:
    def __init__(self, initial_text=""):
        self.text = initial_text
        self._text_saved = False

    def save_text(self, new_text):
        self.text = new_text
        self._text_saved = True
        return "Text saved successfully!"

    def edit_gui(self):
        js_code = """
        async (text) => {
            await navigator.clipboard.writeText(text);
            return "Copied to clipboard!";
        }
        """

        with gr.Blocks() as interface:
            text_area = gr.Textbox(
                value=self.text, lines=10, label="Edit Text", placeholder="Type here..."
            )

            with gr.Row():
                save_btn = gr.Button("Save")
                copy_btn = gr.Button("Copy to Clipboard")

            output = gr.Textbox(label="Status")

            save_btn.click(fn=self.save_text, inputs=[text_area], outputs=[output])

            # Add copy functionality
            copy_btn.click(
                fn=None, inputs=text_area, outputs=output, api_name=False, js=js_code
            )

        interface.launch(share=False, prevent_thread_lock=True)

        while not self._text_saved:
            time.sleep(0.1)

        return self.text
