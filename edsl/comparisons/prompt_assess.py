# Length of the prompt
# Conherence
# Duplication

compress_prompt = "Please compress this narrative to be more concise and coherent. Remove duplicative information."


class PromptAssess:
    def __init__(self, prompt):
        self.prompt = prompt

    def assess_length(self):
        return len(self.prompt)

    def assess_coherence(self):
        return
