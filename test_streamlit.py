import streamlit as st
from edsl.coop import Coop
from edsl import QuestionFreeText 
coop = Coop()                 # no API-key required yet
api_key = coop.login_streamlit()   # renders link + handles polling & storage

def run_my_process(question: str):
    """
    Placeholder for the process that will be executed when the user presses the button.
    Replace the body of this function with your own implementation.
    """
    q = QuestionFreeText(question_name = "example", 
                         question_text = question
    )
    results = q.run()
    return results.select("example")

if api_key:
    st.success("Ready to use EDSL with remote features!")
    st.write(api_key)
    # Input area for the user's question
    question_text = st.text_area("Ask a question:", key="question_input")

    # Button to trigger the user-defined process
    if st.button("Run Process"):
        if question_text.strip() == "":
            st.warning("Please enter a question before running the process.")
        else:
            result = run_my_process(question_text)
            st.write(result)

