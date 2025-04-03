from ..jobs.fetch_invigilator import FetchInvigilator
from ..scenarios import FileStore

import math

# Model configs: base tokens and tile tokens only
VISION_MODELS = {
    "gpt-4o": {
        "base_tokens": 85,
        "tile_tokens": 170,
    },
    "gpt-4o-mini": {
        "base_tokens": 2833,
        "tile_tokens": 5667,
    },
    "o1": {
        "base_tokens": 75,
        "tile_tokens": 150,
    },
}


def estimate_tokens(model_name, width, height):
    if model_name == "test":
        return 10  # for testing purposes

    if "claude" in model_name:
        total_tokens = width * height / 750
        return total_tokens
    if model_name not in VISION_MODELS:
        raise ValueError(f"Unknown model: {model_name}")

    config = VISION_MODELS[model_name]
    TILE_SIZE = 512

    tiles_x = math.ceil(width / TILE_SIZE)
    tiles_y = math.ceil(height / TILE_SIZE)
    total_tiles = tiles_x * tiles_y

    total_tokens = config["base_tokens"] + config["tile_tokens"] * total_tiles
    return total_tokens


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
                        if file.is_image():
                            model_name = self.interview.model.model
                            width, height = file.get_image_dimensions()
                            token_usage = estimate_tokens(model_name, width, height)
                            file_tokens += token_usage
                        else:
                            file_tokens += file.size * 0.25
            else:
                from .exceptions import InterviewTokenError

                raise InterviewTokenError(f"Prompt is of type {type(prompt)}")
        result: float = len(combined_text) / 4.0 + file_tokens
        return result


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
