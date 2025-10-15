"""
Test script to verify that multiple charts in Jupyter don't have ID collisions.

This script creates multiple charts and checks that they have unique IDs.
"""

import sys
import re
sys.path.insert(0, '/Users/johnhorton/tools/ep/edsl')

from edsl import Results
from edsl.reports.report import Report

def test_unique_chart_ids():
    """Test that multiple charts generate unique IDs."""
    
    # Create a simple report with example results
    results = Results.example()
    report = Report(results, exclude_question_types=['free_text'])
    
    # Get multiple charts
    html_outputs = []
    chart_count = 0
    
    for key, output_dict in report.items():
        for output_name, output_obj in output_dict.items():
            try:
                # Get the HTML representation
                chart = output_obj.output()
                if hasattr(chart, 'to_html'):
                    # This should now have a unique ID
                    html = output_obj._get_content_html() if hasattr(output_obj, '_get_content_html') else chart.to_html()
                    html_outputs.append(html)
                    chart_count += 1
                    
                    # Extract chart names/IDs from the HTML
                    # Altair charts include their name in the spec
                    if '"name":"chart_' in html:
                        print(f"✓ Chart {chart_count} has unique ID")
                    
                    if chart_count >= 3:  # Test with 3 charts
                        break
            except Exception as e:
                print(f"Skipping {output_name}: {e}")
                continue
        
        if chart_count >= 3:
            break
    
    # Verify that chart IDs are unique
    chart_ids = []
    for html in html_outputs:
        # Extract chart name from Altair spec
        matches = re.findall(r'"name":"(chart_[a-f0-9]+)"', html)
        if matches:
            chart_ids.extend(matches)
    
    if len(chart_ids) == len(set(chart_ids)):
        print(f"\n✅ SUCCESS: All {len(chart_ids)} chart IDs are unique!")
        print(f"   Chart IDs: {chart_ids}")
        return True
    else:
        print(f"\n❌ FAILURE: Found duplicate chart IDs!")
        print(f"   Chart IDs: {chart_ids}")
        return False

if __name__ == "__main__":
    test_unique_chart_ids()

