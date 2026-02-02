#!/usr/bin/env python3
"""
Generate HTML documentation from MCP server inspection JSON.

This script reads the output of `fastmcp inspect` and generates
a beautiful HTML documentation file with CSS styling.
"""

import json
import sys
from pathlib import Path


def generate_html_documentation(json_file: Path, output_file: Path) -> None:
    """Generate HTML documentation from JSON report."""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    server_info = data.get('server', {})
    tools = data.get('tools', [])
    prompts = data.get('prompts', [])
    resources = data.get('resources', [])
    templates = data.get('templates', [])
    
    # Group tools
    read_only_tools = []
    write_tools = []
    
    for tool in tools:
        annotations = tool.get('annotations')
        if annotations and annotations.get('readOnlyHint'):
            read_only_tools.append(tool)
        else:
            write_tools.append(tool)
    
    # Build HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{server_info.get('name', 'MCP Server')} Documentation</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem 1rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .header .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}
        
        .content {{
            padding: 2rem;
        }}
        
        .section {{
            margin-bottom: 2.5rem;
        }}
        
        .section-title {{
            font-size: 1.8rem;
            color: #2d3748;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #667eea;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .summary-card {{
            background: #f7fafc;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e2e8f0;
        }}
        
        .summary-card .number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #667eea;
        }}
        
        .summary-card .label {{
            color: #4a5568;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }}
        
        .tool-card {{
            background: #f7fafc;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid #667eea;
            transition: all 0.3s ease;
        }}
        
        .tool-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}
        
        .tool-card.write {{
            border-left-color: #ed8936;
        }}
        
        .tool-name {{
            font-size: 1.3rem;
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 0.75rem;
        }}
        
        .tool-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 0.75rem;
            text-transform: uppercase;
        }}
        
        .badge-read {{
            background: #48bb78;
            color: white;
        }}
        
        .badge-write {{
            background: #ed8936;
            color: white;
        }}
        
        .tool-description {{
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 1rem;
        }}
        
        .params-section {{
            margin-top: 1rem;
        }}
        
        .params-title {{
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 0.5rem;
        }}
        
        .params-list {{
            list-style: none;
            padding-left: 0;
        }}
        
        .param-item {{
            background: white;
            padding: 0.75rem;
            border-radius: 4px;
            margin-bottom: 0.5rem;
            border-left: 3px solid #cbd5e0;
        }}
        
        .param-name {{
            font-family: 'Monaco', 'Consolas', Monaco, monospace;
            font-weight: 600;
            color: #667eea;
        }}
        
        .param-meta {{
            color: #718096;
            font-size: 0.85rem;
        }}
        
        .no-params {{
            color: #718096;
            font-style: italic;
        }}
        
        .footer {{
            text-align: center;
            padding: 1.5rem;
            background: #f7fafc;
            color: #718096;
            font-size: 0.9rem;
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1rem;
        }}
        
        .section-count {{
            background: #667eea;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{server_info.get('name', 'MCP Server')}</h1>
            <p class="subtitle">MCP Version {server_info.get('generation', 'N/A')} - Complete API Documentation</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2 class="section-title">Summary</h2>
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="number">{len(tools)}</div>
                        <div class="label">Total Tools</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{len(read_only_tools)}</div>
                        <div class="label">Read-Only</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{len(write_tools)}</div>
                        <div class="label">Write</div>
                    </div>
                    <div class="summary-card">
                        <div class="number">{len(prompts)}</div>
                        <div class="label">Prompts</div>
                    </div>
                </div>
            </div>
"""
    
    # Read-only tools section
    html += f"""
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Read-Only Tools</h2>
                    <span class="section-count">{len(read_only_tools)} tools</span>
                </div>
"""
    
    for tool in read_only_tools:
        name = tool.get('name', 'Unknown')
        desc = tool.get('description', '').strip()
        input_schema = tool.get('input_schema', {})
        props = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        html += f"""
                <div class="tool-card">
                    <div class="tool-name">
                        {name}
                        <span class="tool-badge badge-read">Read</span>
                    </div>
                    <div class="tool-description">
                        {desc.replace(chr(10), '<br>')}
                    </div>
"""
        
        if props:
            html += f"""
                    <div class="params-section">
                        <div class="params-title">Parameters</div>
"""
            for param_name, param_info in props.items():
                is_req = param_name in required
                req_str = '<span style="color: #e53e3e; font-weight: bold;">(required)</span>' if is_req else '<span style="color: #718096;">(optional)</span>'
                param_type = param_info.get('type', 'unknown')
                default = param_info.get('default')
                default_str = f", default: <code>{default}</code>" if default is not None else ""
                
                html += f"""
                        <li class="param-item">
                            <span class="param-name">{param_name}</span>
                            <span class="param-meta"> — {param_type} {req_str}{default_str}</span>
                        </li>
"""
            html += """
                    </div>
"""
        else:
            html += """
                    <div class="params-section">
                        <span class="no-params">No parameters</span>
                    </div>
"""
        
        html += """
                </div>
"""
    
    html += """
            </div>
"""
    
    # Write tools section
    html += f"""
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Write Tools</h2>
                    <span class="section-count">{len(write_tools)} tools</span>
                </div>
"""
    
    for tool in write_tools:
        name = tool.get('name', 'Unknown')
        desc = tool.get('description', '').strip()
        input_schema = tool.get('input_schema', {})
        props = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        html += f"""
                <div class="tool-card write">
                    <div class="tool-name">
                        {name}
                        <span class="tool-badge badge-write">Write</span>
                    </div>
                    <div class="tool-description">
                        {desc.replace(chr(10), '<br>')}
                    </div>
"""
        
        if props:
            html += f"""
                    <div class="params-section">
                        <div class="params-title">Parameters</div>
"""
            for param_name, param_info in props.items():
                is_req = param_name in required
                req_str = '<span style="color: #e53e3e; font-weight: bold;">(required)</span>' if is_req else '<span style="color: #718096;">(optional)</span>'
                param_type = param_info.get('type', 'unknown')
                default = param_info.get('default')
                default_str = f", default: <code>{default}</code>" if default is not None else ""
                
                html += f"""
                        <li class="param-item">
                            <span class="param-name">{param_name}</span>
                            <span class="param-meta"> — {param_type} {req_str}{default_str}</span>
                        </li>
"""
            html += """
                    </div>
"""
        else:
            html += """
                    <div class="params-section">
                        <span class="no-params">No parameters</span>
                    </div>
"""
        
        html += """
                </div>
"""
    
    html += """
            </div>
"""
    
    # Prompts section
    if prompts:
        html += f"""
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Prompts</h2>
                    <span class="section-count">{len(prompts)} prompts</span>
                </div>
"""
        
        for prompt in prompts:
            name = prompt.get('name', 'Unknown')
            desc = prompt.get('description', '').strip()
            
            html += f"""
                <div class="tool-card">
                    <div class="tool-name">{name}</div>
                    <div class="tool-description">
                        {desc.replace(chr(10), '<br>')}
                    </div>
                </div>
"""
        
        html += """
            </div>
"""
    
    # Templates section
    if templates:
        html += f"""
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">Templates</h2>
                    <span class="section-count">{len(templates)} templates</span>
                </div>
"""
        
        for template in templates:
            name = template.get('name', 'Unknown')
            uri = template.get('uri_template', '')
            desc = template.get('description', '').strip()
            
            html += f"""
                <div class="tool-card">
                    <div class="tool-name">{name}</div>
                    <div class="tool-description">
                        <strong>URI Template:</strong> <code>{uri}</code><br><br>
                        {desc.replace(chr(10), '<br>')}
                    </div>
                </div>
"""
        
        html += """
            </div>
"""
    
    html += """
        </div>
        
        <div class="footer">
            <p>Generated by fastmcp inspect • Last updated: """ + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Write output
    output_file.write_text(html, encoding='utf-8')
    print(f"✓ HTML documentation generated: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_mcp_html.py <json_file> [output_file]")
        print("\nExample:")
        print("  python generate_mcp_html.py mcp_tools_report.html MCP_TOOLS.html")
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    
    if not json_file.exists():
        print(f"Error: JSON file not found: {json_file}")
        sys.exit(1)
    
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("MCP_TOOLS.html")
    
    generate_html_documentation(json_file, output_file)
