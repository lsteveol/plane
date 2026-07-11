import json
from pathlib import Path

from .block import RegisterBlock
from .system import RegisterSystem


ACCESS_TYPE_COLORS = {
    "RW": 7,
    "RO": 3,
    "WO": 2,
    "W1C": 5,
    "W1S": 4,
    "RC": 6,
    "RCW": 4,
}


def _wavedrom_bitfield(reg, block_width: int) -> dict:
    """Generate WaveDrom bitfield JSON for a register's bitfield layout.
    
    Returns a dict that can be serialized to JSON for WaveDrom rendering.
    The trim option automatically truncates long field names with "..." when
    they don't fit in the available space.
    """
    sorted_fields = sorted(reg.fields, key=lambda f: f.offset)
    
    bits = []
    current_bit = 0
    
    for field in sorted_fields:
        if field.offset > current_bit:
            gap_bits = field.offset - current_bit
            bits.append({"bits": gap_bits, "name": "", "type": ""})
        
        bits.append({
            "bits": field.width,
            "name": field.name,
            "type": ACCESS_TYPE_COLORS.get(field.access, 0),
            "attr": field.access,
        })
        current_bit = field.offset + field.width
    
    if current_bit < block_width:
        gap_bits = block_width - current_bit
        bits.append({"bits": gap_bits, "name": "", "type": ""})
    
    return {
        "reg": bits,
        "config": {"hspace": 1000, "trim": 5, "fontsize": 10}
    }


def _field_table_html(reg) -> str:
    """Generate HTML <table> for register fields."""
    if not reg.fields:
        return "<p>No fields defined.</p>"
    
    rows = []
    for field in reg.fields:
        rows.append(f'''        <tr>
            <td>{field.name}</td>
            <td>{field.access}</td>
            <td>{field.offset}</td>
            <td>{field.width}</td>
            <td>{field.reset}</td>
            <td>{field.description}</td>
        </tr>''')
    
    html = f'''<table class="field-table">
    <thead>
        <tr>
            <th>Field</th>
            <th>Access</th>
            <th>Offset</th>
            <th>Width</th>
            <th>Reset</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
</table>'''
    
    return html


def _register_section_html(reg, block_width: int) -> str:
    """Generate HTML for a register section with bitfield diagram."""
    
    # Build description
    description = f'\n    <p>{reg.description}</p>' if reg.description else ''
    
    # Build bitfield diagram
    bitfield_data = _wavedrom_bitfield(reg, block_width)
    bitfield_json = json.dumps(bitfield_data, indent=2)
    
    # Build field table rows
    field_rows = []
    for field in reg.fields:
        field_rows.append(f'''        <tr>
            <td>{field.name}</td>
            <td>{field.offset}:{field.offset + field.width - 1}</td>
            <td>{field.access}</td>
            <td>{field.reset}</td>
            <td>{field.description}</td>
        </tr>''')
    
    html = f'''<div class="register-section">
    <h3>{reg.name}</h3>{description}
    <div class="bitfield">
        <script type="WaveDrom">
{bitfield_json}
        </script>
    </div>
    <table class="field-table">
        <thead>
            <tr>
                <th>Field</th>
                <th>Bits</th>
                <th>Type</th>
                <th>Reset</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
{chr(10).join(field_rows)}
        </tbody>
    </table>
</div>'''
    
    return html


