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
from edsl.inference_services.MistralAIService import MistralAIService

default = InferenceServicesCollection(
    [
        OpenAIService,
        AnthropicService,
        DeepInfraService,
        GoogleService,
        GroqService,
        AwsBedrockService,
        AzureAIService,
        OllamaService,
        TestService,
        MistralAIService,
    ]
)
