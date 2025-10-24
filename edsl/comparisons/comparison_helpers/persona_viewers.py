from __future__ import annotations

"""Classes for viewing and displaying agent personas and traits."""

from typing import Dict, Any, List


class PersonaViewer:
    """Interactive viewer for displaying just the persona trait from candidates."""

    def __init__(self, comparisons: List, agent_name: str = None):
        """Initialize with comparisons list.

        Args:
            comparisons: List of ResultPairComparison objects
            agent_name: Optional agent name for context
        """
        self.comparisons = comparisons
        self.agent_name = agent_name
        self.personas = self._extract_personas()

    def _extract_personas(self) -> List[Dict[str, Any]]:
        """Extract just the persona trait from each comparison's candidate agent."""
        personas = []
        for idx, comp in enumerate(self.comparisons):
            persona_data = {
                "index": idx,
                "persona": None,
            }

            # Extract persona trait from result_A (candidate)
            if hasattr(comp.result_A, "agent") and hasattr(
                comp.result_A.agent, "traits"
            ):
                traits = comp.result_A.agent.traits or {}
                persona_data["persona"] = traits.get("persona", "No persona defined")
            else:
                persona_data["persona"] = "No persona available"

            personas.append(persona_data)

        return personas

    def _repr_html_(self) -> str:
        """Return HTML representation with persona viewer."""
        if not self.personas:
            return "<p>No personas found in comparisons.</p>"

        # Generate unique ID for this viewer instance
        import random

        viewer_id = f"pv_{random.randint(100000, 999999)}"

        html = [
            f'<div id="persona-viewer-{viewer_id}" style="font-family: Arial, sans-serif;">'
        ]

        # Title
        title = (
            f"Persona Viewer - Agent: {self.agent_name}"
            if self.agent_name
            else "Persona Viewer"
        )
        html.append(f"<h3>{title}</h3>")

        # Navigation controls
        html.append('<div style="margin: 10px 0;">')
        html.append(
            f'  <button onclick="prevPersona_{viewer_id}()" style="padding: 5px 15px; margin-right: 10px;">← Previous</button>'
        )
        html.append(
            f'  <span id="persona-counter-{viewer_id}" style="font-weight: bold; margin: 0 10px;">Candidate 1 of {len(self.personas)}</span>'
        )
        html.append(
            f'  <button onclick="nextPersona_{viewer_id}()" style="padding: 5px 15px; margin-left: 10px;">Next →</button>'
        )
        html.append("</div>")

        # Create a div for each persona (only first one visible)
        for idx, persona_data in enumerate(self.personas):
            display = "block" if idx == 0 else "none"
            html.append(
                f'<div class="persona-content-{viewer_id}" id="persona-{viewer_id}-{idx}" style="display: {display};">'
            )

            # Show persona in a textbox
            persona_text = str(persona_data["persona"])
            html.append(
                '<div style="background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-top: 10px; white-space: pre-wrap; font-family: Georgia, serif; line-height: 1.6;">'
            )
            html.append(persona_text)
            html.append("</div>")
            html.append("</div>")

        # JavaScript for navigation (unique per instance)
        html.append("<script>")
        html.append(f"let currentPersona_{viewer_id} = 0;")
        html.append(f"const totalPersonas_{viewer_id} = {len(self.personas)};")
        html.append(
            f"""
function showPersona_{viewer_id}(index) {{
    // Hide all personas for this viewer
    const personas = document.querySelectorAll('.persona-content-{viewer_id}');
    personas.forEach(p => p.style.display = 'none');
    
    // Show selected persona
    const selected = document.getElementById('persona-{viewer_id}-' + index);
    if (selected) {{
        selected.style.display = 'block';
    }}
    
    // Update counter
    const counter = document.getElementById('persona-counter-{viewer_id}');
    if (counter) {{
        counter.textContent = 'Candidate ' + (index + 1) + ' of ' + totalPersonas_{viewer_id};
    }}
    
    currentPersona_{viewer_id} = index;
}}

function nextPersona_{viewer_id}() {{
    const next = (currentPersona_{viewer_id} + 1) % totalPersonas_{viewer_id};
    showPersona_{viewer_id}(next);
}}

function prevPersona_{viewer_id}() {{
    const prev = (currentPersona_{viewer_id} - 1 + totalPersonas_{viewer_id}) % totalPersonas_{viewer_id};
    showPersona_{viewer_id}(prev);
}}
        """
        )
        html.append("</script>")
        html.append("</div>")

        return "\n".join(html)


