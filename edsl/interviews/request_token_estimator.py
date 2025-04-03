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


def approximate_image_tokens_google(width: int, height: int) -> int:
    """
    Approximates the token usage for an image based on its dimensions.

    This calculation is based on the rules described for Gemini 2.0 models
    in the provided text:
    - Images with both dimensions <= 384px cost 258 tokens.
    - Larger images are processed in 768x768 tiles, each costing 258 tokens.

    Note: This is an *approximation*. The exact cropping, scaling, and tiling
    strategy used by the actual Gemini API might differ slightly.

    Args:
        width: The width of the image in pixels.
        height: The height of the image in pixels.

    Returns:
        An estimated integer token count for the image.

    Raises:
        ValueError: If width or height are not positive integers.
    """
    SMALL_IMAGE_THRESHOLD = 384  # Max dimension for fixed token count
    FIXED_TOKEN_COST_SMALL = 258  # Token cost for small images (<= 384x384)
    TILE_SIZE = 768  # Dimension of tiles for larger images
    TOKEN_COST_PER_TILE = 258  # Token cost per 768x768 tile
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("Image width and height must be positive integers.")

    # Case 1: Small image (both dimensions <= threshold)
    if width <= SMALL_IMAGE_THRESHOLD and height <= SMALL_IMAGE_THRESHOLD:
        return FIXED_TOKEN_COST_SMALL

    # Case 2: Larger image (at least one dimension > threshold)
    else:
        # Calculate how many tiles are needed to cover the width and height
        # Use ceiling division to ensure full coverage
        tiles_wide = math.ceil(width / TILE_SIZE)
        tiles_high = math.ceil(height / TILE_SIZE)

        # Total number of tiles is the product of tiles needed in each dimension
        total_tiles = tiles_wide * tiles_high

        # Total token cost is the number of tiles times the cost per tile
        estimated_tokens = total_tiles * TOKEN_COST_PER_TILE
        return estimated_tokens


def estimate_tokens(model_name, width, height):
    if model_name == "test":
        return 10  # for testing purposes
    if "gemini" in model_name:
        out = approximate_image_tokens_google(width, height)
        return out
    if "claude" in model_name:
        total_tokens = width * height / 750
        return total_tokens
    if model_name not in VISION_MODELS:
        total_tokens = width * height / 750
        return total_tokens

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
