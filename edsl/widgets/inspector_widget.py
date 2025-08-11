"""
Inspector Widget ABC

Abstract base class for all inspector widgets that display detailed views of EDSL objects.
Provides standardized interface for object inspection with consistent data handling.
"""

from abc import ABCMeta
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
    - Define associated_class to specify which EDSL class they inspect
    """
    
    # Class registry for mapping EDSL classes to inspector widgets
    _registry = {}
    
    # Required class variable - subclasses must define this
    associated_class = None
    
    # Generic traitlets for any object type
    object = traitlets.Any(allow_none=True).tag(sync=False)
    data = traitlets.Dict().tag(sync=True)
    
    def __init_subclass__(cls, **kwargs):
        """Register subclasses and validate required class variables."""
        super().__init_subclass__(**kwargs)
        
        # Skip registration for the base class itself
        if cls.__name__ == 'InspectorWidget':
            return
            
        # Validate required class variables
        cls._validate_class_variables()
        
        # Register the widget class
        if cls.associated_class is not None:
            # Handle both class objects and class names
            if isinstance(cls.associated_class, str):
                key = cls.associated_class
            else:
                key = cls.associated_class.__name__
            
            cls._registry[key] = cls
    
    def __init__(self, obj=None, **kwargs):
        """Initialize the Inspector Widget.
        
        Args:
            obj: An EDSL object to inspect. Can be set later via 
                 the `.object` property or `inspect()` method.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(**kwargs)
        if obj is not None:
            self.object = obj
    
    @traitlets.observe('object')
    def _on_object_change(self, change):
        """Update widget data when inspected object changes."""
        if change['new'] is not None:
            if self._validate_object(change['new']):
                self._update_object_data()
            else:
                print(f"Warning: Invalid object type for {self.__class__.__name__}")
                self.data = {}
        else:
            self.data = {}
    
    def inspect(self, obj):
        """Set the object to inspect and return self for method chaining.
        
        Args:
            obj: An EDSL object to inspect
            
        Returns:
            Self, for method chaining
        """
        self.object = obj
        return self
    
    def _update_object_data(self):
        """Extract and format object data for the frontend using to_dict(full_dict=True).
        
        This default implementation should work for most EDSL objects.
        Subclasses can override if they need custom data processing.
        """
        if self.object is None:
            self.data = {}
            return
        
        # Use the base class safe conversion method
        self.data = self._safe_to_dict(self.object)
        
        # Call subclass hook for additional processing
        self._process_object_data()
    
    def _process_object_data(self):
        """Hook for subclasses to add custom data processing.
        
        Called after the main object data has been extracted via to_dict(full_dict=True).
        Subclasses can override this to add computed fields or transform data.
        """
        pass
    
    def _validate_object(self, obj) -> bool:
        """Validate that the object is the correct type for this inspector.
        
        Default implementation checks against associated_class.
        Subclasses can override for custom validation logic.
        
        Args:
            obj: Object to validate
            
        Returns:
            bool: True if object is valid for this inspector
        """
        if obj is None:
            return True
        
        # Check if the object matches our associated class
        if self.associated_class is not None:
            if isinstance(self.associated_class, str):
                return type(obj).__name__ == self.associated_class
            else:
                return isinstance(obj, self.associated_class)
        
        # Fallback to generic validation if no associated_class
        return True
    
    def refresh(self):
        """Refresh the widget display by re-extracting object data.
        
        Useful if the object has been modified after the widget was created.
        """
        if self.object is not None:
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
        if not self.data:
            return {}
        
        summary = {
            'object_type': self.data.get('edsl_class_name', type(self.object).__name__ if self.object else 'Unknown'),
            'has_data': bool(self.data),
            'data_keys': list(self.data.keys()),
            'edsl_version': self.data.get('edsl_version', 'unknown')
        }
        
        # Allow subclasses to add to the summary
        self._enhance_summary(summary)
        return summary
    
    def _enhance_summary(self, summary: Dict[str, Any]):
        """Hook for subclasses to enhance the exported summary.
        
        Args:
            summary: The base summary dictionary to modify
        """
        pass
    
    @classmethod
    def _validate_class_variables(cls):
        """Validate that required class variables are properly defined.
        
        Raises:
            ValueError: If required class variables are missing or invalid
        """
        if cls.associated_class is None:
            raise ValueError(
                f"{cls.__name__} must define 'associated_class' class variable. "
                "This should be the EDSL class that this inspector handles (e.g., Agent, Survey, etc.)"
            )
    
    @classmethod
    def get_widget_for_class(cls, target_class):
        """Get the appropriate inspector widget class for a given EDSL class.
        
        Args:
            target_class: Either a class object or class name string
            
        Returns:
            InspectorWidget subclass that handles the given class
            
        Raises:
            KeyError: If no inspector is registered for the given class
            
        Example:
            >>> widget_class = InspectorWidget.get_widget_for_class('Agent')
            >>> widget = widget_class(my_agent)
            
            >>> from edsl.agents import Agent
            >>> widget_class = InspectorWidget.get_widget_for_class(Agent)
            >>> widget = widget_class(my_agent)
        """
        # Handle both class objects and strings
        if isinstance(target_class, str):
            key = target_class
        else:
            key = target_class.__name__
            
        if key not in cls._registry:
            available = list(cls._registry.keys())
            raise KeyError(
                f"No inspector widget registered for class '{key}'. "
                f"Available inspectors: {available}"
            )
            
        return cls._registry[key]
    
    @classmethod
    def get_registered_classes(cls):
        """Get a list of all registered EDSL classes that have inspectors.
        
        Returns:
            List of class names that have registered inspectors
        """
        return list(cls._registry.keys())
    
    @classmethod
    def create_inspector_for(cls, obj):
        """Create the appropriate inspector widget for any EDSL object.
        
        Args:
            obj: Any EDSL object
            
        Returns:
            Appropriate InspectorWidget subclass instance
            
        Raises:
            KeyError: If no inspector is registered for the object's class
            
        Example:
            >>> inspector = InspectorWidget.create_inspector_for(my_agent)
            >>> inspector  # Returns AgentInspectorWidget instance
        """
        if obj is None:
            raise ValueError("Cannot create inspector for None object")
            
        obj_class_name = type(obj).__name__
        widget_class = cls.get_widget_for_class(obj_class_name)
        return widget_class(obj)