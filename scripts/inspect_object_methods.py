import inspect
from typing import get_type_hints, Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import re


class MethodType(Enum):
    """Enumeration for different method types."""
    INSTANCE = "instance"
    STATIC = "static"
    CLASS = "class"
    PROPERTY = "property"
    CACHED_PROPERTY = "cached_property"


@dataclass
class ParameterInfo:
    """Information about a method parameter."""
    name: str
    type_hint: Any
    default: Any
    kind: inspect.Parameter
    
    @property
    def has_default(self) -> bool:
        return self.default != inspect.Parameter.empty
    
    @property
    def type_str(self) -> str:
        """Get a string representation of the type."""
        if self.type_hint == inspect.Parameter.empty:
            return "Any"
        return self._format_type(self.type_hint)
    
    def _format_type(self, type_hint) -> str:
        """Format type hint to string."""
        if hasattr(type_hint, '__name__'):
            return type_hint.__name__
        return str(type_hint).replace('typing.', '')


@dataclass
class MethodInfo:
    """Complete information about a method."""
    name: str
    method_type: MethodType
    parameters: List[ParameterInfo]
    return_type: Any
    docstring: Optional[str]
    signature: inspect.Signature
    is_async: bool = False
    
    @property
    def return_type_str(self) -> str:
        """Get a string representation of the return type."""
        if self.return_type == inspect.Parameter.empty:
            return "Any"
        if hasattr(self.return_type, '__name__'):
            return self.return_type.__name__
        return str(self.return_type).replace('typing.', '')
    
    @property
    def param_count(self) -> int:
        """Get the number of parameters (excluding self/cls)."""
        return len([p for p in self.parameters if p.name not in ('self', 'cls')])


