from edsl.inference_services.InferenceServicesCollection import InferenceServicesCollection

from edsl.inference_services.OpenAIService import OpenAIService
from edsl.inference_services.AnthropicService import AnthropicService
from edsl.inference_services.DeepInfraService import DeepInfraService
from edsl.inference_services.GoogleService import GoogleService

collection = InferenceServicesCollection([
    OpenAIService,
    AnthropicService,
    DeepInfraService,
    GoogleService
])
