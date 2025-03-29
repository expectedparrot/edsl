"""
Memory debugging utilities for analyzing object references and memory leaks.
"""
import gc
import sys
import types
import objgraph
from typing import Any, Set, List, Dict

class MemoryDebugger:
    """
    A class for debugging memory issues and analyzing object references.
    
    This class provides utilities to:
    - Inspect objects referring to a target object
    - Detect reference cycles
    - Visualize object dependencies
    - Analyze memory usage patterns
    """
    
    def __init__(self, target_obj: Any):
        """
        Initialize the debugger with a target object to analyze.
        
        Args:
            target_obj: The object to inspect for memory issues
        """
        self.target_obj = target_obj
    
    def inspect_references(self, skip_frames: bool = True) -> None:
        """
        Inspect what objects are referring to the target object.
        
        Args:
            skip_frames: If True, skip function frames and local namespaces
        """
        print(f"\nReference count for {type(self.target_obj)}: {sys.getrefcount(self.target_obj)}")
        print("\nObjects referring to this object:")
        
        referrers = gc.get_referrers(self.target_obj)
        for ref in referrers:
            # Skip frames and function locals if requested
            if skip_frames and (isinstance(ref, (types.FrameType, types.FunctionType)) or 
                              (isinstance(ref, dict) and ref.get('target_obj') is self.target_obj)):
                continue
        
            print(f"\nType: {type(ref)}")
            
            if isinstance(ref, dict):
                self._inspect_dict_reference(ref)
            elif isinstance(ref, list):
                self._inspect_list_reference(ref)
            elif isinstance(ref, tuple):
                self._inspect_tuple_reference(ref)
            else:
                print(f"  - {ref}")
    
    def detect_reference_cycles(self) -> Set[Any]:
        """
        Detect potential reference cycles involving the target object.
        
        Returns:
            Set of objects that are part of potential reference cycles
        """
        referrers = gc.get_referrers(self.target_obj)
        referents = gc.get_referents(self.target_obj)
        
        common_objects = set(referrers) & set(referents)
        
        if common_objects:
            print(f"Potential reference cycle detected! Found {len(common_objects)} common objects")
            for shared_obj in common_objects:
                print(f"Type: {type(shared_obj)}, ID: {id(shared_obj)}")
        
        return common_objects
    
    def visualize_dependencies(self) -> None:
        """
        Visualize object dependencies using objgraph.
        """
        objgraph.show_refs(self.target_obj)
    
    def _inspect_dict_reference(self, ref: Dict) -> None:
        """Helper method to inspect dictionary references."""
        for k, v in ref.items():
            if v is self.target_obj:
                print(f"  - Found in dict with key: {k}")
                try:
                    owner = [o for o in gc.get_referrers(ref) 
                            if hasattr(o, '__dict__') and o.__dict__ is ref]
                    if owner:
                        print(f"    (This dict belongs to: {type(owner[0])})")
                except:
                    pass
    
    def _inspect_list_reference(self, ref: List) -> None:
        """Helper method to inspect list references."""
        try:
            idx = ref.index(self.target_obj)
            print(f"  - Found in list at index: {idx}")
            owners = [o for o in gc.get_referrers(ref) if hasattr(o, '__dict__')]
            if owners:
                print(f"    (This list belongs to: {type(owners[0])})")
        except ValueError:
            print("  - Found in list (as part of a larger structure)")
    
    def _inspect_tuple_reference(self, ref: tuple) -> None:
        """Helper method to inspect tuple references."""
        try:
            idx = ref.index(self.target_obj)
            print(f"  - Found in tuple at index: {idx}")
        except ValueError:
            print("  - Found in tuple (as part of a larger structure)")