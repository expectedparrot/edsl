# edsl/plugins/text_plugins.py
import pluggy
from typing import Dict, Any, Optional

# Define a hook implementation marker
hookimpl = pluggy.HookimplMarker("edsl")

# Create an exportable class for demonstration
class PigLatinTranslator:
    """A class that translates text to Pig Latin."""
    
    @staticmethod
    def translate(text):
        """Translate text to Pig Latin."""
        words = text.split()
        result = []
        for word in words:
            # Simple Pig Latin rule: move first letter to end and add "ay"
            if len(word) > 1:
                pig_latin = word[1:] + word[0] + "ay"
                result.append(pig_latin)
            else:
                result.append(word + "ay")
        return " ".join(result)

class PigLatin:
    """Text processing plugin."""
    
    @hookimpl
    def plugin_name(self):
        return "PigLatin"
    
    @hookimpl
    def plugin_description(self):
        return "This plugin translates text to Pig Latin."
        
    @hookimpl
    def edsl_plugin(self, plugin_name=None):
        if plugin_name is None or plugin_name == "PigLatin":
            return self
    
    @hookimpl
    def get_plugin_methods(self):
        return {
            "pig_latin": self.pig_latin
        }
    
    @hookimpl
    def exports_to_namespace(self) -> Dict[str, Any]:
        """Export objects to the global namespace."""
        return {
            "PigLatinTranslator": PigLatinTranslator
        }
    
    def pig_latin(self, survey, *args, **kwargs):
        """Get pig latin translation of survey questions."""
        # A simple Pig Latin translator without using the model
        # This avoids needing API keys for testing
        
        #print(f"Processing survey: {survey}")
        
        # Translate each question text
        translations = []
        for question in survey.questions:
            translations.append(PigLatinTranslator.translate(question.question_text))
            
        return translations