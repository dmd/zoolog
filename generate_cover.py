#!/usr/bin/env -S uv run --python-preference only-system
# /// script
# dependencies = ["weasyprint"]
# ///

import sys
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


def generate_cover(title, subtitle, output_path):
    """Generate a PDF cover with proper centering."""

    # HTML template with CSS
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: 8in 10in;
                margin: 0;
            }}
            
            body {{
                margin: 0;
                padding: 0;
                width: 8in;
                height: 10in;
                font-family: Georgia, serif;
                display: flex;
                justify-content: center;
                align-items: center;
                text-align: center;
            }}
            
            .content {{
                text-align: center;
            }}
            
            .title {{
                font-size: 70pt;
                line-height: 1.2;
                margin: 0;
            }}
            
            .subtitle {{
                font-size: 36pt;
                line-height: 1.2;
                margin: 20pt 0 0 0;
            }}
        </style>
    </head>
    <body>
        <div class="content">
            <div class="title">{title}</div>
            {f'<div class="subtitle">{subtitle}</div>' if subtitle else ''}
        </div>
    </body>
    </html>
    """

    # Generate PDF
    font_config = FontConfiguration()
    html_doc = HTML(string=html_content)
    html_doc.write_pdf(output_path, font_config=font_config)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: generate_cover.py <title> <subtitle> <output_path>")
        print("Use empty string '' for no subtitle")
        sys.exit(1)

    title = sys.argv[1]
    subtitle = sys.argv[2] if sys.argv[2] != "" else None
    output_path = sys.argv[3]

    generate_cover(title, subtitle, output_path)