class FullTraitsTable:
    """Interactive HTML table for displaying and navigating through all traits."""

    def __init__(self, comparisons: List, agent_name: str = None):
        """Initialize with comparisons list.

        Args:
            comparisons: List of ResultPairComparison objects
            agent_name: Optional agent name for context
        """
        self.comparisons = comparisons
        self.agent_name = agent_name
        self.personas = self._extract_personas()

    def _extract_personas(self) -> List[Dict[str, Any]]:
        """Extract persona information from each comparison's agent traits."""
        personas = []
        for idx, comp in enumerate(self.comparisons):
            persona_data = {
                "index": idx,
                "result_A_traits": {},
                "result_B_traits": {},
            }

            # Extract traits from result_A
            if hasattr(comp.result_A, "agent") and hasattr(
                comp.result_A.agent, "traits"
            ):
                persona_data["result_A_traits"] = comp.result_A.agent.traits or {}

            # Extract traits from result_B
            if hasattr(comp.result_B, "agent") and hasattr(
                comp.result_B.agent, "traits"
            ):
                persona_data["result_B_traits"] = comp.result_B.agent.traits or {}

            # Also store agent names for reference
            if hasattr(comp.result_A, "agent") and hasattr(comp.result_A.agent, "name"):
                persona_data["result_A_name"] = comp.result_A.agent.name
            if hasattr(comp.result_B, "agent") and hasattr(comp.result_B.agent, "name"):
                persona_data["result_B_name"] = comp.result_B.agent.name

            personas.append(persona_data)

        return personas

    def _repr_html_(self) -> str:
        """Return HTML representation with interactive persona viewer."""
        if not self.personas:
            return "<p>No personas found in comparisons.</p>"

        # Generate unique ID for this viewer instance
        import random

        viewer_id = f"ftt_{random.randint(100000, 999999)}"

        # Get all unique trait keys across all personas
        all_traits_A = set()
        all_traits_B = set()
        for p in self.personas:
            all_traits_A.update(p["result_A_traits"].keys())
            all_traits_B.update(p["result_B_traits"].keys())

        all_traits_A = sorted(all_traits_A)
        all_traits_B = sorted(all_traits_B)

        html = [
            f'<div id="traits-viewer-{viewer_id}" style="font-family: Arial, sans-serif;">'
        ]

        # Title
        title = (
            f"Full Traits Viewer - Agent: {self.agent_name}"
            if self.agent_name
            else "Full Traits Viewer"
        )
        html.append(f"<h3>{title}</h3>")

        # Navigation controls
        html.append('<div style="margin: 10px 0;">')
        html.append(
            f'  <button onclick="prevTraits_{viewer_id}()" style="padding: 5px 15px; margin-right: 10px;">← Previous</button>'
        )
        html.append(
            f'  <span id="traits-counter-{viewer_id}" style="font-weight: bold; margin: 0 10px;">Candidate 1 of {len(self.personas)}</span>'
        )
        html.append(
            f'  <button onclick="nextTraits_{viewer_id}()" style="padding: 5px 15px; margin-left: 10px;">Next →</button>'
        )
        html.append("</div>")

        # Create a div for each persona (only first one visible)
        for idx, persona in enumerate(self.personas):
            display = "block" if idx == 0 else "none"
            html.append(
                f'<div class="traits-content-{viewer_id}" id="traits-{viewer_id}-{idx}" style="display: {display};">'
            )

            # Create table for this persona
            html.append(
                '<table style="border-collapse: collapse; width: 100%; margin-top: 10px;">'
            )
            html.append("<thead>")
            html.append('  <tr style="background-color: #f2f2f2;">')
            html.append(
                '    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Trait</th>'
            )
            html.append(
                '    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Candidate Value</th>'
            )
            html.append(
                '    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Gold Standard Value</th>'
            )
            html.append("  </tr>")
            html.append("</thead>")
            html.append("<tbody>")

            # Combine all trait keys
            all_trait_keys = sorted(set(all_traits_A) | set(all_traits_B))

            for trait_key in all_trait_keys:
                value_a = persona["result_A_traits"].get(trait_key, "-")
                value_b = persona["result_B_traits"].get(trait_key, "-")

                # Format values
                if value_a != "-":
                    value_a_str = str(value_a)
                    if len(value_a_str) > 100:
                        value_a_str = value_a_str[:100] + "..."
                else:
                    value_a_str = "-"

                if value_b != "-":
                    value_b_str = str(value_b)
                    if len(value_b_str) > 100:
                        value_b_str = value_b_str[:100] + "..."
                else:
                    value_b_str = "-"

                # Highlight if values differ
                if value_a != value_b and value_a != "-" and value_b != "-":
                    row_style = "background-color: #fff9c4;"
                else:
                    row_style = ""

                html.append(f'  <tr style="{row_style}">')
                html.append(
                    f'    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">{trait_key}</td>'
                )
                html.append(
                    f'    <td style="border: 1px solid #ddd; padding: 8px;">{value_a_str}</td>'
                )
                html.append(
                    f'    <td style="border: 1px solid #ddd; padding: 8px;">{value_b_str}</td>'
                )
                html.append("  </tr>")

            html.append("</tbody>")
            html.append("</table>")
            html.append("</div>")

        # JavaScript for navigation (unique per instance)
        html.append("<script>")
        html.append(f"let currentTraits_{viewer_id} = 0;")
        html.append(f"const totalTraits_{viewer_id} = {len(self.personas)};")
        html.append(
            f"""
function showTraits_{viewer_id}(index) {{
    // Hide all traits for this viewer
    const traits = document.querySelectorAll('.traits-content-{viewer_id}');
    traits.forEach(t => t.style.display = 'none');
    
    // Show selected traits
    const selected = document.getElementById('traits-{viewer_id}-' + index);
    if (selected) {{
        selected.style.display = 'block';
    }}
    
    // Update counter
    const counter = document.getElementById('traits-counter-{viewer_id}');
    if (counter) {{
        counter.textContent = 'Candidate ' + (index + 1) + ' of ' + totalTraits_{viewer_id};
    }}
    
    currentTraits_{viewer_id} = index;
}}

function nextTraits_{viewer_id}() {{
    const next = (currentTraits_{viewer_id} + 1) % totalTraits_{viewer_id};
    showTraits_{viewer_id}(next);
}}

function prevTraits_{viewer_id}() {{
    const prev = (currentTraits_{viewer_id} - 1 + totalTraits_{viewer_id}) % totalTraits_{viewer_id};
    showTraits_{viewer_id}(prev);
}}
        """
        )
        html.append("</script>")
        html.append("</div>")

        return "\n".join(html)

