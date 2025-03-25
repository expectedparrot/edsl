from ..jobs.fetch_invigilator import FetchInvigilator
from ..scenarios import FileStore


class RequestTokenEstimator:
    """Estimate the number of tokens that will be required to run the focal task."""

    def __init__(self, interview):
        self.interview = interview

    def __call__(self, question) -> float:
        """Estimate the number of tokens that will be required to run the focal task."""

        invigilator = FetchInvigilator(self.interview)(question=question)

        # TODO: There should be a way to get a more accurate estimate.
        combined_text = ""
        file_tokens = 0
        for prompt in invigilator.get_prompts().values():
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            elif isinstance(prompt, str):
                combined_text += prompt
            elif isinstance(prompt, list):
                for file in prompt:
                    if isinstance(file, FileStore):
                        file_tokens += file.size * 0.25
            else:
                from .exceptions import InterviewTokenError
                raise InterviewTokenError(f"Prompt is of type {type(prompt)}")
        result: float = len(combined_text) / 4.0 + file_tokens
        return result



if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
