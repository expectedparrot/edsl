# Global registry instance with lazy model source
from .inference_service_registry import InferenceServiceRegistry
from ..config import CONFIG

# verbose = CONFIG.get('EDSL_VERBOSE_MODE').lower() == 'true'
GLOBAL_REGISTRY = InferenceServiceRegistry(verbose=False)
