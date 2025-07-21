"""
Memory debugging utilities for analyzing object references and memory leaks.
"""

import gc
import os
import sys
import time
import types
import inspect
import webbrowser
import base64
import html
from datetime import datetime
from typing import Any, Set, List, Dict, Tuple

# Try to import objgraph, which is only available as a dev dependency
try:
    import objgraph

    OBJGRAPH_AVAILABLE = True
except ImportError:
    OBJGRAPH_AVAILABLE = False


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

    def _get_source_info(self, obj: Any) -> Dict[str, Any]:
        """Get source code information for an object if available."""
        result = {
            "module": getattr(obj, "__module__", "unknown"),
            "file": "unknown",
            "line": 0,
            "source": None,
            "has_source": False,
            "type_str": str(type(obj)),
        }

        try:
            # Try to get the source file and line number
            if hasattr(obj, "__class__"):
                module = inspect.getmodule(obj.__class__)
                if module:
                    result["module"] = module.__name__
                    try:
                        file = inspect.getsourcefile(obj.__class__)
                        if file:
                            result["file"] = file
                            try:
                                _, line = inspect.getsourcelines(obj.__class__)
                                result["line"] = line
                                result["has_source"] = True
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            # Silently fail if we can't get source info
            pass

        return result

    def _generate_html_report(
        self, prefix: str = "", output_dir: str = None
    ) -> Tuple[str, str, str]:
        """
        Generate a comprehensive HTML memory debugging report.

        Args:
            prefix: Optional prefix for output files. If empty, uses target object type.
            output_dir: Optional directory to write files to. If None, uses tempdir or current directory.

        Returns:
            A tuple containing (html_filename, refs_graph_filename, backrefs_graph_filename)
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if not prefix:
            prefix = type(self.target_obj).__name__.lower()

        # Determine output directory
        if output_dir is None:
            output_dir = os.environ.get("EDSL_MEMORY_DEBUG_DIR", "")

        if output_dir:
            # Ensure directory exists
            os.makedirs(output_dir, exist_ok=True)

        # Prepare filenames
        html_filename = (
            os.path.join(output_dir, f"{prefix}_memory_debug_{timestamp}.html")
            if output_dir
            else f"{prefix}_memory_debug_{timestamp}.html"
        )
        refs_graph_filename = (
            os.path.join(output_dir, f"{prefix}_outgoing_refs_{timestamp}.png")
            if output_dir
            else f"{prefix}_outgoing_refs_{timestamp}.png"
        )
        backrefs_graph_filename = (
            os.path.join(output_dir, f"{prefix}_incoming_refs_{timestamp}.png")
            if output_dir
            else f"{prefix}_incoming_refs_{timestamp}.png"
        )

        # Generate object graphs - both directions
        graph_exists = False
        backrefs_graph_exists = False

        if OBJGRAPH_AVAILABLE:
            try:
                # Use objgraph's backup function to filter frames and functions
                def skip_frames(obj):
                    return not isinstance(obj, (types.FrameType, types.FunctionType))

                # Outgoing references (what this object references)
                objgraph.show_refs(
                    self.target_obj,
                    filename=refs_graph_filename,
                    max_depth=3,
                    extra_ignore=[
                        id(obj)
                        for obj in gc.get_objects()
                        if isinstance(obj, (types.FrameType, types.FunctionType))
                    ],
                )
                graph_exists = True

                # Incoming references (what references this object)
                objgraph.show_backrefs(
                    self.target_obj,
                    filename=backrefs_graph_filename,
                    max_depth=3,
                    extra_ignore=[
                        id(obj)
                        for obj in gc.get_objects()
                        if isinstance(obj, (types.FrameType, types.FunctionType))
                    ],
                )
                backrefs_graph_exists = True
            except Exception as e:
                print(f"Warning: Could not generate object graph visualization: {e}")
                graph_exists = False
        else:
            print(
                "Warning: objgraph package is not available. Install it with 'pip install objgraph' to enable visualizations."
            )

        # Get all reference cycle information
        import io
        from contextlib import redirect_stdout

        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            cycles = self.detect_reference_cycles()

        cycle_output = captured_output.getvalue()

        # Get referrers and referents with source info
        referrers = gc.get_referrers(self.target_obj)
        referents = gc.get_referents(self.target_obj)

        # Skip frames and function objects for referrers
        filtered_referrers = [
            ref
            for ref in referrers
            if not isinstance(ref, (types.FrameType, types.FunctionType))
        ]

        # Get source info for all objects
        referrer_info = [self._get_source_info(ref) for ref in filtered_referrers]
        referent_info = [self._get_source_info(ref) for ref in referents]

        # Get target object info
        target_info = self._get_source_info(self.target_obj)

        # Generate HTML content
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memory Debug Report - {type(self.target_obj).__name__}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        h1 {{
            border-bottom: 2px solid #eaecef;
            padding-bottom: 10px;
        }}
        h2 {{
            margin-top: 30px;
            border-bottom: 1px solid #eaecef;
            padding-bottom: 5px;
        }}
        .info-box {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }}
        .warning {{
            background-color: #fff3cd;
            border-color: #ffeeba;
        }}
        .object {{
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-left: 4px solid #007bff;
            border-radius: 3px;
        }}
        .object-header {{
            display: flex;
            justify-content: space-between;
            font-weight: bold;
        }}
        .object-details {{
            margin-top: 5px;
            font-size: 0.9em;
        }}
        .file-link {{
            color: #007bff;
            text-decoration: none;
        }}
        .file-link:hover {{
            text-decoration: underline;
        }}
        .unhashable {{
            border-left-color: #dc3545;
        }}
        .cycle {{
            border-left-color: #fd7e14;
        }}
        .tab {{
            overflow: hidden;
            border: 1px solid #ccc;
            background-color: #f1f1f1;
            border-radius: 5px 5px 0 0;
        }}
        .tab button {{
            background-color: inherit;
            float: left;
            border: none;
            outline: none;
            cursor: pointer;
            padding: 10px 16px;
            transition: 0.3s;
        }}
        .tab button:hover {{
            background-color: #ddd;
        }}
        .tab button.active {{
            background-color: #ccc;
        }}
        .tabcontent {{
            display: none;
            padding: 20px;
            border: 1px solid #ccc;
            border-top: none;
            border-radius: 0 0 5px 5px;
        }}
        .code {{
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            background-color: #f6f8fa;
            padding: 10px;
            border-radius: 3px;
            overflow-x: auto;
        }}
        .graph-container {{
            text-align: center;
            margin: 20px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .toggle-button {{
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 5px 10px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 12px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <h1>Memory Debug Report - {type(self.target_obj).__name__}</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="info-box">
        <h3>Target Object Information</h3>
        <p><strong>Type:</strong> {type(self.target_obj)}</p>
        <p><strong>ID:</strong> {id(self.target_obj)}</p>
        <p><strong>Module:</strong> {target_info['module']}</p>
        <p><strong>Reference Count:</strong> {sys.getrefcount(self.target_obj)}</p>
        {f'<p><strong>Source File:</strong> <a href="file://{target_info["file"]}" class="file-link">{os.path.basename(target_info["file"])}</a> (line {target_info["line"]})</p>' if target_info["has_source"] else ''}
    </div>
    
    <div class="tab">
        <button class="tablinks" onclick="openTab(event, 'Overview')" id="defaultOpen">Overview</button>
        <button class="tablinks" onclick="openTab(event, 'Referrers')">Referrers ({len(filtered_referrers)})</button>
        <button class="tablinks" onclick="openTab(event, 'Referents')">Referents ({len(referents)})</button>
        <button class="tablinks" onclick="openTab(event, 'Cycles')" {'style="color: red;"' if cycles else ''}>Cycles {f"({len(cycles)})" if cycles else ""}</button>
        <button class="tablinks" onclick="openTab(event, 'Graph')">Reference Visualizations</button>
    </div>
    
    <div id="Overview" class="tabcontent">
        <h2>Memory Analysis Overview</h2>
        <div class="info-box">
            <p>This report analyzes the memory references to and from the target object. It helps identify potential memory leaks by showing object relationships.</p>
            <p><strong>Total referrers:</strong> {len(filtered_referrers)}</p>
            <p><strong>Total referents:</strong> {len(referents)}</p>
            <p><strong>Potential reference cycles:</strong> {len(cycles) if cycles else "None detected"}</p>
        </div>
        
        <h3>Common Types</h3>
        <table>
            <tr>
                <th>Type</th>
                <th>Count as Referrer</th>
                <th>Count as Referent</th>
            </tr>
"""

        # Count types
        referrer_types = {}
        for ref in filtered_referrers:
            type_name = type(ref).__name__
            referrer_types[type_name] = referrer_types.get(type_name, 0) + 1

        referent_types = {}
        for ref in referents:
            type_name = type(ref).__name__
            referent_types[type_name] = referent_types.get(type_name, 0) + 1

        # Get all unique types
        all_types = set(list(referrer_types.keys()) + list(referent_types.keys()))

        # Add type rows to the table
        for type_name in sorted(all_types):
            html_content += f"""
            <tr>
                <td>{type_name}</td>
                <td>{referrer_types.get(type_name, 0)}</td>
                <td>{referent_types.get(type_name, 0)}</td>
            </tr>"""

        html_content += """
        </table>
    </div>
    
    <div id="Referrers" class="tabcontent">
        <h2>Objects Referring to Target</h2>
        <p>These objects hold references to the target object:</p>
"""

        # Add referrers
        for i, (ref, info) in enumerate(zip(filtered_referrers, referrer_info)):
            object_id = id(ref)
            object_type = type(ref).__name__
            is_unhashable = not self._is_hashable(ref)

            html_content += f"""
        <div class="object {'unhashable' if is_unhashable else ''}">
            <div class="object-header">
                <span>[{i}] {object_type}{' (unhashable)' if is_unhashable else ''}</span>
                <span>ID: {object_id}</span>
            </div>
            <div class="object-details">
                <p><strong>Module:</strong> {info['module']}</p>
                {f'<p><strong>Source:</strong> <a href="file://{info["file"]}" class="file-link">{os.path.basename(info["file"])}</a> (line {info["line"]})</p>' if info["has_source"] else ''}"""

            # Add more specific information based on type
            if isinstance(ref, dict):
                html_content += f"""
                <p><strong>Dict size:</strong> {len(ref)} items</p>
                <button class="toggle-button" onclick="toggleDetails('referrer-{i}')">Show/Hide Contents</button>
                <div id="referrer-{i}" style="display: none;">
                    <table>
                        <tr><th>Key</th><th>Value Type</th></tr>"""

                for k, v in list(ref.items())[:20]:  # Limit to 20 items
                    # Skip showing the target object itself
                    if v is self.target_obj:
                        key_html = html.escape(str(k))
                        html_content += f"""
                        <tr><td>{key_html}</td><td><strong>TARGET OBJECT</strong></td></tr>"""
                    else:
                        key_html = html.escape(str(k))
                        html_content += f"""
                        <tr><td>{key_html}</td><td>{type(v).__name__}</td></tr>"""

                if len(ref) > 20:
                    html_content += f"""
                        <tr><td colspan="2">... and {len(ref) - 20} more items</td></tr>"""

                html_content += """
                    </table>
                </div>"""
            elif isinstance(ref, (list, tuple)):
                html_content += f"""
                <p><strong>{type(ref).__name__} size:</strong> {len(ref)} items</p>
                <button class="toggle-button" onclick="toggleDetails('referrer-{i}')">Show/Hide Contents</button>
                <div id="referrer-{i}" style="display: none;">
                    <table>
                        <tr><th>Index</th><th>Value Type</th></tr>"""

                for idx, item in enumerate(ref[:20]):  # Limit to 20 items
                    if item is self.target_obj:
                        html_content += f"""
                        <tr><td>{idx}</td><td><strong>TARGET OBJECT</strong></td></tr>"""
                    else:
                        html_content += f"""
                        <tr><td>{idx}</td><td>{type(item).__name__}</td></tr>"""

                if len(ref) > 20:
                    html_content += f"""
                        <tr><td colspan="2">... and {len(ref) - 20} more items</td></tr>"""

                html_content += """
                    </table>
                </div>"""

            html_content += """
            </div>
        </div>"""

        html_content += """
    </div>
    
    <div id="Referents" class="tabcontent">
        <h2>Objects Referenced by Target</h2>
        <p>These objects are referenced by the target object:</p>
"""

        # Add referents
        for i, (ref, info) in enumerate(zip(referents, referent_info)):
            object_id = id(ref)
            object_type = type(ref).__name__
            is_unhashable = not self._is_hashable(ref)

            html_content += f"""
        <div class="object {'unhashable' if is_unhashable else ''}">
            <div class="object-header">
                <span>[{i}] {object_type}{' (unhashable)' if is_unhashable else ''}</span>
                <span>ID: {object_id}</span>
            </div>
            <div class="object-details">
                <p><strong>Module:</strong> {info['module']}</p>
                {f'<p><strong>Source:</strong> <a href="file://{info["file"]}" class="file-link">{os.path.basename(info["file"])}</a> (line {info["line"]})</p>' if info["has_source"] else ''}"""

            # Add specific information for dicts and sequences
            if isinstance(ref, dict):
                html_content += f"""
                <p><strong>Dict size:</strong> {len(ref)} items</p>
                <button class="toggle-button" onclick="toggleDetails('referent-{i}')">Show/Hide Contents</button>
                <div id="referent-{i}" style="display: none;">
                    <table>
                        <tr><th>Key</th><th>Value Type</th></tr>"""

                for k, v in list(ref.items())[:20]:  # Limit to 20 items
                    key_html = html.escape(str(k))
                    html_content += f"""
                        <tr><td>{key_html}</td><td>{type(v).__name__}</td></tr>"""

                if len(ref) > 20:
                    html_content += f"""
                        <tr><td colspan="2">... and {len(ref) - 20} more items</td></tr>"""

                html_content += """
                    </table>
                </div>"""
            elif isinstance(ref, (list, tuple)):
                html_content += f"""
                <p><strong>{type(ref).__name__} size:</strong> {len(ref)} items</p>
                <button class="toggle-button" onclick="toggleDetails('referent-{i}')">Show/Hide Contents</button>
                <div id="referent-{i}" style="display: none;">
                    <table>
                        <tr><th>Index</th><th>Value Type</th></tr>"""

                for idx, item in enumerate(ref[:20]):  # Limit to 20 items
                    html_content += f"""
                        <tr><td>{idx}</td><td>{type(item).__name__}</td></tr>"""

                if len(ref) > 20:
                    html_content += f"""
                        <tr><td colspan="2">... and {len(ref) - 20} more items</td></tr>"""

                html_content += """
                    </table>
                </div>"""

            html_content += """
            </div>
        </div>"""

        html_content += """
    </div>
    
    <div id="Cycles" class="tabcontent">
        <h2>Reference Cycles</h2>
"""

        # Add reference cycle output
        if cycles:
            html_content += f"""
        <div class="info-box warning">
            <p>Found {len(cycles)} potential reference cycles. These objects might be causing memory leaks.</p>
        </div>
"""
            # Add cycle details
            for i, obj in enumerate(cycles):
                object_type = type(obj).__name__
                object_id = id(obj)
                info = self._get_source_info(obj)

                html_content += f"""
        <div class="object cycle">
            <div class="object-header">
                <span>[{i}] {object_type}</span>
                <span>ID: {object_id}</span>
            </div>
            <div class="object-details">
                <p><strong>Module:</strong> {info['module']}</p>
                {f'<p><strong>Source:</strong> <a href="file://{info["file"]}" class="file-link">{os.path.basename(info["file"])}</a> (line {info["line"]})</p>' if info["has_source"] else ''}
            </div>
        </div>"""
        else:
            html_content += """
        <p>No reference cycles detected among hashable objects.</p>
"""

        # Add unhashable object analysis
        html_content += """
        <h3>Unhashable Object Analysis</h3>
        <div class="code">
"""
        for line in cycle_output.splitlines():
            html_content += f"{html.escape(line)}<br>"

        html_content += """
        </div>
    </div>
    
    <div id="Graph" class="tabcontent">
        <h2>Object Graph Visualization</h2>
        
        <h3>Outgoing References (Objects Referenced By Target)</h3>
        <p>This graph shows what objects are referenced by the target object:</p>
"""

        if graph_exists:
            try:
                with open(refs_graph_filename, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                html_content += f"""
        <div class="graph-container">
            <img src="data:image/png;base64,{img_data}" alt="Objects referenced by target" style="max-width: 100%;">
        </div>
        <p><a href="file://{os.path.abspath(refs_graph_filename)}" target="_blank">Open full-size outgoing references graph</a></p>
"""
            except Exception as e:
                html_content += f"""
        <div class="info-box warning">
            <p>Could not embed outgoing references graph image: {e}</p>
            <p><a href="file://{os.path.abspath(refs_graph_filename)}" target="_blank">Open outgoing references graph image</a></p>
        </div>
"""
        else:
            html_content += """
        <div class="info-box warning">
            <p>Could not generate outgoing references graph visualization.</p>
        </div>
"""

        html_content += """
        <h3>Incoming References (Objects Referencing Target)</h3>
        <p>This graph shows what objects have a strong reference to the target object:</p>
"""

        if backrefs_graph_exists:
            try:
                with open(backrefs_graph_filename, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                html_content += f"""
        <div class="graph-container">
            <img src="data:image/png;base64,{img_data}" alt="Objects referencing the target" style="max-width: 100%;">
        </div>
        <p><a href="file://{os.path.abspath(backrefs_graph_filename)}" target="_blank">Open full-size incoming references graph</a></p>
"""
            except Exception as e:
                html_content += f"""
        <div class="info-box warning">
            <p>Could not embed incoming references graph image: {e}</p>
            <p><a href="file://{os.path.abspath(backrefs_graph_filename)}" target="_blank">Open incoming references graph image</a></p>
        </div>
"""
        else:
            html_content += """
        <div class="info-box warning">
            <p>Could not generate incoming references graph visualization.</p>
        </div>
"""

        html_content += """
    </div>
    
    <script>
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }
        
        function toggleDetails(id) {
            var element = document.getElementById(id);
            if (element.style.display === "none") {
                element.style.display = "block";
            } else {
                element.style.display = "none";
            }
        }
        
        // Open the default tab
        document.getElementById("defaultOpen").click();
    </script>
</body>
</html>
"""

        # Write HTML to file
        with open(html_filename, "w") as f:
            f.write(html_content)

        return html_filename, refs_graph_filename, backrefs_graph_filename

    def debug_memory(
        self, prefix: str = "", open_browser: bool = True, output_dir: str = None
    ) -> str:
        """
        Comprehensive memory debugging that writes results to files and opens an HTML report.

        Args:
            prefix: Optional prefix for output files. If empty, uses target object type.
            open_browser: Whether to automatically open the HTML report in a browser.
            output_dir: Optional directory to write files to. If None, uses EDSL_MEMORY_DEBUG_DIR
                        environment variable or current directory.

        Returns:
            The path to the HTML report file.
        """
        # Generate HTML report with both incoming and outgoing reference visualizations
        html_filename, outgoing_refs_filename, incoming_refs_filename = (
            self._generate_html_report(prefix, output_dir)
        )

        # Also create the legacy markdown report for backward compatibility
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if not prefix:
            prefix = type(self.target_obj).__name__.lower()

        # Determine output directory
        if output_dir is None:
            output_dir = os.environ.get("EDSL_MEMORY_DEBUG_DIR", "")

        # Write reference analysis to markdown file
        md_filename = (
            os.path.join(output_dir, f"{prefix}_memory_debug_{timestamp}.md")
            if output_dir
            else f"{prefix}_memory_debug_{timestamp}.md"
        )
        with open(md_filename, "w") as f:
            f.write(f"# Memory Debug Report for {type(self.target_obj)}\n\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"HTML Report: [View HTML Report]({html_filename})\n\n")
            f.write("Visualizations:\n")
            f.write(
                f"- [Outgoing References Graph]({outgoing_refs_filename}) - Objects referenced by the target\n"
            )
            f.write(
                f"- [Incoming References Graph]({incoming_refs_filename}) - Objects that reference the target\n\n"
            )

            # Capture reference count
            f.write("## Reference Count\n")
            f.write(f"Current reference count: {sys.getrefcount(self.target_obj)}\n\n")

            # Capture referrers
            f.write("## Objects Referring to Target\n")
            referrers = gc.get_referrers(self.target_obj)
            for ref in referrers:
                if isinstance(ref, (types.FrameType, types.FunctionType)):
                    continue
                f.write(f"- Type: {type(ref)}\n")

            # Capture reference cycles
            f.write("\n## Reference Cycles\n")

            # Get all reference cycle information (capture stdout for the detailed info)
            import io
            from contextlib import redirect_stdout

            captured_output = io.StringIO()
            with redirect_stdout(captured_output):
                cycles = self.detect_reference_cycles()

            # Write the cycle information to file
            cycle_output = captured_output.getvalue()
            if cycles:
                f.write(f"Found {len(cycles)} potential reference cycles:\n")
                for obj in cycles:
                    f.write(f"- Type: {type(obj)}, ID: {id(obj)}\n")
            else:
                f.write("No reference cycles detected among hashable objects\n")

            # Add the detailed unhashable information
            f.write("\n## Unhashable Object Analysis\n")
            f.write(cycle_output)

        # Open the HTML report in a browser if requested
        if open_browser:
            try:
                webbrowser.open(f"file://{os.path.abspath(html_filename)}")
                print(f"Opened memory report in browser: {html_filename}")
            except Exception as e:
                print(f"Could not open browser: {e}")
                print(f"Report saved to: {html_filename}")
        else:
            print(f"HTML Report saved to: {html_filename}")

        return html_filename

    def inspect_references(self, skip_frames: bool = True) -> None:
        """
        Inspect what objects are referring to the target object.

        Args:
            skip_frames: If True, skip function frames and local namespaces
        """
        print(
            f"\nReference count for {type(self.target_obj)}: {sys.getrefcount(self.target_obj)}"
        )
        print("\nObjects referring to this object:")

        referrers = gc.get_referrers(self.target_obj)
        for ref in referrers:
            # Skip frames and function locals if requested
            if skip_frames and (
                isinstance(ref, (types.FrameType, types.FunctionType))
                or (isinstance(ref, dict) and ref.get("target_obj") is self.target_obj)
            ):
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

        # Separate hashable and unhashable objects
        hashable_referrers = []
        unhashable_referrers = []
        hashable_referents = []
        unhashable_referents = []

        for obj in referrers:
            if self._is_hashable(obj):
                hashable_referrers.append(obj)
            else:
                unhashable_referrers.append(obj)

        for obj in referents:
            if self._is_hashable(obj):
                hashable_referents.append(obj)
            else:
                unhashable_referents.append(obj)

        # Find common objects among hashable ones
        common_objects = set(hashable_referrers) & set(hashable_referents)

        if common_objects:
            print(
                f"Potential reference cycle detected! Found {len(common_objects)} common objects"
            )
            for shared_obj in common_objects:
                print(f"Type: {type(shared_obj)}, ID: {id(shared_obj)}")

        # Report on unhashable objects
        if unhashable_referrers or unhashable_referents:
            print(
                f"Note: {len(unhashable_referrers)} unhashable referrers and {len(unhashable_referents)} unhashable referents were excluded from cycle detection"
            )

            # Check for unhashable objects that might be in both lists
            potential_unhashable_cycles = []
            for ureferrer in unhashable_referrers:
                for ureferent in unhashable_referents:
                    if id(ureferrer) == id(ureferent):
                        potential_unhashable_cycles.append(ureferrer)

            if potential_unhashable_cycles:
                print(
                    f"Warning: Found {len(potential_unhashable_cycles)} unhashable objects that may be part of cycles:"
                )
                for obj in potential_unhashable_cycles:
                    print(f"  - Type: {type(obj)}, ID: {id(obj)}")

            # Report details of unhashable objects for further investigation
            print("Unhashable referrers:")
            for i, obj in enumerate(
                unhashable_referrers[:5]
            ):  # Limit to first 5 to avoid flooding output
                print(f"  - [{i}] Type: {type(obj)}, ID: {id(obj)}")
            if len(unhashable_referrers) > 5:
                print(f"  ... and {len(unhashable_referrers) - 5} more")

            print("Unhashable referents:")
            for i, obj in enumerate(unhashable_referents[:5]):  # Limit to first 5
                print(f"  - [{i}] Type: {type(obj)}, ID: {id(obj)}")
            if len(unhashable_referents) > 5:
                print(f"  ... and {len(unhashable_referents) - 5} more")

        # Add unhashable objects that might be in cycles to the full result list
        result_set = common_objects.copy()
        return result_set

    def _is_hashable(self, obj: Any) -> bool:
        """Helper method to check if an object is hashable."""
        try:
            hash(obj)
            return True
        except TypeError:
            return False

    def visualize_dependencies(
        self, max_depth: int = 3, output_dir: str = None, prefix: str = ""
    ) -> Tuple[str, str]:
        """
        Visualize object dependencies using objgraph.

        Args:
            max_depth: Maximum depth of reference tree to display
            output_dir: Directory to save visualization files
            prefix: Prefix for output files

        Returns:
            Tuple of (outgoing_refs_filename, incoming_refs_filename)
        """
        if not OBJGRAPH_AVAILABLE:
            print(
                "Warning: objgraph package is not available. Install it with 'pip install objgraph' to enable visualizations."
            )
            return "", ""

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if not prefix:
            prefix = type(self.target_obj).__name__.lower()

        # Determine output directory
        if output_dir is None:
            output_dir = os.environ.get("EDSL_MEMORY_DEBUG_DIR", "")

        if output_dir:
            # Ensure directory exists
            os.makedirs(output_dir, exist_ok=True)

        # Prepare filenames
        refs_filename = (
            os.path.join(output_dir, f"{prefix}_outgoing_refs_{timestamp}.png")
            if output_dir
            else f"{prefix}_outgoing_refs_{timestamp}.png"
        )
        backrefs_filename = (
            os.path.join(output_dir, f"{prefix}_incoming_refs_{timestamp}.png")
            if output_dir
            else f"{prefix}_incoming_refs_{timestamp}.png"
        )

        try:
            # Filter out frames and functions
            ignore_ids = [
                id(obj)
                for obj in gc.get_objects()
                if isinstance(obj, (types.FrameType, types.FunctionType))
            ]

            # For the regular references (what the object references)
            objgraph.show_refs(
                self.target_obj,
                max_depth=max_depth,
                filename=refs_filename,
                extra_ignore=ignore_ids,
            )

            # For the referrers (what references the object)
            objgraph.show_backrefs(
                self.target_obj,
                max_depth=max_depth,
                filename=backrefs_filename,
                extra_ignore=ignore_ids,
            )

            print(f"Outgoing references saved to: {refs_filename}")
            print(f"Incoming references saved to: {backrefs_filename}")

            return refs_filename, backrefs_filename
        except Exception as e:
            print(f"Error visualizing dependencies: {e}")
            return "", ""

    def _inspect_dict_reference(self, ref: Dict) -> None:
        """Helper method to inspect dictionary references."""
        for k, v in ref.items():
            if v is self.target_obj:
                print(f"  - Found in dict with key: {k}")
                try:
                    owner = [
                        o
                        for o in gc.get_referrers(ref)
                        if hasattr(o, "__dict__") and o.__dict__ is ref
                    ]
                    if owner:
                        print(f"    (This dict belongs to: {type(owner[0])})")
                except (AttributeError, TypeError, KeyError):
                    pass

    def _inspect_list_reference(self, ref: List) -> None:
        """Helper method to inspect list references."""
        try:
            idx = ref.index(self.target_obj)
            print(f"  - Found in list at index: {idx}")
            owners = [o for o in gc.get_referrers(ref) if hasattr(o, "__dict__")]
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

    def find_reference_paths(self, max_depth: int = 5) -> None:
        """
        Find and print paths to objects that reference the target object.
        This is a simplified version that directly prints the results.

        Args:
            max_depth: Maximum depth to search for references
        """
        print(
            f"\nFinding reference paths to {type(self.target_obj)} (id: {id(self.target_obj)}):"
        )

        # Create a simplified reference chain explorer
        def find_path_to_referrers(obj, path=None, depth=0, visited=None):
            if path is None:
                path = []
            if visited is None:
                visited = set()

            if depth > max_depth:
                return

            # Get referrers excluding frames and functions
            referrers = [
                ref
                for ref in gc.get_referrers(obj)
                if not isinstance(ref, (types.FrameType, types.FunctionType))
            ]

            for ref in referrers:
                ref_id = id(ref)

                # Skip if we've seen this object already
                if ref_id in visited:
                    continue

                visited.add(ref_id)

                # Print current path
                ref_type = type(ref).__name__
                current_path = path + [(ref_type, ref_id)]

                # Print the path
                # path_str = " -> ".join([f"{t} (id:{i})" for t, i in current_path])
                print(f"{' ' * depth}• {ref_type} references {type(obj).__name__}")

                # If it's a container, try to find the specific reference
                if isinstance(ref, dict):
                    for k, v in ref.items():
                        if v is obj:
                            print(f"{' ' * (depth+2)}(via dict key: {k})")
                elif isinstance(ref, (list, tuple)):
                    try:
                        idx = ref.index(obj)
                        print(
                            f"{' ' * (depth+2)}(via {type(ref).__name__} index: {idx})"
                        )
                    except (ValueError, TypeError):
                        print(f"{' ' * (depth+2)}(as part of a larger structure)")

                # Look for owners of this container
                if isinstance(ref, dict):
                    owners = [
                        o
                        for o in gc.get_referrers(ref)
                        if hasattr(o, "__dict__") and o.__dict__ is ref
                    ]
                    if owners:
                        owner = owners[0]
                        print(
                            f"{' ' * (depth+2)}(dict belongs to: {type(owner).__name__} id:{id(owner)})"
                        )

                # Continue recursion with increased depth
                find_path_to_referrers(ref, current_path, depth + 1, visited)

        # Start the recursive search
        find_path_to_referrers(self.target_obj)
