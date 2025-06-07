import gradio as gr
from edsl.coop import Coop
from edsl import QuestionFreeText 

coop = Coop()                 # no API-key required yet

def run_my_process(question: str):
    """
    Placeholder for the process that will be executed when the user presses the button.
    Replace the body of this function with your own implementation.
    """
    if question.strip() == "":
        return "⚠️ Please enter a question before running the process."
    
    try:
        q = QuestionFreeText(question_name = "example", 
                             question_text = question
        )
        results = q.run()
        return str(results.select("example").to_list()[0])
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Use the dedicated login_gradio method which creates its own Gradio interface
# This will handle the login flow and return the interface
login_interface = coop.login_gradio(launch=False)

# Create main application interface  
def create_main_app():
    with gr.Blocks(title="EDSL Main Interface") as main_app:
        gr.Markdown("# EDSL Gradio Interface")
        gr.Markdown("✅ **Ready to use EDSL with remote features!**")
        
        # Input area for the user's question
        question_text = gr.Textbox(
            label="Ask a question:",
            placeholder="Enter your question here...",
            lines=3
        )
        
        # Buttons
        with gr.Row():
            run_button = gr.Button("Run Process", variant="primary")
            clear_button = gr.Button("Clear", variant="secondary")
        
        # Output area
        output = gr.Textbox(
            label="Results:",
            lines=8,
            interactive=False
        )
        
        # Event handlers
        run_button.click(
            fn=run_my_process,
            inputs=question_text,
            outputs=output
        )
        
        clear_button.click(
            fn=lambda: ("", ""),
            outputs=[question_text, output]
        )
    
    return main_app

# Create the combined interface with tabs
with gr.Blocks(title="EDSL Gradio Demo") as demo:
    gr.Markdown("# Expected Parrot EDSL - Gradio Demo")
    
    with gr.Tabs():
        with gr.Tab("🔐 Login"):
            # Embed the login interface
            login_interface.render()
        
        with gr.Tab("🚀 EDSL Interface"):
            create_main_app()

if __name__ == "__main__":
    demo.launch(share = True)