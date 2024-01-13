class Prompt:
    def __init__(self, text):
        self.text

    def __add__(self, other_prompt):
        return Prompt(text=self.text + other_prompt.text)
