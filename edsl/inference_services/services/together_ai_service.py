from typing import List

from .open_ai_service import OpenAIService

import openai


class TogetherAIService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "together"
    _env_key_name_ = "TOGETHER_API_KEY"
    _base_url_ = "https://api.together.xyz/v1"
    _models_list_cache: List[str] = []

    # These are non-serverless models. There was no api param to filter them
    model_exclude_list = [
        "EleutherAI/llemma_7b",
        "HuggingFaceH4/zephyr-7b-beta",
        "Nexusflow/NexusRaven-V2-13B",
        "NousResearch/Hermes-2-Theta-Llama-3-70B",
        "NousResearch/Nous-Capybara-7B-V1p9",
        "NousResearch/Nous-Hermes-13b",
        "NousResearch/Nous-Hermes-2-Mistral-7B-DPO",
        "NousResearch/Nous-Hermes-2-Mixtral-8x7B-SFT",
        "NousResearch/Nous-Hermes-Llama2-13b",
        "NousResearch/Nous-Hermes-Llama2-70b",
        "NousResearch/Nous-Hermes-llama-2-7b",
        "NumbersStation/nsql-llama-2-7B",
        "Open-Orca/Mistral-7B-OpenOrca",
        "Phind/Phind-CodeLlama-34B-Python-v1",
        "Phind/Phind-CodeLlama-34B-v2",
        "Qwen/Qwen1.5-0.5B",
        "Qwen/Qwen1.5-0.5B-Chat",
        "Qwen/Qwen1.5-1.8B",
        "Qwen/Qwen1.5-1.8B-Chat",
        "Qwen/Qwen1.5-14B",
        "Qwen/Qwen1.5-14B-Chat",
        "Qwen/Qwen1.5-32B",
        "Qwen/Qwen1.5-32B-Chat",
        "Qwen/Qwen1.5-4B",
        "Qwen/Qwen1.5-4B-Chat",
        "Qwen/Qwen1.5-72B",
        "Qwen/Qwen1.5-7B",
        "Qwen/Qwen1.5-7B-Chat",
        "Qwen/Qwen2-1.5B",
        "Qwen/Qwen2-1.5B-Instruct",
        "Qwen/Qwen2-72B",
        "Qwen/Qwen2-7B",
        "Qwen/Qwen2-7B-Instruct",
        "SG161222/Realistic_Vision_V3.0_VAE",
        "Snowflake/snowflake-arctic-instruct",
        "Undi95/ReMM-SLERP-L2-13B",
        "Undi95/Toppy-M-7B",
        "WizardLM/WizardCoder-Python-34B-V1.0",
        "WizardLM/WizardLM-13B-V1.2",
        "WizardLM/WizardLM-70B-V1.0",
        "allenai/OLMo-7B",
        "allenai/OLMo-7B-Instruct",
        "bert-base-uncased",
        "codellama/CodeLlama-13b-Instruct-hf",
        "codellama/CodeLlama-13b-Python-hf",
        "codellama/CodeLlama-13b-hf",
        "codellama/CodeLlama-34b-Python-hf",
        "codellama/CodeLlama-34b-hf",
        "codellama/CodeLlama-70b-Instruct-hf",
        "codellama/CodeLlama-70b-Python-hf",
        "codellama/CodeLlama-70b-hf",
        "codellama/CodeLlama-7b-Instruct-hf",
        "codellama/CodeLlama-7b-Python-hf",
        "codellama/CodeLlama-7b-hf",
        "cognitivecomputations/dolphin-2.5-mixtral-8x7b",
        "deepseek-ai/deepseek-coder-33b-instruct",
        "garage-bAInd/Platypus2-70B-instruct",
        "google/gemma-2b",
        "google/gemma-7b",
        "google/gemma-7b-it",
        "gradientai/Llama-3-70B-Instruct-Gradient-1048k",
        "hazyresearch/M2-BERT-2k-Retrieval-Encoder-V1",
        "huggyllama/llama-13b",
        "huggyllama/llama-30b",
        "huggyllama/llama-65b",
        "huggyllama/llama-7b",
        "lmsys/vicuna-13b-v1.3",
        "lmsys/vicuna-13b-v1.5",
        "lmsys/vicuna-13b-v1.5-16k",
        "lmsys/vicuna-7b-v1.3",
        "lmsys/vicuna-7b-v1.5",
        "meta-llama/Llama-2-13b-hf",
        "meta-llama/Llama-2-70b-chat-hf",
        "meta-llama/Llama-2-7b-hf",
        "meta-llama/Llama-3-70b-hf",
        "meta-llama/Llama-3-8b-hf",
        "meta-llama/Meta-Llama-3-70B",
        "meta-llama/Meta-Llama-3-70B-Instruct",
        "meta-llama/Meta-Llama-3-8B-Instruct",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Reference",
        "meta-llama/Meta-Llama-3.1-70B-Reference",
        "meta-llama/Meta-Llama-3.1-8B-Reference",
        "microsoft/phi-2",
        "mistralai/Mixtral-8x22B",
        "openchat/openchat-3.5-1210",
        "prompthero/openjourney",
        "runwayml/stable-diffusion-v1-5",
        "sentence-transformers/msmarco-bert-base-dot-v5",
        "snorkelai/Snorkel-Mistral-PairRM-DPO",
        "stabilityai/stable-diffusion-2-1",
        "teknium/OpenHermes-2-Mistral-7B",
        "teknium/OpenHermes-2p5-Mistral-7B",
        "togethercomputer/CodeLlama-13b-Instruct",
        "togethercomputer/CodeLlama-13b-Python",
        "togethercomputer/CodeLlama-34b",
        "togethercomputer/CodeLlama-34b-Python",
        "togethercomputer/CodeLlama-7b-Instruct",
        "togethercomputer/CodeLlama-7b-Python",
        "togethercomputer/Koala-13B",
        "togethercomputer/Koala-7B",
        "togethercomputer/LLaMA-2-7B-32K",
        "togethercomputer/SOLAR-10.7B-Instruct-v1.0-int4",
        "togethercomputer/StripedHyena-Hessian-7B",
        "togethercomputer/alpaca-7b",
        "togethercomputer/evo-1-131k-base",
        "togethercomputer/evo-1-8k-base",
        "togethercomputer/guanaco-13b",
        "togethercomputer/guanaco-33b",
        "togethercomputer/guanaco-65b",
        "togethercomputer/guanaco-7b",
        "togethercomputer/llama-2-13b",
        "togethercomputer/llama-2-70b-chat",
        "togethercomputer/llama-2-7b",
        "wavymulder/Analog-Diffusion",
        "zero-one-ai/Yi-34B",
        "zero-one-ai/Yi-34B-Chat",
        "zero-one-ai/Yi-6B",
    ]

    _sync_client_ = openai.OpenAI
    _async_client_ = openai.AsyncOpenAI

    @classmethod
    def get_model_list(cls, api_token=None):
        # Togheter.ai has a different response in model list then openai
        # and the OpenAI class returns an error when calling .models.list()
        import requests
        import os

        url = "https://api.together.xyz/v1/models?filter=serverless"
        if api_token is None:
            api_token = os.getenv(cls._env_key_name_)

        headers = {"accept": "application/json", "authorization": f"Bearer {api_token}"}

        response = requests.get(url, headers=headers)
        return response.json()

    @classmethod
    def available(cls) -> List[str]:
        if not cls._models_list_cache:
            try:
                cls._models_list_cache = [
                    m["id"]
                    for m in cls.get_model_list()
                    if m["id"] not in cls.model_exclude_list
                ]
            except Exception:
                raise
        return cls._models_list_cache
