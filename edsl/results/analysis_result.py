"""
AnalysisResult: Rich display wrapper for answer analysis service results.

Provides formatted terminal and HTML output for question analysis data
returned by the answer_analysis service.
"""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .results import Results


class AnalysisResult:
    """Rich wrapper for question analysis results from the answer_analysis service.
    
    Provides formatted output for displaying analysis summaries and visualizations
    in both terminal and Jupyter environments.
    
    Examples:
        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> # analysis = r.analysis.by_question('how_feeling')  # Via service
    """
    
    def __init__(self, data: Dict[str, Any], results: "Results"):
        """Initialize with analysis data.
        
        Args:
            data: Dict mapping question names to their analysis results
            results: The Results object this analysis came from
        """
        self._data = data
        self._results = results
        self._question_names = list(data.keys())
    
    @property
    def questions(self) -> List[str]:
        """Get the list of analyzed question names."""
        return self._question_names
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get the raw analysis data."""
        return self._data
    
    def get(self, question_name: str) -> Dict[str, Any]:
        """Get analysis for a specific question."""
        return self._data.get(question_name, {})
    
    def __repr__(self) -> str:
        """Terminal representation with formatted output."""
        lines = []
        
        for q_name, result in self._data.items():
            if result.get("status") == "error":
                lines.append(f"Question: {q_name}")
                lines.append(f"  Error: {result.get('error', 'Unknown error')}")
                lines.append("")
                continue
            
            # Header
            q_type = result.get('question_type', 'unknown')
            # Try to extract from summary_text if not directly available
            if q_type == 'unknown':
                summary_text = result.get('summary', result.get('summary_text', ''))
                if 'Type: ' in summary_text:
                    for line in summary_text.split('\n'):
                        if line.strip().startswith('Type:'):
                            q_type = line.split(':', 1)[1].strip()
                            break
            
            lines.append("=" * 60)
            lines.append(f"  Question: {q_name}")
            lines.append(f"  Type: {q_type}")
            lines.append("=" * 60)
            lines.append("")
            
            # Summary
            summary = result.get("summary", result.get("summary_text", ""))
            if summary:
                lines.append("Summary:")
                lines.append("-" * 40)
                for line in summary.split("\n"):
                    lines.append(f"  {line}")
                lines.append("")
            
            # Visualization
            viz = result.get("visualization", result.get("visualization_text", ""))
            if viz:
                lines.append("Distribution:")
                lines.append("-" * 40)
                lines.append(viz)
                lines.append("")
        
        return "\n".join(lines)
    
    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks."""
        html_parts = []
        
        for q_name, result in self._data.items():
            if result.get("status") == "error":
                html_parts.append(f"""
                <div style="border: 1px solid #f5c6cb; padding: 15px; margin: 10px 0; 
                            border-radius: 8px; background: #f8d7da;">
                    <h3 style="color: #721c24; margin-top: 0;">{q_name}</h3>
                    <p style="color: #721c24;">Error: {result.get('error', 'Unknown error')}</p>
                </div>
                """)
                continue
            
            question_type = result.get("question_type", "unknown")
            summary = result.get("summary", result.get("summary_text", "")).replace("\n", "<br>")
            viz = result.get("visualization", result.get("visualization_text", ""))
            
            # Format distribution if available
            distribution_html = ""
            dist = result.get("distribution", {})
            if dist:
                distribution_html = "<h4>Distribution</h4><table style='width: 100%;'>"
                total = sum(d.get("count", d) if isinstance(d, dict) else d for d in dist.values())
                for option, data in dist.items():
                    count = data.get("count", data) if isinstance(data, dict) else data
                    pct = (count / total * 100) if total > 0 else 0
                    bar_width = int(pct * 2)  # Scale to reasonable width
                    distribution_html += f"""
                    <tr>
                        <td style="width: 30%; padding: 5px;">{option}</td>
                        <td style="width: 10%; padding: 5px; text-align: right;">{count}</td>
                        <td style="width: 60%; padding: 5px;">
                            <div style="background: #3498db; height: 20px; width: {bar_width}%;"></div>
                        </td>
                    </tr>
                    """
                distribution_html += "</table>"
            
            # Statistics if available
            stats_html = ""
            stats = result.get("statistics", {})
            if stats:
                stats_html = "<h4>Statistics</h4><table style='width: 50%;'>"
                for key, value in stats.items():
                    stats_html += f"<tr><td style='padding: 3px;'>{key}</td><td style='padding: 3px;'>{value}</td></tr>"
                stats_html += "</table>"
            
            html_parts.append(f"""
            <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; 
                        border-radius: 8px; background: #f9f9f9; font-family: sans-serif;">
                <h3 style="color: #2c3e50; margin-top: 0; border-bottom: 2px solid #3498db; 
                           padding-bottom: 10px;">{q_name}</h3>
                <p><strong>Type:</strong> {question_type}</p>
                {stats_html}
                {distribution_html}
            </div>
            """)
        
        return "".join(html_parts)
    
    def __getitem__(self, key: str) -> Dict[str, Any]:
        """Access analysis for a specific question by name."""
        return self._data[key]
    
    def __iter__(self):
        """Iterate over question names."""
        return iter(self._question_names)
    
    def __len__(self) -> int:
        """Return the number of questions analyzed."""
        return len(self._question_names)

