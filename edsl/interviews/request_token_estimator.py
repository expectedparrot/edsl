from ..jobs.fetch_invigilator import FetchInvigilator
from ..scenarios import FileStore


def request_token_estimator(interview, question):
    """Estimate the number of tokens that will be required to run the focal task."""
    invigilator = FetchInvigilator(interview)(question=question)

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
    return len(combined_text) / 4.0 + file_tokens



if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