class TypeInspector:
    """A comprehensive class for inspecting Python objects and their type annotations."""
    
    def __init__(self, obj: Any, include_private: bool = False, include_magic: bool = False):
        """
        Initialize the TypeInspector.
        
        Args:
            obj: The object or class to inspect
            include_private: Whether to include methods starting with '_'
            include_magic: Whether to include methods starting with '__'
        """
        self.obj = obj
        self.cls = obj if inspect.isclass(obj) else type(obj)
        self.include_private = include_private
        self.include_magic = include_magic
        self._methods_cache: Optional[List[MethodInfo]] = None
    
    def _should_include_method(self, name: str) -> bool:
        """Check if a method should be included based on filters."""
        if name.startswith('__') and not self.include_magic:
            return False
        if name.startswith('_') and not name.startswith('__') and not self.include_private:
            return False
        return True
    
    def _get_method_type(self, name: str) -> MethodType:
        """Determine the type of a method."""
        attr = inspect.getattr_static(self.cls, name)
        
        if isinstance(attr, staticmethod):
            return MethodType.STATIC
        elif isinstance(attr, classmethod):
            return MethodType.CLASS
        elif isinstance(attr, property):
            return MethodType.PROPERTY
        elif hasattr(attr, '__class__') and attr.__class__.__name__ == 'cached_property':
            return MethodType.CACHED_PROPERTY
        else:
            return MethodType.INSTANCE
    
    def _extract_method_info(self, name: str, method: Any) -> Optional[MethodInfo]:
        """Extract detailed information about a method."""
        try:
            method_type = self._get_method_type(name)
            
            # Handle properties differently
            if method_type in (MethodType.PROPERTY, MethodType.CACHED_PROPERTY):
                # For properties, get the getter method
                if hasattr(method, 'fget'):
                    method = method.fget
                else:
                    return None
            
            # Get type hints
            try:
                hints = get_type_hints(method)
            except:
                hints = {}
            
            # Get signature
            try:
                sig = inspect.signature(method)
            except:
                return None
            
            # Extract parameters
            parameters = []
            for param_name, param in sig.parameters.items():
                param_info = ParameterInfo(
                    name=param_name,
                    type_hint=hints.get(param_name, inspect.Parameter.empty),
                    default=param.default,
                    kind=param.kind
                )
                parameters.append(param_info)
            
            # Get return type
            return_type = hints.get('return', inspect.Parameter.empty)
            
            # Get docstring
            docstring = inspect.getdoc(method)
            
            # Check if async
            is_async = inspect.iscoroutinefunction(method)
            
            return MethodInfo(
                name=name,
                method_type=method_type,
                parameters=parameters,
                return_type=return_type,
                docstring=docstring,
                signature=sig,
                is_async=is_async
            )
            
        except Exception:
            return None
    
    def get_all_methods(self) -> List[MethodInfo]:
        """Get all methods with their information."""
        if self._methods_cache is not None:
            return self._methods_cache
        
        methods = []
        
        for name in dir(self.cls):
            if not self._should_include_method(name):
                continue
            
            try:
                attr = getattr(self.cls, name)
                if callable(attr) or isinstance(attr, (property, type(lambda: None))):
                    method_info = self._extract_method_info(name, attr)
                    if method_info:
                        methods.append(method_info)
            except:
                continue
        
        self._methods_cache = methods
        return methods
    
    def get_methods_by_type(self, method_type: MethodType) -> List[MethodInfo]:
        """Get all methods of a specific type."""
        return [m for m in self.get_all_methods() if m.method_type == method_type]
    
    def get_methods_with_return_type(self, return_type: type) -> List[MethodInfo]:
        """Get all methods that return a specific type."""
        methods = []
        for method in self.get_all_methods():
            if method.return_type == return_type:
                methods.append(method)
        return methods
    
    def get_async_methods(self) -> List[MethodInfo]:
        """Get all async methods."""
        return [m for m in self.get_all_methods() if m.is_async]
    
    def search_methods(self, pattern: str) -> List[MethodInfo]:
        """Search for methods by name pattern (regex supported)."""
        regex = re.compile(pattern, re.IGNORECASE)
        return [m for m in self.get_all_methods() if regex.search(m.name)]
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert all method information to a dictionary."""
        result = {}
        for method in self.get_all_methods():
            result[method.name] = {
                'type': method.method_type.value,
                'return_type': method.return_type_str,
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type_str,
                        'has_default': p.has_default,
                        'default': str(p.default) if p.has_default else None
                    }
                    for p in method.parameters
                ],
                'is_async': method.is_async,
                'docstring': method.docstring
            }
        return result
    
    def print_summary(self, verbose: bool = False):
        """Print a summary of all methods."""
        methods = self.get_all_methods()
        
        print(f"\n{'='*80}")
        print(f"Type Inspector Summary for: {self.cls.__name__}")
        print(f"{'='*80}")
        print(f"Total methods: {len(methods)}")
        
        # Group by method type
        by_type = {}
        for method in methods:
            by_type.setdefault(method.method_type, []).append(method)
        
        for method_type, method_list in by_type.items():
            print(f"\n{method_type.value.upper()} METHODS ({len(method_list)}):")
            print("-" * 40)
            
            for method in sorted(method_list, key=lambda m: m.name):
                print(f"  {method.name:<30} -> {method.return_type_str}")
                
                if verbose:
                    # Print parameters
                    if method.parameters:
                        params_str = []
                        for p in method.parameters:
                            if p.name in ('self', 'cls'):
                                continue
                            param_str = f"{p.name}: {p.type_str}"
                            if p.has_default:
                                param_str += f" = {p.default}"
                            params_str.append(param_str)
                        
                        if params_str:
                            print(f"    Parameters: {', '.join(params_str)}")
                    
                    # Print docstring first line
                    if method.docstring:
                        first_line = method.docstring.split('\n')[0]
                        if len(first_line) > 60:
                            first_line = first_line[:57] + "..."
                        print(f"    Doc: {first_line}")
                    
                    if method.is_async:
                        print("    [ASYNC]")
                    
                    print()
    
    def print_method_details(self, method_name: str):
        """Print detailed information about a specific method."""
        methods = [m for m in self.get_all_methods() if m.name == method_name]
        
        if not methods:
            print(f"Method '{method_name}' not found")
            return
        
        method = methods[0]
        
        print(f"\n{'='*60}")
        print(f"Method: {method.name}")
        print(f"{'='*60}")
        print(f"Type: {method.method_type.value}")
        print(f"Async: {method.is_async}")
        print(f"Return Type: {method.return_type_str}")
        print(f"\nSignature: {method.name}{method.signature}")
        
        if method.parameters:
            print("\nParameters:")
            for p in method.parameters:
                param_str = f"  - {p.name}: {p.type_str}"
                if p.has_default:
                    param_str += f" = {p.default}"
                print(param_str)
        
        if method.docstring:
            print("\nDocstring:")
            print(f"{method.docstring}")
    
    def generate_stub(self) -> str:
        """Generate a stub file content for the class."""
        lines = [f"class {self.cls.__name__}:"]
        
        for method in self.get_all_methods():
            if method.method_type == MethodType.PROPERTY:
                lines.append("    @property")
            elif method.method_type == MethodType.STATIC:
                lines.append("    @staticmethod")
            elif method.method_type == MethodType.CLASS:
                lines.append("    @classmethod")
            elif method.method_type == MethodType.CACHED_PROPERTY:
                lines.append("    @cached_property")
            
            # Build parameter list
            params = []
            for p in method.parameters:
                param_str = p.name
                if p.type_hint != inspect.Parameter.empty:
                    param_str += f": {p.type_str}"
                if p.has_default:
                    param_str += " = ..."
                params.append(param_str)
            
            # Add async if needed
            async_prefix = "async " if method.is_async else ""
            
            # Build method signature
            return_annotation = f" -> {method.return_type_str}" if method.return_type != inspect.Parameter.empty else ""
            lines.append(f"    {async_prefix}def {method.name}({', '.join(params)}){return_annotation}: ...")
            lines.append("")
        
        return "\n".join(lines)


# Example usage and demonstration
if __name__ == "__main__":
    # Example class with various method types and annotations
    from typing import List, Dict, Optional
    
    from edsl import AgentList
    
    # Create inspector and demonstrate features
    inspector = TypeInspector(AgentList, include_private=True, include_magic=True)
    
    # Print summary
    #inspector.print_summary(verbose=True)

    methods_returning_agentlist = inspector.get_methods_with_return_type(AgentList)
    instance_methods_returning_agentlist = [m for m in methods_returning_agentlist if m.method_type == MethodType.INSTANCE]
    print(f"Instance methods that return AgentList ({len(instance_methods_returning_agentlist)}):")
    for method in instance_methods_returning_agentlist:
        print(f"  - {method.name}: {method.return_type_str}")
    # print("\n\nStatic methods:")
    # for method in inspector.get_methods_by_type(MethodType.STATIC):
    #     print(f"  - {method.name}")
    
    # # Print detailed info about a specific method
    # inspector.print_method_details("method_with_params")
    
    # # Generate stub
    # print("\n\nGenerated stub:")
    # print(inspector.generate_stub())