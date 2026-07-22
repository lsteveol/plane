from pathlib import Path

from .block import RegisterBlock
from .system import RegisterSystem

_ACCESS_TO_UVM = {
    "RW": ("RW", 0),
    "RO": ("RO", 1),
    "WO": ("WO", 0),
    "W1C": ("W1C", 1),
    "W1S": ("W1S", 1),
    "RC": ("RC", 1),
    "RCW": ("WRC", 1),
}


def generate_uvm_ral(node, output_path: str | None = None) -> str:
    """Generate UVM RAL SystemVerilog model for a block or system."""
    emitted_blocks = set()
    emitted_systems = set()
    lines = []

    _collect_and_emit(node, emitted_blocks, emitted_systems, lines)

    result = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(result)

    return result


def _collect_and_emit(node, emitted_blocks, emitted_systems, lines):
    """Recursively collect unique definitions and emit classes in dependency order."""
    if isinstance(node, RegisterBlock):
        if node.name not in emitted_blocks:
            emitted_blocks.add(node.name)
            for reg in node.registers:
                lines.append(_gen_register_class(reg, node.name, node.width))
                lines.append("")
            lines.append(_gen_block_class(node))
            lines.append("")
    elif isinstance(node, RegisterSystem):
        for child in node.children:
            _collect_and_emit(child.obj, emitted_blocks, emitted_systems, lines)
        if node.name not in emitted_systems:
            emitted_systems.add(node.name)
            lines.append(_gen_system_class(node))
            lines.append("")


def _gen_register_class(reg, block_name: str, width: int) -> str:
    """Generate a uvm_reg class for a register."""
    class_name = f"{block_name}_{reg.name}"

    field_decls = []
    field_builds = []
    for fld in reg.fields:
        access, volatile = _ACCESS_TO_UVM.get(fld.uvm_access, ("RW", 0))
        reset_str = f"{fld.width}'h{fld.reset:X}" if fld.width > 1 else f"1'h{fld.reset:X}"

        field_decls.append(f"  rand uvm_reg_field {fld.name};")
        field_builds.append(f"""    {fld.name} = uvm_reg_field::type_id::create("{fld.name}");
    {fld.name}.configure(this, {fld.width}, {fld.offset}, "{access}", {volatile}, {reset_str}, 1, 1, 0);""")

    return f"""class {class_name} extends uvm_reg;
{chr(10).join(field_decls)}

  function new(string name = "{class_name}");
    super.new(name, {width}, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
{chr(10).join(field_builds)}
  endfunction

  `uvm_object_utils({class_name})
endclass"""


def _gen_block_class(block) -> str:
    """Generate a uvm_reg_block class for a block."""
    n_bytes = block.width // 8

    reg_decls = []
    reg_builds = []
    for reg in block.registers:
        class_name = f"{block.name}_{reg.name}"
        reg_decls.append(f"  rand {class_name} {reg.name};")
        reg_builds.append(f"""    {reg.name} = {class_name}::type_id::create("{reg.name}");
    {reg.name}.configure(this, null, "");
    {reg.name}.build();
    default_map.add_reg({reg.name}, 'h{reg.offset:X});""")

    return f"""class {block.name} extends uvm_reg_block;
{chr(10).join(reg_decls)}

  function new(string name = "{block.name}");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map("default_map", 0, {n_bytes}, UVM_LITTLE_ENDIAN, 0);
{chr(10).join(reg_builds)}
  endfunction

  `uvm_object_utils({block.name})
endclass"""


def _gen_system_class(system) -> str:
    """Generate a uvm_reg_block class for a system."""
    n_bytes = _get_max_n_bytes(system)

    child_decls = []
    child_builds = []
    for child in system.children:
        child_class = child.obj.name
        child_decls.append(f"  rand {child_class} {child.name};")
        child_builds.append(f"""    {child.name} = {child_class}::type_id::create("{child.name}");
    {child.name}.configure(this, "{child.name}");
    {child.name}.build();
    default_map.add_submap({child.name}.default_map, 'h{child.offset:X});""")

    return f"""class {system.name} extends uvm_reg_block;
{chr(10).join(child_decls)}

  function new(string name = "{system.name}");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map("default_map", 0, {n_bytes}, UVM_LITTLE_ENDIAN, 0);
{chr(10).join(child_builds)}
  endfunction

  `uvm_object_utils({system.name})
endclass"""


def _get_max_n_bytes(node) -> int:
    """Get the maximum n_bytes from all blocks in the tree."""
    if isinstance(node, RegisterBlock):
        return node.width // 8
    elif isinstance(node, RegisterSystem):
        if not node.children:
            return 4
        return max(_get_max_n_bytes(child.obj) for child in node.children)
    return 4
