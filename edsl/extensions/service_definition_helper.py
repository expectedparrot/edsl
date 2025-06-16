from typing import Dict, List, Optional, Callable, Any
import inspect

from .parameter_extraction import FunctionSignatureExtractor
from .return_analyzer import ReturnAnalyzer, ReturnStructure
from .authoring import ParameterDefinition, ReturnDefinition, ServiceDefinition, CostDefinition

def format_value(value):
    """Format a value for display, handling None and multi-line strings."""
    if value is None:
        return "None"
    if isinstance(value, str) and "\n" in value:
        # Handle multi-line strings by adding indentation to each line
        lines = value.split("\n")
        indented_lines = ["    " + line for line in lines]
        return "\n" + "\n".join(indented_lines)
    return str(value)

def example_analyze_text(
    text: str,
    language: str = "en",
    max_length: Optional[int] = None,
    *,
    advanced_features: bool = False
) -> Dict[str, Any]:
    """Analyzes text and returns linguistic insights.
    
    This function performs various text analysis operations including:
    - Sentiment analysis
    - Key phrase extraction
    - Language detection
    - Readability metrics
    
    Args:
        text: The text to analyze
        language: Language code (e.g., 'en' for English)
        max_length: Maximum text length to process
        advanced_features: Whether to include advanced analysis
        
    Returns:
        A dictionary containing the analysis results with the following structure:
        {
            'analysis': {
                'type': 'TextAnalysis',
                'description': 'Comprehensive text analysis results',
                'coopr_url': False,
                'value': {
                    'sentiment': float,
                    'key_phrases': List[str],
                    'readability_score': float
                }
            }
        }
    """
    # Simulate text analysis
    return {
        'analysis': {
            'type': 'TextAnalysis',
            'description': 'Comprehensive text analysis results',
            'coopr_url': False,
            'value': {
                'sentiment': 0.8,
                'key_phrases': ['example', 'text'],
                'readability_score': 75.0
            }
        }
    }

