"""
Inspector Widget ABC

Abstract base class for all inspector widgets that display detailed views of EDSL objects.
Provides standardized interface for object inspection with consistent data handling.
"""

from abc import ABCMeta, abstractmethod
import traitlets
from typing import Any, Dict, Optional
from .base_widget import EDSLBaseWidget


# Create a compatible metaclass that combines the base widget metaclass with ABC
class InspectorMeta(type(EDSLBaseWidget), ABCMeta):
    pass


class InspectorWidget(EDSLBaseWidget, metaclass=InspectorMeta):
    """Abstract base class for inspector widgets.
    
    Provides common functionality for inspecting EDSL objects with standardized
    data handling and frontend communication patterns.
    
    All inspector widgets should:
    - Accept an EDSL object for inspection
    - Convert objects to dictionaries using to_dict(full_dict=True)
    - Handle missing object properties gracefully in JavaScript
    - Provide search and filtering capabilities
    - Support method chaining via inspect() method
    """
    
    # Base traitlets - subclasses can add more specific ones
    inspected_object = traitlets.Any(allow_none=True).tag(sync=False)
    object_data = traitlets.Dict().tag(sync=True)
    
    def __init__(self, inspected_object=None, **kwargs):
        """Initialize the Inspector Widget.
        
        Args:
            inspected_object: An EDSL object to inspect. Can be set later via 
                             the `.inspected_object` property or `inspect()` method.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(**kwargs)
        if inspected_object is not None:
            self.inspected_object = inspected_object
    
    @traitlets.observe('inspected_object')
    def _on_object_change(self, change):
        """Update widget data when inspected object changes."""
        if change['new'] is not None:
            self._update_object_data()
        else:
            self.object_data = {}
    
    def inspect(self, obj) -> 'InspectorWidget':
        """Set the object to inspect and return self for method chaining.
        
        Args:
            obj: An EDSL object to inspect
            
        Returns:
            Self, for method chaining
        """
        self.inspected_object = obj
        return self
    
    @abstractmethod
    def _update_object_data(self):
        """Extract and format object data for the frontend.
        
        Subclasses must implement this method to handle their specific object type.
        Should populate self.object_data with the result of calling to_dict(full_dict=True)
        on the inspected object, plus any additional computed fields needed by the frontend.
        """
        pass
    
    @abstractmethod  
    def _validate_object(self, obj) -> bool:
        """Validate that the object is the correct type for this inspector.
        
        Args:
            obj: Object to validate
            
        Returns:
            bool: True if object is valid for this inspector
        """
        pass
    
    def refresh(self):
        """Refresh the widget display by re-extracting object data.
        
        Useful if the object has been modified after the widget was created.
        """
        if self.inspected_object is not None:
            self._update_object_data()
    
    def _safe_to_dict(self, obj, fallback_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Safely call to_dict(full_dict=True) on an object with error handling.
        
        Args:
            obj: Object to convert to dictionary
            fallback_data: Optional fallback data if to_dict fails
            
        Returns:
            Dictionary representation of the object
        """
        if obj is None:
            return {}
            
        try:
            if hasattr(obj, 'to_dict'):
                return obj.to_dict(full_dict=True)
            else:
                # If no to_dict method, create basic representation
                return {
                    'type': type(obj).__name__,
                    'str_representation': str(obj),
                    'available_methods': [method for method in dir(obj) if not method.startswith('_')]
                }
        except Exception as e:
            print(f"Warning: Failed to convert {type(obj).__name__} to dict: {e}")
            if fallback_data:
                return fallback_data
            return {
                'error': f"Failed to convert object to dictionary: {str(e)}",
                'type': type(obj).__name__,
                'str_representation': str(obj)
            }
    
    def export_summary(self) -> Dict[str, Any]:
        """Export a summary of the object's key characteristics.
        
        Returns:
            Dictionary containing object summary information
        """
        if not self.object_data:
            return {}
        
        return {
            'object_type': self.object_data.get('edsl_class_name', type(self.inspected_object).__name__),
            'has_data': bool(self.object_data),
            'data_keys': list(self.object_data.keys()),
            'edsl_version': self.object_data.get('edsl_version', 'unknown')
        }