"""
Built-in external service implementations.

NOTE: Services have been moved to the edsl-services package.
Install it with: pip install edsl-services

Services are now discovered via Python entry points, which allows:
- Smaller edsl core package
- Independent service versioning
- Third-party service packages

This module is kept for backward compatibility but is effectively empty.
All services are loaded via entry points from edsl-services.
"""

# No services are defined here anymore - they come from entry points
__all__ = []
