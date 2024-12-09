import re
from typing import Dict, Set, Optional


class CSSParameterizer:
    """A utility class to parameterize CSS with custom properties (variables)."""

    def __init__(self, css_content: str):
        """
        Initialize with CSS content to be parameterized.

        Args:
            css_content (str): The CSS content containing var() declarations
        """
        self.css_content = css_content
        self._extract_variables()

    def _extract_variables(self) -> None:
        """Extract all CSS custom properties (variables) from the CSS content."""
        # Find all var(...) declarations in the CSS
        var_pattern = r"var\((--[a-zA-Z0-9-]+)\)"
        self.variables = set(re.findall(var_pattern, self.css_content))

    def _validate_parameters(self, parameters: Dict[str, str]) -> Set[str]:
        """
        Validate the provided parameters against the CSS variables.

        Args:
            parameters (Dict[str, str]): Dictionary of variable names and their values

        Returns:
            Set[str]: Set of missing variables
        """
        # Convert parameter keys to CSS variable format if they don't already have --
        formatted_params = {
            f"--{k}" if not k.startswith("--") else k for k in parameters.keys()
        }

        # print("Variables from CSS:", self.variables)
        # print("Formatted parameters:", formatted_params)

        # Find missing and extra variables
        missing_vars = self.variables - formatted_params
        extra_vars = formatted_params - self.variables

        if extra_vars:
            print(f"Warning: Found unused parameters: {extra_vars}")

        return missing_vars

    def generate_root(self, **parameters: str) -> Optional[str]:
        """
        Generate a :root block with the provided parameters.

        Args:
            **parameters: Keyword arguments where keys are variable names and values are their values

        Returns:
            str: Generated :root block with variables, or None if validation fails

        Example:
            >>> css = "body { height: var(--bodyHeight); }"
            >>> parameterizer = CSSParameterizer(css)
            >>> parameterizer.apply_parameters({'bodyHeight':"100vh"})
            ':root {\\n  --bodyHeight: 100vh;\\n}\\n\\nbody { height: var(--bodyHeight); }'
        """
        missing_vars = self._validate_parameters(parameters)

        if missing_vars:
            # print(f"Error: Missing required variables: {missing_vars}")
            return None

        # Format parameters with -- prefix if not present
        formatted_params = {
            f"--{k}" if not k.startswith("--") else k: v for k, v in parameters.items()
        }

        # Generate the :root block
        root_block = [":root {"]
        for var_name, value in sorted(formatted_params.items()):
            if var_name in self.variables:
                root_block.append(f"  {var_name}: {value};")
        root_block.append("}")

        return "\n".join(root_block)

    def apply_parameters(self, parameters: dict) -> Optional[str]:
        """
        Generate the complete CSS with the :root block and original CSS content.

        Args:
            **parameters: Keyword arguments where keys are variable names and values are their values

        Returns:
            str: Complete CSS with :root block and original content, or None if validation fails
        """
        root_block = self.generate_root(**parameters)
        if root_block is None:
            return None

        return f"{root_block}\n\n{self.css_content}"


# Example usage
if __name__ == "__main__":
    import doctest

    doctest.testmod()
