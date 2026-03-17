#!/usr/bin/env python3
"""Fix test file to use new API"""

with open('tests/test_resume_operations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace old API call with new enum-based API
old_call = 'update_resume_section("resume/summary", updated_markdown)'
new_call = '''update_resume_section(
                version_name="resume", 
                section_id=ResumeSectionId.SUMMARY,
                new_content=updated_markdown
            )'''

if old_call in content:
    content = content.replace(old_call, new_call)
    
    # Add import if not present
    if 'from myagent.mcp_server import ResumeSectionId' not in content:
        # Find the import line (after from myagent.settings...)
        lines = content.split('\n')
        import_inserted = False
        for i, line in enumerate(lines):
            if line.startswith('from myagent.'):
                # Insert ResumeSectionId import after this line
                lines.insert(i, 'from myagent.mcp_server import ResumeSectionId')
                import_inserted = True
                break
        
        if import_inserted:
            content = '\n'.join(lines)
    
    with open('tests/test_resume_operations.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ Updated test file to use new API with ResumeSectionId enum')