class ServiceDefinitionHelper:
    """Helps analyze, validate, and construct ServiceDefinitions from callables.
    
    This class provides tools to analyze a function and:
    1. Compare it against an existing service definition
    2. Generate a proposed service definition
    3. Validate the implementation matches requirements
    
    Args:
        func: The callable to analyze
        
    Example:
        >>> example_func = ServiceDefinitionHelper.get_example_function()
        >>> helper = ServiceDefinitionHelper(example_func)
        >>> proposed = helper.propose_service_definition()
        >>> proposed.name == 'analyze_text'
        True
        >>> 'text' in proposed.parameters
        True
        >>> 'analysis' in proposed.service_returns
        True
        >>> proposed.service_returns['analysis'].type == 'TextAnalysis'
        True
    """
    
    @classmethod
    def get_example_function(cls) -> Callable:
        """Returns an example function that demonstrates proper service definition structure.
        
        The function includes:
        - Proper type hints
        - Detailed docstring
        - Multiple parameters with defaults
        - Return value matching ReturnDefinition structure
        
        Returns:
            A well-defined function suitable for testing ServiceDefinitionHelper
        """
        return example_analyze_text

    def __init__(self, func: Callable):
        self.func = func
        self.signature_extractor = FunctionSignatureExtractor(func)
        self.return_analyzer = ReturnAnalyzer()

    def propose_service_definition(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        endpoint: Optional[str] = None,
        cost: Optional[CostDefinition] = None
    ) -> ServiceDefinition:
        """Generate a proposed ServiceDefinition based on the function's signature and returns.
        
        Args:
            name: Service name (defaults to function name if not provided)
            description: Service description (defaults to function's docstring if not provided)
            endpoint: Service endpoint (defaults to f"/{name}")
            cost: Cost definition (defaults to basic cost structure if not provided)
            
        Returns:
            A ServiceDefinition constructed from the function's signature and provided values
        """
        # Get function name and docstring
        func_name = self.func.__name__
        func_doc = inspect.getdoc(self.func) or ""
        
        # Use provided values or defaults
        service_name = name or func_name
        service_description = description or func_doc
        service_endpoint = endpoint or f"/{service_name}"
        
        # Get parameters from function signature
        parameters = self.signature_extractor.get_parameter_definitions()
        
        # Get return structure from function implementation
        returns = self.return_analyzer.get_return_definitions(self.func)
        
        # Use provided cost or create default
        service_cost = cost or CostDefinition(
            unit="ep_credits",
            per_call_cost=1,  # Default cost
            variable_pricing_cost_formula=None,
            uses_client_ep_key=True,
            ep_username="test"
        )
        
        return ServiceDefinition(
            name=service_name,
            description=service_description,
            parameters=parameters,
            cost=service_cost,
            service_returns=returns,
            endpoint=service_endpoint
        )

    def _generate_comparison_report(self, extracted_defs: Dict, service_defs: Dict, section_name: str) -> str:
        """Generate a human-readable report comparing definitions."""
        report = []
        report.append(f"\n=== {section_name} Comparison Report ===\n")
        
        # Compare keys
        extracted_keys = set(extracted_defs.keys())
        service_keys = set(service_defs.keys())
        
        # Missing items section
        missing_in_extracted = service_keys - extracted_keys
        missing_in_service = extracted_keys - service_keys
        
        if missing_in_extracted or missing_in_service:
            report.append(f"--- Missing {section_name} ---")
            if missing_in_extracted:
                report.append(f"\n{section_name} missing in Implementation ❌:")
                for item in sorted(missing_in_extracted):
                    report.append(f"  • {item}")
            
            if missing_in_service:
                report.append(f"\n{section_name} missing in Service Definition ❌:")
                for item in sorted(missing_in_service):
                    report.append(f"  • {item}")
            report.append("")
        
        # Item comparison section
        report.append(f"--- {section_name} Comparisons ---\n")
        common_keys = sorted(extracted_keys.intersection(service_keys))
        
        for key in common_keys:
            extracted_dict = extracted_defs[key].to_dict()
            service_dict = service_defs[key].to_dict()
            
            has_differences = False
            item_report = []
            item_report.append(f"{section_name[:-1]}: {key}")
            
            # Compare each field
            all_fields = sorted(set(extracted_dict.keys()) | set(service_dict.keys()))
            for field in all_fields:
                extracted_value = extracted_dict.get(field)
                service_value = service_dict.get(field)
                
                if extracted_value != service_value:
                    has_differences = True
                    item_report.append(f"  {field} ❌:")
                    item_report.append(f"    Implementation: {format_value(extracted_value)}")
                    item_report.append(f"    Service Definition: {format_value(service_value)}")
                else:
                    item_report.append(f"  {field} ✅: {format_value(extracted_value)}")
            
            if has_differences:
                report.extend(item_report)
                report.append("")  # Add blank line between items
            else:
                report.append(f"{section_name[:-1]}: {key} ✅ (All fields match)\n")
        
        # Add summary section
        report.append("=== Summary ===")
        total_items = len(extracted_keys | service_keys)
        matching_items = len([k for k in common_keys if extracted_defs[k].to_dict() == service_defs[k].to_dict()])
        report.append(f"Total {section_name}: {total_items}")
        report.append(f"Fully Matching {section_name}: {matching_items} ✅")
        report.append(f"Items with Differences: {total_items - matching_items} ❌")
        
        return "\n".join(report)

    def validate_parameters(self, service_def: ServiceDefinition) -> str:
        """Validate the function's parameters against the service definition."""
        extracted_params = self.signature_extractor.get_parameter_definitions()
        return self._generate_comparison_report(extracted_params, service_def.parameters, "Parameters")

    def validate_returns(self, service_def: ServiceDefinition) -> str:
        """Validate the function's return value against the service definition."""
        extracted_returns = self.return_analyzer.get_return_definitions(self.func)
        return self._generate_comparison_report(extracted_returns, service_def.service_returns, "Returns")

    def validate(self, service_def: ServiceDefinition) -> str:
        """Validate implementation against a service definition.
        
        Returns:
            A formatted report showing all comparisons and any discrepancies.
        """
        report_parts = [
            "=== Service Definition Validation Report ===\n",
            f"Validating implementation of service: {service_def.name}\n",
            self.validate_parameters(service_def),
            "\n" + "="*80 + "\n",  # Separator
            self.validate_returns(service_def)
        ]
        return "\n".join(report_parts)

    def get_missing_parameters(self, service_def: ServiceDefinition) -> List[str]:
        """Get list of parameters required by service definition but missing in implementation."""
        extracted_params = self.signature_extractor.get_parameter_definitions()
        return list(set(service_def.parameters.keys()) - set(extracted_params.keys()))

    def get_missing_returns(self, service_def: ServiceDefinition) -> List[str]:
        """Get list of return values required by service definition but missing in implementation."""
        extracted_returns = self.return_analyzer.get_return_definitions(self.func)
        return list(set(service_def.service_returns.keys()) - set(extracted_returns.keys()))

    def is_valid(self, service_def: ServiceDefinition) -> bool:
        """Check if the implementation fully matches the service definition.
        
        Returns:
            True if all parameters and returns match exactly, False otherwise.
        """
        return not (self.get_missing_parameters(service_def) or self.get_missing_returns(service_def))

    def has_differences(self, service_def: ServiceDefinition) -> bool:
        """Check if there are any differences between the implementation and service definition.
        
        This method performs a deep comparison of parameters and returns, checking not just
        for missing items but also for differences in their definitions.
        
        Args:
            service_def: The service definition to compare against
            
        Returns:
            True if there are any differences in parameters or returns, False if everything matches exactly
        """
        # Get parameter and return definitions
        extracted_params = self.signature_extractor.get_parameter_definitions()
        extracted_returns = self.return_analyzer.get_return_definitions(self.func)
        
        # Check for any differences in parameters
        for key in set(extracted_params.keys()) | set(service_def.parameters.keys()):
            if key not in extracted_params or key not in service_def.parameters:
                return True
            if extracted_params[key].to_dict() != service_def.parameters[key].to_dict():
                return True
        
        # Check for any differences in returns
        for key in set(extracted_returns.keys()) | set(service_def.service_returns.keys()):
            if key not in extracted_returns or key not in service_def.service_returns:
                return True
            if extracted_returns[key].to_dict() != service_def.service_returns[key].to_dict():
                return True
        
        return False

if __name__ == "__main__":
    # Get the example function
    example_func = ServiceDefinitionHelper.get_example_function()
    helper = ServiceDefinitionHelper(example_func)
    
    # Generate a proposed service definition
    proposed = helper.propose_service_definition()
    print("Proposed Service Definition:")
    print(f"Name: {proposed.name}")
    print(f"Description: {proposed.description}")
    print(f"Parameters: {list(proposed.parameters.keys())}")
    print(f"Returns: {list(proposed.service_returns.keys())}")
    print(f"Endpoint: {proposed.endpoint}")
    print("\n" + "="*80 + "\n")
    
    # Validate the function against its own proposed definition
    print(helper.validate(proposed))
    
    # Optional: Use specific validation methods
    # print("\nParameter Validation:")
    # print(helper.validate_parameters(proposed))
    # print("\nReturn Value Validation:")
    # print(helper.validate_returns(proposed))
    
    # Optional: Check specific issues
    # print("\nMissing Parameters:", helper.get_missing_parameters(proposed))
    # print("Missing Returns:", helper.get_missing_returns(proposed))
    # print("Is Valid:", helper.is_valid(proposed))


