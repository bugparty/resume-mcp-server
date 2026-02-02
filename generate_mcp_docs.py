#!/usr/bin/env python3
"""
Generate Markdown documentation from MCP server inspection JSON.

This script reads the output of `fastmcp inspect` and generates
a beautiful Markdown documentation file.
"""

import json
import sys
from pathlib import Path


def generate_markdown_documentation(json_file: Path, output_file: Path) -> None:
    """Generate Markdown documentation from JSON report."""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    server_info = data.get('server', {})
    tools = data.get('tools', [])
    prompts = data.get('prompts', [])
    resources = data.get('resources', [])
    templates = data.get('templates', [])
    
    # Build markdown content
    lines = []
    
    # Title
    lines.append(f"# {server_info.get('name', 'MCP Server')} Documentation")
    lines.append("")
    
    # Server info
    lines.append("## Server Information")
    lines.append("")
    lines.append(f"- **Name**: {server_info.get('name', 'N/A')}")
    lines.append(f"- **MCP Version**: {server_info.get('generation', 'N/A')}")
    lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Tools**: {len(tools)}")
    lines.append(f"- **Total Prompts**: {len(prompts)}")
    lines.append(f"- **Total Resources**: {len(resources)}")
    lines.append(f"- **Total Templates**: {len(templates)}")
    lines.append("")
    
    # Tools
    lines.append("## Tools")
    lines.append("")
    
    # Group tools by type (read vs write)
    read_only_tools = []
    write_tools = []
    
    for tool in tools:
        annotations = tool.get('annotations')
        if annotations and annotations.get('readOnlyHint'):
            read_only_tools.append(tool)
        else:
            write_tools.append(tool)
    
    # Read-only tools
    lines.append("### Read-Only Tools")
    lines.append("")
    lines.append(f"**{len(read_only_tools)} tools**")
    lines.append("")
    
    for tool in read_only_tools:
        lines.append(f"#### `{tool['name']}`")
        lines.append("")
        
        # Description
        desc = tool.get('description', '').strip()
        lines.append(f"**Description**: {desc}")
        lines.append("")
        
        # Parameters
        input_schema = tool.get('input_schema', {})
        props = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        if props:
            lines.append("**Parameters**:")
            lines.append("")
            for param_name, param_info in props.items():
                is_req = param_name in required
                req_str = "*(required)*" if is_req else "*(optional)*"
                param_type = param_info.get('type', 'unknown')
                default = param_info.get('default')
                default_str = f", default: `{default}`" if default is not None else ""
                
                lines.append(f"- `{param_name}` ({param_type}) {req_str}{default_str}")
            lines.append("")
        else:
            lines.append("**Parameters**: None")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Write tools
    lines.append("### Write Tools")
    lines.append("")
    lines.append(f"**{len(write_tools)} tools**")
    lines.append("")
    
    for tool in write_tools:
        lines.append(f"#### `{tool['name']}`")
        lines.append("")
        
        # Description
        desc = tool.get('description', '').strip()
        lines.append(f"**Description**: {desc}")
        lines.append("")
        
        # Parameters
        input_schema = tool.get('input_schema', {})
        props = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        if props:
            lines.append("**Parameters**:")
            lines.append("")
            for param_name, param_info in props.items():
                is_req = param_name in required
                req_str = "*(required)*" if is_req else "*(optional)*"
                param_type = param_info.get('type', 'unknown')
                default = param_info.get('default')
                default_str = f", default: `{default}`" if default is not None else ""
                
                lines.append(f"- `{param_name}` ({param_type}) {req_str}{default_str}")
            lines.append("")
        else:
            lines.append("**Parameters**: None")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # Prompts
    if prompts:
        lines.append("## Prompts")
        lines.append("")
        
        for prompt in prompts:
            lines.append(f"### `{prompt['name']}`")
            lines.append("")
            desc = prompt.get('description', '').strip()
            lines.append(f"**Description**: {desc}")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # Resources
    if resources:
        lines.append("## Resources")
        lines.append("")
        
        for resource in resources:
            lines.append(f"### `{resource['name']}`")
            lines.append("")
            desc = resource.get('description', '').strip()
            lines.append(f"**Description**: {desc}")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # Templates
    if templates:
        lines.append("## Templates")
        lines.append("")
        
        for template in templates:
            lines.append(f"### `{template['name']}`")
            lines.append("")
            uri = template.get('uri_template', '')
            lines.append(f"**URI Template**: `{uri}`")
            lines.append("")
            desc = template.get('description', '').strip()
            lines.append(f"**Description**: {desc}")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by fastmcp inspect*")
    
    # Write output
    content = "\n".join(lines)
    output_file.write_text(content, encoding='utf-8')
    print(f"✓ Documentation generated: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_mcp_docs.py <json_file> [output_file]")
        print("\nExample:")
        print("  python generate_mcp_docs.py mcp_tools_report.json MCP_TOOLS.md")
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    
    if not json_file.exists():
        print(f"Error: JSON file not found: {json_file}")
        sys.exit(1)
    
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("MCP_TOOLS.md")
    
    generate_markdown_documentation(json_file, output_file)
