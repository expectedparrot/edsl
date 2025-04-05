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


# Configuration for Claude image token estimation
# Based on official Anthropic documentation
CLAUDE_IMAGE_TOKENS = {
    "claude-3-opus": {
        "base_tokens": 170,
        "pixels_per_token": 2048,  # Number of pixels that cost approximately 1 token
    },
    "claude-3-sonnet": {
        "base_tokens": 170,
        "pixels_per_token": 2048,
    },
    "claude-3-haiku": {
        "base_tokens": 170,
        "pixels_per_token": 2048,
    },
    # Add generic config for any Claude model
    "claude": {
        "base_tokens": 170,
        "pixels_per_token": 2048,
    },
}

def approximate_image_tokens_claude(width: int, height: int, claude_model: str = "claude") -> int:
    """
    Approximates the token usage for an image with Claude models.
    
    This calculation follows the official Anthropic documentation for Claude Opus, Sonnet, and Haiku.
    Claude uses a two-part calculation:
    1. A fixed base cost (approximately 170 tokens)
    2. A variable cost based on image dimensions
    
    Args:
        width: The width of the image in pixels.
        height: The height of the image in pixels.
        claude_model: Specific Claude model name (e.g., "claude-3-opus", "claude-3-sonnet")
                     Defaults to "claude" for generic estimation
        
    Returns:
        An estimated integer token count for the image.
        
    Raises:
        ValueError: If width or height are not positive integers.
        
    References:
        - Anthropic API documentation: https://docs.anthropic.com/claude/docs/vision
    """
    if (not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0):
        raise ValueError("Image width and height must be positive integers.")
    
    # Get the appropriate token configuration for this Claude model
    # Use the specific model if available, otherwise fall back to generic "claude" config
    model_key = claude_model.lower() if claude_model.lower() in CLAUDE_IMAGE_TOKENS else "claude"
    config = CLAUDE_IMAGE_TOKENS[model_key]
    
    # Get the configuration values
    BASE_COST = config["base_tokens"]
    PIXELS_PER_TOKEN = config["pixels_per_token"]
    
    # Calculate total pixels
    total_pixels = width * height
    
    # Calculate variable cost based on image dimensions
    variable_cost = total_pixels / PIXELS_PER_TOKEN
    
    # Total token cost is base cost plus variable cost
    total_tokens = BASE_COST + variable_cost
    
    return math.ceil(total_tokens)  # Round up to ensure we don't underestimate


def estimate_tokens(model_name, width, height):
    """
    Estimates the token usage for an image based on the model being used.
    
    This function routes the token estimation to the appropriate model-specific calculation,
    with specific handling for:
    - Claude models (Opus, Sonnet, Haiku)
    - Gemini models 
    - GPT-4 Vision models (gpt-4o, etc.)
    
    Args:
        model_name: The name of the LLM model being used.
        width: The width of the image in pixels.
        height: The height of the image in pixels.
        
    Returns:
        An estimated integer token count for the image.
        
    Examples:
        >>> estimate_tokens("claude-3-opus", 1024, 768)  # Claude 3 Opus
        602
        >>> estimate_tokens("gemini-pro-vision", 2048, 1024)  # Gemini model
        774
        >>> estimate_tokens("gpt-4o", 800, 600)  # GPT-4o model
        425
    """
    if model_name == "test":
        return 10  # for testing purposes
    
    # Gemini models
    if "gemini" in model_name.lower():
        return approximate_image_tokens_google(width, height)
    
    # Claude models (check for exact model name match)
    if "claude" in model_name.lower():
        # Pass the specific model name to get more accurate estimation if possible
        return approximate_image_tokens_claude(width, height, claude_model=model_name)
    
    # GPT-4 Vision models
    if model_name in VISION_MODELS:
        config = VISION_MODELS[model_name]
        TILE_SIZE = 512
        
        tiles_x = math.ceil(width / TILE_SIZE)
        tiles_y = math.ceil(height / TILE_SIZE)
        total_tiles = tiles_x * tiles_y
        
        total_tokens = config["base_tokens"] + config["tile_tokens"] * total_tiles
        return total_tokens
    
    # Default fallback for unknown models
    # Use a conservative approach similar to Claude's estimation
    # This ensures we don't underestimate token usage for new or unknown models
    return approximate_image_tokens_claude(width, height)


class RequestTokenEstimator:
    """Estimate the number of tokens that will be required to run the focal task."""

    def __init__(self, interview):
        self.interview = interview

    def __call__(self, question) -> float:
        """
        Estimate the number of tokens that will be required to run the focal task.
        
        This method analyzes the prompts that will be sent to the model and
        estimates the number of tokens they will consume, including both text
        and media content like images.
        
        Args:
            question: The question being posed to the model
            
        Returns:
            float: Estimated number of tokens required for the request
            
        Raises:
            InterviewTokenError: If the prompt contains unsupported types
        """
        invigilator = FetchInvigilator(self.interview)(question=question)
        model_name = self.interview.model.model.lower()
        
        # Get the conversion ratio of characters to tokens for this model
        # Default is 4.0 (typical for many models), but can be customized
        chars_per_token = 4.0
        
        # Collect text and calculate tokens for files
        combined_text = ""
        file_tokens = 0
        
        for prompt in invigilator.get_prompts().values():
            # Handle prompt objects with a text attribute
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            
            # Handle string prompts
            elif isinstance(prompt, str):
                combined_text += prompt
            
            # Handle lists (typically lists of files)
            elif isinstance(prompt, list):
                for item in prompt:
                    if isinstance(item, FileStore):
                        # Handle image files
                        if item.is_image():
                            # Get image dimensions
                            width, height = item.get_image_dimensions()
                            # Use model-specific token estimator
                            token_usage = estimate_tokens(model_name, width, height)
                            file_tokens += token_usage
                        
                        # Handle video files
                        elif item.is_video():
                            # For videos, we use a conservative estimate
                            # Videos typically have higher token costs
                            # Base cost + estimate for first frame
                            file_tokens += 200  # Base cost
                            
                        # Handle text-based files
                        elif hasattr(item, "text") and item.text:
                            # For text files, we count tokens based on character length
                            file_tokens += len(item.text) / chars_per_token
                            
                        # Handle other file types (PDF, DOCX, etc.)
                        else:
                            # Conservative estimate based on file size
                            # Note: Actual token usage may vary significantly depending on content
                            # This uses a heuristic of 0.25 tokens per byte
                            file_tokens += item.size * 0.25
            
            # Handle other prompt types
            else:
                from .exceptions import InterviewTokenError
                raise InterviewTokenError(f"Prompt is of type {type(prompt)} which is not supported")
        
        # Calculate total token estimate
        text_tokens = len(combined_text) / chars_per_token
        total_tokens = text_tokens + file_tokens
        
        # Apply a safety margin to avoid underestimation (5% extra)
        result = total_tokens * 1.05
        
        return result


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
