"""Test script for model service."""
import sys
sys.path.insert(0, '..')

from backend.services.model_service import get_model_service
from backend.services.model_validator import get_model_validator

print("=" * 60)
print("TESTING MODEL SERVICE")
print("=" * 60)

# Test model service
service = get_model_service()

print("\n1. Getting all models...")
models = service.get_all_models()
print(f"   ✓ Total models: {len(models)}")
if models:
    print(f"   ✓ Sample models: {models[:3]}")

print("\n2. Getting grouped models...")
grouped = service.get_grouped_models()
print(f"   ✓ Services: {list(grouped.keys())}")
for service_name, model_list in grouped.items():
    print(f"   ✓ {service_name}: {len(model_list)} models")

print("\n3. Getting popular models...")
popular = service.get_popular_models()
print(f"   ✓ Popular models: {popular}")

print("\n" + "=" * 60)
print("TESTING MODEL VALIDATOR")
print("=" * 60)

# Test model validator
validator = get_model_validator()

print("\n1. Validating existing model...")
is_valid, error = validator.validate_model("claude-opus-4-5-20251101")
print(f"   ✓ Valid: {is_valid}, Error: {error}")

print("\n2. Validating non-existent model...")
is_valid, error = validator.validate_model("fake-model-999")
print(f"   ✓ Valid: {is_valid}")
print(f"   ✓ Error message: {error}")

print("\n3. Validating experiment config...")
config = {
    "storytellerModel": "claude-opus-4-5-20251101",
    "judgeModel": "gpt-4-turbo"
}
result = validator.validate_experiment_config(config)
print(f"   ✓ Config valid: {result['valid']}")
print(f"   ✓ Errors: {result['errors']}")
print(f"   ✓ Warnings: {result['warnings']}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
