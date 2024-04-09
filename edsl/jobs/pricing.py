# TODO: Move this to a more appropriate location
from edsl.jobs.tokens.TokenPricing import TokenPricing

# , InterviewTokenUsage

pricing = {
    "gpt-3.5-turbo": TokenPricing(
        model_name="gpt-3.5-turbo",
        prompt_token_price_per_k=0.0005,
        completion_token_price_per_k=0.0015,
    ),
    "gpt-4-1106-preview": TokenPricing(
        model_name="gpt-4",
        prompt_token_price_per_k=0.01,
        completion_token_price_per_k=0.03,
    ),
    "test": TokenPricing(
        model_name="test",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "gemini_pro": TokenPricing(
        model_name="gemini_pro",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "llama-2-13b-chat-hf": TokenPricing(
        model_name="llama-2-13b-chat-hf",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "llama-2-70b-chat-hf": TokenPricing(
        model_name="llama-2-70b-chat-hf",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "mixtral-8x7B-instruct-v0.1": TokenPricing(
        model_name="mixtral-8x7B-instruct-v0.1",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
}
