#!/usr/bin/env -S uv run
# /// script
# dependencies = ["weasyprint"]
# ///

import sys
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

def generate_content_pdf(html_file, pdf_file):
    """Generate a content PDF with proper dimensions and margins."""
    
    # Additional CSS for page layout
    additional_css = """
    @page {
        size: 8in 10in;
        margin: 30pt 40pt 30pt 40pt;
    }
    
    body {
        font-family: Georgia, serif;
        font-size: 10pt;
    }
    
    td {
        text-align: justify;
    }
    
    tr {
        page-break-inside: avoid;
        break-inside: avoid;
    }
    """
    
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Generate PDF with additional CSS
    font_config = FontConfiguration()
    html_doc = HTML(string=html_content)
    css = CSS(string=additional_css)
    
    html_doc.write_pdf(pdf_file, stylesheets=[css], font_config=font_config)
    print(f"Generated {pdf_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: generate_content_pdf.py <html_file> <pdf_file>")
        sys.exit(1)
    
    html_file = sys.argv[1]
    pdf_file = sys.argv[2]
    
    generate_content_pdf(html_file, pdf_file)