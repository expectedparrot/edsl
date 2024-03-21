class TokenPricing:
    def __init__(
        self,
        *,
        model_name,
        prompt_token_price_per_k: float,
        completion_token_price_per_k: float,
    ):
        self.model_name = model_name
        self.prompt_token_price = prompt_token_price_per_k / 1_000.0
        self.completion_token_price = completion_token_price_per_k / 1_000.0

    def __eq__(self, other):
        if not isinstance(other, TokenPricing):
            return False
        return (
            self.model_name == other.model_name
            and self.prompt_token_price == other.prompt_token_price
            and self.completion_token_price == other.completion_token_price
        )
