from IPython.display import HTML
import difflib

def show_diff(text1, text2, text1_name="Original", text2_name="Modified", split_sentences = True):
    """
    Compact side-by-side diff without wasted space
    """
    if split_sentences:
        text1 = "\n".join(text1.split("."))
        text2 = "\n".join(text2.split("."))
    d = difflib.HtmlDiff()
    # Use make_table instead of make_file for more control
    html_table = d.make_table(text1.splitlines(), text2.splitlines(), 
                              fromdesc=text1_name, todesc=text2_name)
    
    custom_css = """
    <style>
        /* Compact table styling */
        table.diff {
            font-family: monospace;
            font-size: 13px;
            border-collapse: collapse;
            width: auto;  /* Let table size to content */
            margin: 10px 0;
        }
        
        /* Remove excessive padding and width */
        table.diff td {
            padding: 2px 8px;
            text-align: left !important;
            white-space: pre;
            border: none;
        }
        
        /* Make line number columns narrow */
        table.diff td.diff_header {
            width: 30px !important;
            min-width: 30px !important;
            max-width: 30px !important;
            text-align: right !important;
            padding: 2px 4px;
            background-color: #f6f8fa;
            color: #666;
            font-size: 11px;
            border-right: 1px solid #ddd;
        }
        
        /* Content columns - no fixed width */
        table.diff td:not(.diff_header) {
            white-space: pre-wrap;
            word-break: break-word;
            max-width: 600px; /* Reasonable max width */
        }
        
        /* Git-style colors */
        .diff_add { background-color: #e6ffed; }
        .diff_chg { background-color: #fff5dd; }
        .diff_sub { background-color: #ffeef0; }
        
        /* Container with border */
        .diff-wrapper {
            border: 1px solid #ddd;
            border-radius: 3px;
            overflow-x: auto;
            display: inline-block; /* Shrink to content */
        }
    </style>
    <div class="diff-wrapper">
    """
    
    display(HTML(custom_css + html_table + "</div>"))