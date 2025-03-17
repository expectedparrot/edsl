# Example plugin that demonstrates exporting objects to the global namespace
import pluggy
from typing import Dict, Any, Optional

# Define a hook implementation marker
hookimpl = pluggy.HookimplMarker("edsl")

# Create a class that will be exported to the global namespace
class ExportedClass:
    """An example class exported from a plugin to the global namespace."""
    
    def __init__(self, name="Example"):
        self.name = name
        
    def greet(self):
        """Return a greeting message."""
        return f"Hello from {self.name}!"
    
# A function to be exported to the global namespace
def exported_function(text):
    """An example function exported from a plugin to the global namespace."""
    return f"Processed: {text}"

class ExportExample:
    """Example plugin that exports objects to the global namespace."""
    
    @hookimpl
    def plugin_name(self):
        return "ExportExample"
    
    @hookimpl
    def plugin_description(self):
        return "Demonstrates how to export objects to the global namespace."
    
    @hookimpl
    def edsl_plugin(self, plugin_name=None):
        if plugin_name is None or plugin_name == "ExportExample":
            return self
    
    @hookimpl
    def get_plugin_methods(self):
        return {}
    
    @hookimpl
    def exports_to_namespace(self) -> Dict[str, Any]:
        """Export objects to the global namespace."""
        return {
            "ExportedClass": ExportedClass,
            "exported_function": exported_function
        }