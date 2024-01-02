"""This question type is for option sets that are too large to read into the LLM.
We instead compute embeddings of the options, ask the LLM the question as free text, 
create an embedding of the LLM's answer and compare the embeddings, and ask 
the LLM to select the best option among the subset of close embeddings. 

Steps:
1. Compute embeddings for the option set.
2. Ask the LLM to answer the ultimate question (as free text).
3. Create an embedding of the LLM's answer.
4. Compare the embeddings.
5. Create a multiple choice question with the close embeddings as options.
6. Ask the LLM to answer the multiple choice question.
7. Validate the answer to the multiple choice question.

Can we turn a survey back into a question?
Can we question-ify a survey?

Use Agent differently
Similar to theme finder 


Consider
- Add a special attribute to a question
- Have agent check whether attribute exists
- Answer question the different way

Create a different kind of question that looks the same to the end user
but has a different way of getting answered.
"""
