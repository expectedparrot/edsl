class Prompt:
    def __init__(self, text):
        self.text = text

    def __add__(self, other_prompt):
        if isinstance(other_prompt, str):
            return self.text + other_prompt
        else:
            return Prompt(text=self.text + other_prompt.text)

    def __str__(self):
        return self.text

    def __contains__(self, text_to_check):
        return text_to_check in self.text
