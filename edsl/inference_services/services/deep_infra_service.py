from typing import List


from .open_ai_service import OpenAIService


#Model(id='meta-llama/Llama-Guard-4-12B', created=0, object='model', owned_by='deepinfra', root='meta-llama/Llama-Guard-4-12B', parent=None)


class DeepInfraService(OpenAIService):
    """DeepInfra service class."""


    _inference_service_ = "deep_infra"
    _env_key_name_ = "DEEP_INFRA_API_KEY"
    _base_url_ = "https://api.deepinfra.com/v1/openai"
    _models_list_cache: List[str] = []