def _block_page_html(block, qualified_name: str, referenced_by: list, sidebar_html: str) -> str:
    """Full HTML page for a RegisterBlock definition."""
    
    # Build register sections
    register_sections = []
    if block.registers:
        for reg in block.registers:
            register_sections.append(_register_section_html(reg, block.width))
    else:
        register_sections.append('<p>No registers defined.</p>')
    
    # Build referenced by section
    referenced_by_section = ''
    if referenced_by:
        referenced_by_section = f'''
    <div class="referenced-by">
        <strong>Referenced by:</strong> {', '.join(referenced_by)}
    </div>'''
    
    # Build description
    description = f'\n    <p>{block.description}</p>' if block.description else ''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{qualified_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; display: flex; background: #1a1a1a; color: #e0e0e0; }}
        .sidebar {{ width: 250px; min-width: 150px; max-width: 600px; height: 100vh; position: fixed; overflow-y: auto; background: #2d2d2d; padding: 20px; border-right: 1px solid #444; }}
        .sidebar-resize-handle {{ width: 5px; height: 100vh; position: fixed; left: 250px; top: 0; cursor: col-resize; background: #444; z-index: 100; }}
        .sidebar-resize-handle:hover {{ background: #007bff; }}
        .main {{ margin-left: 280px; padding: 40px; max-width: 1200px; }}
        h1 {{ color: #f0f0f0; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h3 {{ color: #e0e0e0; margin-top: 30px; }}
        .offset {{ color: #999; font-size: 0.9em; font-weight: normal; }}
        .register-description {{ color: #aaa; font-style: italic; }}
        .register-section {{ margin-bottom: 40px; }}
        .register-section svg {{ font-family: "DejaVu Sans Mono", "Liberation Mono", "Courier New", monospace; }}
        
        /* Dark mode overrides for wavedrom bitfield colors */
        .register-section svg rect[style*="fill:#ff0000"] {{ fill: #ff6b6b !important; fill-opacity: 0.3 !important; }}
        .register-section svg rect[style*="fill:#aaff00"] {{ fill: #a3e635 !important; fill-opacity: 0.3 !important; }}
        .register-section svg rect[style*="fill:#00ffd5"] {{ fill: #22d3ee !important; fill-opacity: 0.3 !important; }}
        .register-section svg rect[style*="fill:#ffbf00"] {{ fill: #fbbf24 !important; fill-opacity: 0.3 !important; }}
        .register-section svg rect[style*="fill:#00ff19"] {{ fill: #4ade80 !important; fill-opacity: 0.3 !important; }}
        .register-section svg rect[style*="fill:#006aff"] {{ fill: #60a5fa !important; fill-opacity: 0.3 !important; }}
        
        /* Text and box colors */
        .register-section svg text {{ fill: #e0e0e0 !important; }}
        .register-section svg line {{ stroke: #888 !important; }}
        .register-section svg rect[stroke="black"] {{ stroke: #888 !important; }}
        
        .field-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        .field-table th, .field-table td {{ border: 1px solid #555; padding: 8px; text-align: left; }}
        .field-table th {{ background: #3a3a3a; font-weight: 600; color: #f0f0f0; }}
        .field-table td {{ background: #2d2d2d; }}
        .field-table td:nth-child(1), .field-table td:nth-child(3), .field-table td:nth-child(4), .field-table td:nth-child(5) {{ font-family: monospace; }}
        .referenced-by {{ background: #3a3a2d; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
        .referenced-by strong {{ color: #ffd966; }}
        details {{ margin: 5px 0; }}
        summary {{ cursor: pointer; padding: 5px; color: #e0e0e0; }}
        summary:hover {{ background: #3a3a3a; }}
        .tree-node {{ margin-left: 20px; }}
        a {{ color: #4a9eff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
    <script src="https://wavedrom.com/wavedrom.min.js"></script>
    <script src="https://wavedrom.com/skins/default.js"></script>
</head>
<body>
    <div class="sidebar">
        {sidebar_html}
    </div>
    <div class="sidebar-resize-handle"></div>
    <div class="main">
        <h1>{qualified_name}</h1>{description}{referenced_by_section}
        {''.join(register_sections)}
    </div>
    <script>
        window.addEventListener("load", () => {{ WaveDrom.ProcessAll(); }});
        
        // Sidebar resize functionality
        const resizeHandle = document.querySelector('.sidebar-resize-handle');
        const sidebar = document.querySelector('.sidebar');
        const main = document.querySelector('.main');
        let isResizing = false;
        
        resizeHandle.addEventListener('mousedown', (e) => {{
            isResizing = true;
            e.preventDefault();
        }});
        
        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;
            const newWidth = e.clientX;
            if (newWidth >= 150 && newWidth <= 600) {{
                sidebar.style.width = newWidth + 'px';
                resizeHandle.style.left = newWidth + 'px';
                main.style.marginLeft = (newWidth + 30) + 'px';
            }}
        }});
        
        document.addEventListener('mouseup', () => {{
            isResizing = false;
        }});
    </script>
</body>
</html>'''
    
    return html


def _system_page_html(system, qualified_name: str, referenced_by: list, sidebar_html: str, base_path: str = "") -> str:
    """Full HTML page for a RegisterSystem definition."""
    
    # Build referenced by section
    referenced_by_section = ''
    if referenced_by:
        referenced_by_section = f'''
    <div class="referenced-by">
        <strong>Referenced by:</strong> {', '.join(referenced_by)}
    </div>'''
    
    # Build description
    description = f'\n    <p>{system.description}</p>' if system.description else ''
    
    # Build address map table
    if system.children:
        address_rows = []
        for child in system.children:
            # Create link based on child kind
            if child.kind == 'block':
                link = f'{base_path}blocks/{child.obj.name}.html'
            else:  # system
                link = f'{base_path}systems/{child.obj.name}.html'
            
            address_rows.append(f'''        <tr>
            <td><a href="{link}">{child.name}</a></td>
            <td>{child.kind}</td>
            <td>0x{child.offset:X} - 0x{child.offset + child.address_space - 1:X}</td>
            <td>{child.description}</td>
        </tr>''')
        
        address_map = f'''
    <h2>Address Map</h2>
    <table class="address-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Kind</th>
                <th>Range</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
{chr(10).join(address_rows)}
        </tbody>
    </table>'''
    else:
        address_map = '\n    <p>No children defined.</p>'
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{qualified_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; display: flex; background: #1a1a1a; color: #e0e0e0; }}
        .sidebar {{ width: 250px; min-width: 150px; max-width: 600px; height: 100vh; position: fixed; overflow-y: auto; background: #2d2d2d; padding: 20px; border-right: 1px solid #444; }}
        .sidebar-resize-handle {{ width: 5px; height: 100vh; position: fixed; left: 250px; top: 0; cursor: col-resize; background: #444; z-index: 100; }}
        .sidebar-resize-handle:hover {{ background: #007bff; }}
        .main {{ margin-left: 280px; padding: 40px; max-width: 1200px; }}
        h1 {{ color: #f0f0f0; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .address-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        .address-table th, .address-table td {{ border: 1px solid #555; padding: 8px; text-align: left; }}
        .address-table th {{ background: #3a3a3a; font-weight: 600; color: #f0f0f0; }}
        .address-table td {{ background: #2d2d2d; }}
        .address-table td:nth-child(3) {{ font-family: monospace; }}
        .referenced-by {{ background: #3a3a2d; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
        .referenced-by strong {{ color: #ffd966; }}
        details {{ margin: 5px 0; }}
        summary {{ cursor: pointer; padding: 5px; color: #e0e0e0; }}
        summary:hover {{ background: #3a3a3a; }}
        .tree-node {{ margin-left: 20px; }}
        a {{ color: #4a9eff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="sidebar">
        {sidebar_html}
    </div>
    <div class="sidebar-resize-handle"></div>
    <div class="main">
        <h1>{qualified_name}</h1>{description}{referenced_by_section}{address_map}
    </div>
    <script>
        // Sidebar resize functionality
        const resizeHandle = document.querySelector('.sidebar-resize-handle');
        const sidebar = document.querySelector('.sidebar');
        const main = document.querySelector('.main');
        let isResizing = false;
        
        resizeHandle.addEventListener('mousedown', (e) => {{
            isResizing = true;
            e.preventDefault();
        }});
        
        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;
            const newWidth = e.clientX;
            if (newWidth >= 150 && newWidth <= 600) {{
                sidebar.style.width = newWidth + 'px';
                resizeHandle.style.left = newWidth + 'px';
                main.style.marginLeft = (newWidth + 30) + 'px';
            }}
        }});
        
        document.addEventListener('mouseup', () => {{
            isResizing = false;
        }});
    </script>
</body>
</html>'''
    
    return html


def _sidebar_html(root_system, base_path: str = "") -> str:
    """Collapsible instance tree using <details> elements.
    
    Args:
        root_system: The root system or block to generate the tree for
        base_path: Relative path from current page to root (e.g., "../" for pages in subdirs)
    """
    def build_tree(node, instance_name, path, indent=0):
        indent_str = '    ' * indent
        if isinstance(node, RegisterSystem):
            # System node
            node_path = f"{path}.{instance_name}" if path else instance_name
            children_html = []
            for child in node.children:
                child_path = f"{node_path}.{child.name}"
                children_html.append(build_tree(child.obj, child.name, child_path, indent + 1))
            
            return f'''{indent_str}<details open>
{indent_str}    <summary><a href="{base_path}systems/{node.name}.html">{instance_name}</a></summary>
{indent_str}    <div class="tree-node">
{chr(10).join(children_html)}
{indent_str}    </div>
{indent_str}</details>'''
        elif isinstance(node, RegisterBlock):
            # Block node
            return f'{indent_str}<div><a href="{base_path}blocks/{node.name}.html">{instance_name}</a></div>'
        return ''
    
    return build_tree(root_system, root_system.name, "")


def _search_index(root_system) -> list:
    """Build search index: list of {path, url, kind, description}."""
    index = []
    
    def walk_system(system, path):
        # Add system entry
        system_path = f"{path}.{system.name}" if path else system.name
        index.append({
            "path": system_path,
            "url": f"systems/{system.name}.html",
            "kind": "system",
            "description": system.description,
        })
        
        # Walk children
        for child in system.children:
            child_path = f"{system_path}.{child.name}"
            if isinstance(child.obj, RegisterSystem):
                walk_system(child.obj, child_path)
            elif isinstance(child.obj, RegisterBlock):
                walk_block(child.obj, child_path)
    
    def walk_block(block, path):
        # Add block entry
        block_path = f"{path}.{block.name}" if path else block.name
        index.append({
            "path": block_path,
            "url": f"blocks/{block.name}.html",
            "kind": "block",
            "description": block.description,
        })
        
        # Add register entries
        for reg in block.registers:
            reg_path = f"{block_path}.{reg.name}"
            index.append({
                "path": reg_path,
                "url": f"blocks/{block.name}.html#{reg.name}",
                "kind": "register",
                "description": reg.description,
            })
            
            # Add field entries
            for field in reg.fields:
                field_path = f"{reg_path}.{field.name}"
                index.append({
                    "path": field_path,
                    "url": f"blocks/{block.name}.html#{reg.name}",
                    "kind": "field",
                    "description": field.description,
                })
    
    walk_system(root_system, "")
    return index


def _index_page_html(root_system, sidebar_html: str) -> str:
    """Root index.html: title, sidebar, list of top-level children."""
    
    # Build description
    description = f'\n    <p>{root_system.description}</p>' if root_system.description else ''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{root_system.name} - Documentation</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 0; display: flex; background: #1a1a1a; color: #e0e0e0; }}
        .sidebar {{ width: 250px; min-width: 150px; max-width: 600px; height: 100vh; position: fixed; overflow-y: auto; background: #2d2d2d; padding: 20px; border-right: 1px solid #444; }}
        .sidebar-resize-handle {{ width: 5px; height: 100vh; position: fixed; left: 250px; top: 0; cursor: col-resize; background: #444; z-index: 100; }}
        .sidebar-resize-handle:hover {{ background: #007bff; }}
        .main {{ margin-left: 280px; padding: 40px; max-width: 1200px; }}
        h1 {{ color: #f0f0f0; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        details {{ margin: 5px 0; }}
        summary {{ cursor: pointer; padding: 5px; color: #e0e0e0; }}
        summary:hover {{ background: #3a3a3a; }}
        .tree-node {{ margin-left: 20px; }}
        a {{ color: #4a9eff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="sidebar">
        {sidebar_html}
    </div>
    <div class="sidebar-resize-handle"></div>
    <div class="main">
        <h1>{root_system.name}</h1>{description}
    </div>
    <script>
        // Sidebar resize functionality
        const resizeHandle = document.querySelector('.sidebar-resize-handle');
        const sidebar = document.querySelector('.sidebar');
        const main = document.querySelector('.main');
        let isResizing = false;
        
        resizeHandle.addEventListener('mousedown', (e) => {{
            isResizing = true;
            e.preventDefault();
        }});
        
        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;
            const newWidth = e.clientX;
            if (newWidth >= 150 && newWidth <= 600) {{
                sidebar.style.width = newWidth + 'px';
                resizeHandle.style.left = newWidth + 'px';
                main.style.marginLeft = (newWidth + 30) + 'px';
            }}
        }});
        
        document.addEventListener('mouseup', () => {{
            isResizing = false;
        }});
    </script>
</body>
</html>'''
    
    return html


def generate_html(node, output_dir):
    """Entry point: accepts RegisterBlock or RegisterSystem."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (output_dir / "blocks").mkdir(exist_ok=True)
    (output_dir / "systems").mkdir(exist_ok=True)
    (output_dir / "_static").mkdir(exist_ok=True)
    
    # Build referenced_by map
    referenced_by_map = {}
    
    def build_referenced_by(system, path):
        system_path = f"{path}.{system.name}" if path else system.name
        referenced_by_map.setdefault(system.name, []).append(system_path)
        
        for child in system.children:
            child_path = f"{system_path}.{child.name}"
            if isinstance(child.obj, RegisterSystem):
                build_referenced_by(child.obj, child_path)
            elif isinstance(child.obj, RegisterBlock):
                referenced_by_map.setdefault(child.obj.name, []).append(child_path)
    
    if isinstance(node, RegisterSystem):
        build_referenced_by(node, "")
    elif isinstance(node, RegisterBlock):
        referenced_by_map[node.name] = [node.name]
    
    # Generate sidebars with correct relative paths for different page locations
    sidebar_root = _sidebar_html(node, base_path="") if isinstance(node, RegisterSystem) else ""
    sidebar_subdir = _sidebar_html(node, base_path="../") if isinstance(node, RegisterSystem) else ""
    
    # Generate pages
    def generate_system(system):
        system_name = system.name
        qualified_name = system_name  # For now, just use the name
        referenced_by = referenced_by_map.get(system_name, [])
        
        # Generate system page (in systems/ subdir)
        page_html = _system_page_html(system, qualified_name, referenced_by, sidebar_subdir, "../")
        (output_dir / "systems" / f"{system_name}.html").write_text(page_html)
        
        # Generate child pages
        for child in system.children:
            if isinstance(child.obj, RegisterSystem):
                generate_system(child.obj)
            elif isinstance(child.obj, RegisterBlock):
                generate_block(child.obj)
    
    def generate_block(block):
        block_name = block.name
        qualified_name = block_name
        referenced_by = referenced_by_map.get(block_name, [])
        
        # Generate block page (in blocks/ subdir)
        page_html = _block_page_html(block, qualified_name, referenced_by, sidebar_subdir)
        (output_dir / "blocks" / f"{block_name}.html").write_text(page_html)
    
    if isinstance(node, RegisterSystem):
        # Generate index page (in root)
        index_html = _index_page_html(node, sidebar_root)
        (output_dir / "index.html").write_text(index_html)
        
        # Generate search index
        search_index = _search_index(node)
        (output_dir / "_static" / "search.json").write_text(json.dumps(search_index, indent=2))
        
        # Generate all pages
        generate_system(node)
    elif isinstance(node, RegisterBlock):
        # Single block - just generate block page
        generate_block(node)
