"""
Column Tree Visualization for Results objects.

This module provides a ColumnTreeVisualization class that displays hierarchical
column structure using mermaid diagrams in Jupyter notebooks and formatted text
in terminals.
"""

from typing import Dict, List
import html


class ColumnTreeVisualization:
    """A visualization of Results columns organized in a tree structure.

    This class creates both mermaid diagram representations for Jupyter notebooks
    and formatted text representations for terminal display.
    """

    def __init__(self, data_types: Dict[str, List[str]]):
        """Initialize the visualization with grouped column data.

        Args:
            data_types: Dictionary mapping data type names to lists of column keys.
                       Example: {'agent': ['status', 'name'], 'answer': ['how_feeling']}
        """
        self.data_types = data_types

    def _generate_mermaid_diagram(self) -> str:
        """Generate a mermaid diagram showing the column hierarchy.

        Returns:
            str: A mermaid diagram in text format.
        """
        lines = ["graph TD"]
        lines.append("    Results --> Data_Types[Data Types]")

        # Add each data type as a node connected to the root
        for data_type in sorted(self.data_types.keys()):
            data_type_node = f"DT_{data_type}"
            lines.append(f"    Data_Types --> {data_type_node}[{data_type}]")

            # Add each key as a child of the data type
            for key in sorted(self.data_types[data_type]):
                # Clean key names for mermaid (replace special characters)
                key_node = f"KEY_{data_type}_{key}".replace(".", "_").replace("-", "_")
                key_display = html.escape(key)
                lines.append(f"    {data_type_node} --> {key_node}[{key_display}]")

        # Add styling
        lines.extend([
            "",
            "    classDef dataType fill:#e1f5fe,stroke:#01579b,stroke-width:2px",
            "    classDef key fill:#f3e5f5,stroke:#4a148c,stroke-width:1px",
            "    classDef root fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px",
            "",
            "    class Results root",
            "    class Data_Types root"
        ])

        # Apply styling to data type nodes
        for data_type in self.data_types.keys():
            lines.append(f"    class DT_{data_type} dataType")

        # Apply styling to key nodes
        for data_type, keys in self.data_types.items():
            for key in keys:
                key_node = f"KEY_{data_type}_{key}".replace(".", "_").replace("-", "_")
                lines.append(f"    class {key_node} key")

        return "\n".join(lines)

    def _generate_text_representation(self) -> str:
        """Generate a text-based tree representation for terminal display.

        Returns:
            str: A formatted text tree.
        """
        lines = ["Results Columns Tree:"]
        lines.append("├─ Data Types")

        data_type_items = sorted(self.data_types.items())
        for i, (data_type, keys) in enumerate(data_type_items):
            is_last_data_type = (i == len(data_type_items) - 1)
            data_type_prefix = "└─" if is_last_data_type else "├─"
            lines.append(f"   {data_type_prefix} {data_type} ({len(keys)} keys)")

            # Add keys for this data type
            sorted_keys = sorted(keys)
            for j, key in enumerate(sorted_keys):
                is_last_key = (j == len(sorted_keys) - 1)
                if is_last_data_type:
                    key_prefix = "   └─" if is_last_key else "   ├─"
                else:
                    key_prefix = "│  └─" if is_last_key else "│  ├─"
                lines.append(f"   {key_prefix} {key}")

        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """Generate HTML representation for Jupyter notebook display.

        Returns:
            str: HTML containing a mermaid diagram.
        """
        mermaid_code = self._generate_mermaid_diagram()

        html_content = f"""
        <div id="mermaid-{id(self)}" class="mermaid">
            {mermaid_code}
        </div>
        <script>
            // Load mermaid if not already loaded
            if (typeof mermaid === 'undefined') {{
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js';
                script.onload = function() {{
                    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
                    mermaid.init(undefined, '#mermaid-{id(self)}');
                }};
                document.head.appendChild(script);
            }} else {{
                mermaid.init(undefined, '#mermaid-{id(self)}');
            }}
        </script>
        <style>
            .mermaid {{
                text-align: center;
                margin: 20px 0;
            }}
        </style>
        <details style="margin-top: 10px;">
            <summary>Show as text tree</summary>
            <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">
{self._generate_text_representation()}
            </pre>
        </details>
        """
        return html_content

    def __str__(self) -> str:
        """Generate string representation for terminal display.

        Returns:
            str: A formatted text tree.
        """
        return self._generate_text_representation()

    def __repr__(self) -> str:
        """Generate repr string for the object.

        Shows the tree visualization in terminal environments, but a summary in Jupyter
        (where _repr_html_ handles the display).

        Returns:
            str: Either the tree visualization or a summary.
        """
        # Check if we're in IPython/Jupyter - if so, use summary since HTML will handle display
        try:
            from IPython import get_ipython
            ipy = get_ipython()
            if ipy is not None:
                # Check if we're in Jupyter notebook/kernel vs IPython terminal
                if hasattr(ipy, 'kernel'):
                    # We're in Jupyter, use summary since _repr_html_ will be used
                    total_keys = sum(len(keys) for keys in self.data_types.values())
                    return f"ColumnTreeVisualization({len(self.data_types)} data types, {total_keys} total keys)"
        except ImportError:
            pass

        # Default to showing the tree visualization in terminal/regular Python
        return self._generate_text_representation()

    def to_dict(self) -> Dict[str, List[str]]:
        """Return the underlying data structure.

        Returns:
            Dict[str, List[str]]: The data types and their keys.
        """
        return self.data_types.copy()

    def get_data_type_keys(self, data_type: str) -> List[str]:
        """Get all keys for a specific data type.

        Args:
            data_type: The name of the data type.

        Returns:
            List[str]: List of keys for the specified data type.

        Raises:
            KeyError: If the data type doesn't exist.
        """
        if data_type not in self.data_types:
            available_types = list(self.data_types.keys())
            raise KeyError(f"Data type '{data_type}' not found. Available types: {available_types}")
        return self.data_types[data_type].copy()

    def get_data_types(self) -> List[str]:
        """Get all available data types.

        Returns:
            List[str]: Sorted list of all data type names.
        """
        return sorted(self.data_types.keys())