"""
Lazy import utilities to improve module import performance.

This module provides tools to defer the loading of modules until they are actually
accessed, significantly improving import time for the EDSL package.
"""
import importlib
import time
import sys
from typing import Optional, Dict, Any, List, Callable


class LazyModule:
    """
    A proxy module that loads the real module only when an attribute is accessed.
    
    This allows for faster imports by deferring the actual loading of modules until
    they are needed, rather than loading everything at startup.
    
    Args:
        name: The name of the module to lazy-load
        package: Optional parent package name for relative imports
    """
    def __init__(self, name: str, package: Optional[str] = None):
        self._name = name
        self._package = package
        self._module = None
        
    def __getattr__(self, name: str) -> Any:
        """
        Triggered when an attribute is accessed on the lazy module.
        This will load the actual module if it hasn't been loaded yet.
        
        Args:
            name: The attribute name being accessed
            
        Returns:
            The requested attribute from the loaded module
            
        Raises:
            AttributeError: If the attribute doesn't exist in the loaded module
        """
        if self._module is None:
            # Delay the import to avoid circular dependencies
            from edsl import logger
            
            start_time = time.time()
            
            if self._package:
                self._module = importlib.import_module(f".{self._name}", package=self._package)
            else:
                self._module = importlib.import_module(self._name)
            
            load_time = (time.time() - start_time) * 1000
            logger.debug(f"Lazy-loaded {self._name} in {load_time:.2f} ms")
        
        return getattr(self._module, name)


class LazyCallable:
    """
    A callable proxy that delays the import of a function or class until it's called.
    
    Args:
        module_name: The module containing the callable
        callable_name: The name of the function or class to import
        package: Optional parent package for relative imports
    """
    def __init__(self, module_name: str, callable_name: str, package: Optional[str] = None):
        self._module_name = module_name
        self._callable_name = callable_name
        self._package = package
        self._callable = None
        
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Calls the function or class, importing it first if needed.
        
        Args:
            *args: Positional arguments to pass to the callable
            **kwargs: Keyword arguments to pass to the callable
            
        Returns:
            The result of calling the function or instantiating the class
        """
        if self._callable is None:
            if self._package:
                module = importlib.import_module(f".{self._module_name}", package=self._package)
            else:
                module = importlib.import_module(self._module_name)
                
            self._callable = getattr(module, self._callable_name)
            
        return self._callable(*args, **kwargs)


def lazy_import(module_name: str, package: Optional[str] = None) -> Any:
    """
    Create a lazy-loading proxy for a module.
    
    Args:
        module_name: The name of the module to lazy-load
        package: Optional parent package for relative imports
        
    Returns:
        A LazyModule proxy object
    """
    return LazyModule(module_name, package)


def lazy_function(module_name: str, function_name: str, package: Optional[str] = None) -> Callable:
    """
    Create a lazy-loading proxy for a function.
    
    Args:
        module_name: The module containing the function
        function_name: The name of the function to lazy-load
        package: Optional parent package for relative imports
        
    Returns:
        A callable proxy that will import the function when called
    """
    return LazyCallable(module_name, function_name, package)


def lazy_class(module_name: str, class_name: str, package: Optional[str] = None) -> Callable:
    """
    Create a lazy-loading proxy for a class.
    
    Args:
        module_name: The module containing the class
        class_name: The name of the class to lazy-load
        package: Optional parent package for relative imports
        
    Returns:
        A callable proxy that will import the class when instantiated
    """
    return LazyCallable(module_name, class_name, package)