"""
Cache management for EDSL jobs.

This module provides utilities for managing cache operations 
within EDSL jobs, making cache setup and usage more consistent.
"""
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..caching import Cache
    from ..key_management import KeyLookup
    from .data_structures import RunConfig


class CacheManager:
    """
    Manager for cache operations in EDSL jobs.
    
    This class encapsulates the logic for setting up, configuring, and
    retrieving cache objects, with appropriate handling of remote caching.
    """
    
    @staticmethod
    def setup_cache(config: "RunConfig") -> "Cache":
        """
        Set up an appropriate cache based on the provided configuration.
        
        This method handles the logic of determining the right cache type
        and configuration based on the run settings.
        
        Parameters:
            config: The run configuration
            
        Returns:
            Cache: The configured cache object
        """
        # If a cache is already provided, use it
        if isinstance(config.environment.cache, object) and not isinstance(
            config.environment.cache, bool
        ):
            return config.environment.cache
            
        # If cache is disabled, create a non-persistent cache
        if config.environment.cache is False:
            from ..caching import Cache
            return Cache(immediate_write=False)
            
        # Otherwise, get or create a default cache
        from ..caching import CacheHandler
        return CacheHandler().get_cache()
    
    @staticmethod
    def should_use_remote_cache(config: "RunConfig") -> bool:
        """
        Determine if remote cache should be used.
        
        This method checks the configuration and user settings to decide
        whether remote caching should be enabled.
        
        Parameters:
            config: The run configuration
            
        Returns:
            bool: True if remote cache should be used, False otherwise
        """
        import requests
        
        # If remote cache is explicitly disabled, don't use it
        if config.parameters.disable_remote_cache:
            return False
            
        # Otherwise, check user settings from Coop
        try:
            from ..coop import Coop
            user_edsl_settings = Coop().edsl_settings
            return user_edsl_settings.get("remote_caching", False)
        except (requests.ConnectionError, Exception):
            # If Coop is unavailable or returns an error, don't use remote cache
            pass
            
        return False
    
    @staticmethod
    def extract_relevant_cache(results: "Results", cache: "Cache") -> "Cache":
        """
        Extract only the cache entries relevant to the results.
        
        This method creates a new cache containing only the entries used
        in generating the provided results, which is useful for serialization
        and result sharing.
        
        Parameters:
            results: The results from job execution
            cache: The full cache used during execution
            
        Returns:
            Cache: A new cache containing only relevant entries
        """
        return results.relevant_cache(cache)