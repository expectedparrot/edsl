# Global registry instance with lazy model source
from .inference_service_registry import InferenceServiceRegistry

# verbose = CONFIG.get('EDSL_VERBOSE_MODE').lower() == 'true'
GLOBAL_REGISTRY = InferenceServiceRegistry(verbose=False)
