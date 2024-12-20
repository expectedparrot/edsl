from edsl.inference_services.InferenceServicesCollection import (
    InferenceServicesCollection,
)

from edsl.inference_services.OpenAIService import OpenAIService
from edsl.inference_services.AnthropicService import AnthropicService
from edsl.inference_services.DeepInfraService import DeepInfraService
from edsl.inference_services.GoogleService import GoogleService
from edsl.inference_services.GroqService import GroqService
from edsl.inference_services.AwsBedrock import AwsBedrockService
from edsl.inference_services.AzureAI import AzureAIService
from edsl.inference_services.OllamaService import OllamaService
from edsl.inference_services.TestService import TestService
from edsl.inference_services.TogetherAIService import TogetherAIService
from edsl.inference_services.PerplexityService import PerplexityService

try:
    from edsl.inference_services.MistralAIService import MistralAIService

    mistral_available = True
except Exception as e:
    mistral_available = False

services = [
    OpenAIService,
    AnthropicService,
    DeepInfraService,
    GoogleService,
    GroqService,
    AwsBedrockService,
    AzureAIService,
    OllamaService,
    TestService,
    TogetherAIService,
    PerplexityService,
]

if mistral_available:
    services.append(MistralAIService)

default = InferenceServicesCollection(services)
