"""
Verilog/SV emitter for the cutter HDL.

Supports:
- Flat combinational assignments (assign statements)
- Conditional logic via AlwaysComb + When/Switch
- Sequential logic via RegNext (always_ff blocks)
- Module instantiation
"""

from .base import Module, Parameter
from .connect import Builder
from .control import (
    AlwaysCombContext,
    CaseContext,
    DefaultContext,
    ElseWhenContext,
    OtherwiseContext,
    SwitchContext,
    WhenContext,
)
from .ir import build_ir
from .nodes import (
    BinOp,
    Cat,
    Index,
    InoutPort,
    InputPort,
    Literal,
    Mux,
    OutputPort,
    ReductionOp,
    Reg,
    RegNext,
    Replicate,
    SignExtend,
    SIntCast,
    Slice,
    UIntCast,
    UnaryOp,
    Wire,
    ZeroExtend,
)
from .types import EnumVal, PlaneEnum
from . import utils
from .utils import get_node_width, get_width, is_signed


def _emit_comment(text, indent: int) -> list[str]:
    """Emit comment lines at the given indent level. Returns [] if text is None/empty."""
    if not text:
        return []
    prefix = "  " * indent
    lines = []
    for line in text.split("\n"):
        lines.append(f"{prefix}// {line}")
    return lines


def _find_optimizable_regs(mod):
    """Find Regs that can be optimized to drive OutputPorts directly.
    
    A Reg is optimizable if:
    - It has at least one OutputPort load
    - The Reg's _optimize attribute is True (or global config is True)
    """
    optimizable = {}
    
    for reg in mod._graph.nodes:
        if not isinstance(reg, Reg):
            continue
        
        # Check if optimization is enabled for this reg
        if not getattr(reg, '_optimize', True):
            continue
        
        # Check global config
        if not utils.optimize_reg_to_port:
            continue
        
        # Find all OutputPort loads
        output_port_loads = [load for load in reg.loads if isinstance(load, OutputPort)]
        
        # Must have at least one OutputPort load
        if not output_port_loads:
            continue
        
        # Use the first OutputPort as the canonical name
        canonical_port = output_port_loads[0]
        
        # Mark the register with the output port it's optimized to
        reg._optimized_to = canonical_port
        optimizable[reg] = canonical_port
    
    return optimizable

# =============================================================================
# Entry Point
# =============================================================================


def emitVerilog(top: Module, filename: str = None) -> str:
    """
    Emit SV from a module tree.

    1. Elaborate the top module (children elaborated via instance())
    2. Collect all modules
    3. Build IR for each module
    4. Deduplicate by IR structural equality
    5. Emit SV to file or return string

    Enum emission mode is controlled by `enum_mode` in utils.py:
      - "package": typedef enum in a separate package file
      - "localparam": per-module localparam declarations
    """
    # Compute package name with snake_case conversion and prefix
    pkg_base = top._graph.module_name
    if utils.convert_module_names_to_snake_case and not top._is_blackbox:
        pkg_base = utils.to_snake_case(pkg_base)
    if utils.module_prefix:
        pkg_base = f"{utils.module_prefix}_{pkg_base}"
    pkg_name = f"{pkg_base}_pkg"

    # Elaborate top module (children elaborated via instance())
    # Guard against double-elaboration: if emitVerilog(top) is called twice
    # on the same module, the second call would duplicate nodes in the graph.
    if not top._elaborated:
        Builder.push(top)
        top.elaborate()
        Builder.pop()
        top._validate()
        top._elaborated = True

    top._validate_input_ports()

    # Collect all modules
    modules = _collect_modules(top)

    # Build IR for each module
    irs = [build_ir(mod) for mod in modules]

    # Deduplicate by IR structural equality, assign emitted names
    _assign_emitted_names(modules, irs)

    # Collect used enums
    used_enums = _collect_used_enums(modules)

    # Emit (skip duplicate modules that share an emitted_name)
    output = []
    seen_names = set()
    for mod in modules:
        if mod._is_blackbox:
            continue
        ename = mod._graph.emitted_name
        if ename in seen_names:
            continue
        seen_names.add(ename)
        sv = _emit_module(mod, pkg_name, used_enums)
        output.append(sv)

    result = "\n\n".join(output)

    # Prepend package to returned string if using package mode
    from .utils import enum_mode

    pkg_sv = None
    if enum_mode == "package" and used_enums:
        pkg_sv = _emit_package(pkg_name, used_enums)
        result = f"{pkg_sv}\n\n{result}"

    if filename:
        # Write main file without package (Option A)
        with open(filename, "w") as f:
            f.write("\n\n".join(output))
        # Write package file separately
        if pkg_sv:
            import os
            pkg_path = os.path.join(os.path.dirname(filename), f"{pkg_name}.sv")
            with open(pkg_path, "w") as f:
                f.write(pkg_sv)

    return result


# =============================================================================
# Module Collection & Naming
# =============================================================================


def _collect_modules(mod: Module) -> list:
    """Collect all modules from module tree."""
    modules = [mod]
    for child in mod._children:
        modules.extend(_collect_modules(child))
    return modules


def _assign_emitted_names(modules, irs):
    """Assign unique emitted names using IR structural equality.

    Modules with identical IR share the same emitted_name (deduplication).
    Modules with different IR but same module_name get unique suffixes.

    Order of transformations (for non-BlackBox modules):
    1. Snake case conversion (if enabled)
    2. Dedup suffix (_1, _2, etc.)
    3. Module prefix (if set)
    """
    seen = {}
    name_counts = {}

    for mod, ir in zip(modules, irs):
        key = (ir.module_name, ir)
        if key in seen:
            mod._graph.emitted_name = seen[key]
            continue

        # Start with original name
        name = ir.module_name

        # 1. Apply snake_case conversion (before dedup)
        if utils.convert_module_names_to_snake_case and not mod._is_blackbox:
            name = utils.to_snake_case(name)

        # 2. Apply dedup suffix
        count = name_counts.get(name, 0)
        name_counts[name] = count + 1

        if count == 0:
            emitted = name
        else:
            emitted = f"{name}_{count}"

        # 3. Apply module prefix (after dedup)
        if utils.module_prefix and not mod._is_blackbox:
            emitted = f"{utils.module_prefix}_{emitted}"

        seen[key] = emitted
        mod._graph.emitted_name = emitted


# =============================================================================
# Enum Collection & Package Emission
# =============================================================================


def _collect_used_enums(modules) -> set:
    """Collect all PlaneEnum subclasses used by nodes in modules."""
    enums = set()
    for mod in modules:
        for node in mod._graph.nodes:
            typ = getattr(node, "typ", None)
            if isinstance(typ, type) and issubclass(typ, PlaneEnum):
                enums.add(typ)
    return enums


def _get_enum_values(enum_type) -> list[tuple]:
    """Get (value_name, value, width) tuples for an enum type."""
    from .types import EnumVal

    vals = []
    for attr_name, val in enum_type.__dict__.items():
        if attr_name.startswith("_"):
            continue
        if isinstance(val, int):
            vals.append((attr_name, val))
        elif isinstance(val, EnumVal):
            vals.append((attr_name, val.value))
    n = len(vals)
    width = max(1, (n - 1).bit_length()) if n > 1 else 1
    return [(name, v, width) for name, v in vals]


def _emit_package(pkg_name: str, enums: set) -> str:
    """Emit a package with typedef enum declarations."""
    lines = [f"package {pkg_name};"]
    for enum_type in sorted(enums, key=lambda e: e.__name__):
        type_name = f"{enum_type.__name__}_t"
        vals = _get_enum_values(enum_type)
        width = vals[0][2] if vals else 1
        val_list = ", ".join(v[0] for v in vals)
        if width > 1:
            lines.append(f"  typedef enum logic [{width - 1}:0] {{ {val_list} }} {type_name};")
        else:
            lines.append(f"  typedef enum logic {{ {val_list} }} {type_name};")
    lines.append("endpackage")
    return "\n".join(lines)


def _emit_module(mod: Module, pkg_name: str, used_enums: set) -> str:
    """Emit SV for a single module."""
    graph = mod._graph
    lines = []

    # Find optimizable regs (Reg -> OutputPort)
    optimizable_regs = _find_optimizable_regs(mod)

    # 1. Emit ports
    lines.extend(_emit_ports(graph, mod))

    # 2. Emit enum declarations (import for package mode, localparam for localparam mode)
    from .utils import enum_mode

    mod_enums = {node.typ for node in graph.nodes
                 if hasattr(node, "typ") and isinstance(node.typ, type) and issubclass(node.typ, PlaneEnum)}
    if mod_enums and used_enums:
        if enum_mode == "package":
            lines.append(f"  import {pkg_name}::*;")
        else:
            # localparam mode: emit all values for each enum type used in this module
            parts = []
            for enum_type in sorted(mod_enums, key=lambda e: e.__name__):
                for val_name, val, width in _get_enum_values(enum_type):
                    parts.append(f"{enum_type.__name__}_{val_name} = {width}'d{val}")
            lines.append(f"  localparam {', '.join(parts)};")
        lines.append("")

    # 3. Emit declarations (wires, regs)
    lines.extend(_emit_declarations(graph, optimizable_regs))

    # 4. Emit flat connections as assigns
    lines.extend(_emit_flat_assigns(graph.connections, optimizable_regs))

    # 5. Emit conditional blocks (AlwaysComb)
    if hasattr(mod, "_always_comb_blocks") and mod._always_comb_blocks:
        for ac in mod._always_comb_blocks:
            lines.extend(_emit_always_comb(ac))

    # 6. Emit Reg blocks (always_ff)
    lines.extend(_emit_reg_blocks(mod, graph, optimizable_regs))

    # 7. Emit instances
    lines.extend(_emit_instances(mod))

    lines.append("endmodule")
    return "\n".join(lines)


# =============================================================================
# Port Emission
# =============================================================================


def _collect_parameters(mod) -> dict:
    """Collect Parameter objects from module attributes."""
    params = {}
    for attr_name in dir(mod):
        val = getattr(mod, attr_name, None)
        if isinstance(val, Parameter):
            params[val.name] = val
    return params


def _emit_ports(graph, mod) -> list[str]:
    """Emit module port declarations in creation order."""
    lines = []

    # Collect parameters from module attributes
    params = _collect_parameters(mod)

    # Module declaration with parameters
    if params:
        param_lines = []
        for name, param in params.items():
            param_lines.append(f"  parameter int {name} = {param.default}")
        lines.append(f"module {graph.emitted_name} #(")
        for i, pl in enumerate(param_lines):
            comma = "," if i < len(param_lines) - 1 else ""
            lines.append(f"{pl}{comma}")
        lines.append(") (")
    else:
        lines.append(f"module {graph.emitted_name} (")

    # Collect ports in creation order
    all_ports = []
    for node in graph.nodes:
        if isinstance(node, (InputPort, OutputPort, InoutPort)):
            if isinstance(node, InputPort):
                direction = "input"
            elif isinstance(node, OutputPort):
                direction = "output"
            else:
                direction = "inout"
            width = get_width(node.typ)
            signed = is_signed(node.typ)
            param_name = getattr(node.typ, "_param", None)
            all_ports.append((direction, width, signed, param_name, node))

    # Check if any port is signed — if so, all ports get a signed column
    has_signed = any(s for _, _, s, _, _ in all_ports)

    # Find max width bracket length for alignment
    width_strs = []
    for _, width, _, param_name, _ in all_ports:
        if param_name:
            width_strs.append(f"[{param_name}-1:0]")
        elif width > 1:
            width_strs.append(f"[{width - 1}:0]")
        else:
            width_strs.append("")
    max_ws = max(len(ws) for ws in width_strs) if width_strs else 0

    # Emit ports in creation order
    for i, (direction, width, signed, param_name, p) in enumerate(all_ports):
        # Emit comment if present
        if getattr(p, 'comment', None):
            lines.extend(_emit_comment(p.comment, 1))
        for attr in p._attributes:
            lines.append(f"  {attr.content()}")
        comma = "," if i < len(all_ports) - 1 else ""
        net_type = "wire " if direction == "inout" else "logic"
        signed_str = " signed" if signed else (" " * 7 if has_signed else "")
        dir_str = f"{direction:<6}"
        ws = width_strs[i]
        ws_padded = f"{ws:<{max_ws}}"
        if max_ws > 0:
            lines.append(f"  {dir_str} {net_type}{signed_str} {ws_padded} {p.name}{comma}")
        else:
            lines.append(f"  {dir_str} {net_type}{signed_str} {p.name}{comma}")

    lines.append(");")
    lines.append("")

    return lines


# =============================================================================
# Declaration Emission
# =============================================================================


def _emit_declarations(graph, optimizable_regs=None) -> list[str]:
    """Emit internal signal declarations (wires, regs)."""
    from .utils import enum_mode

    if optimizable_regs is None:
        optimizable_regs = {}

    lines = []
    wires = []
    regs = []

    for node in graph.nodes:
        if isinstance(node, Wire):
            wires.append(node)
        elif isinstance(node, (Reg, RegNext)):
            # Skip declaration for optimizable regs
            if node not in optimizable_regs:
                regs.append(node)

    def _emit_decl_line(typ, name):
        """Emit a declaration line for a node."""
        if enum_mode == "package" and isinstance(typ, type) and issubclass(typ, PlaneEnum):
            return f"  {typ.__name__}_t {name};"
        param_name = getattr(typ, "_param", None)
        width = get_width(typ)
        signed_str = " signed" if is_signed(typ) else ""
        if param_name:
            return f"  logic{signed_str} [{param_name}-1:0] {name};"
        elif width > 1:
            return f"  logic{signed_str} [{width - 1}:0] {name};"
        return f"  logic{signed_str} {name};"

    for wire in wires:
        for attr in wire._attributes:
            lines.append(f"  {attr.content()}")
        lines.append(_emit_decl_line(wire.typ, wire.name))

    for reg in regs:
        for attr in reg._attributes:
            lines.append(f"  {attr.content()}")
        lines.append(_emit_decl_line(reg.typ, reg.name))

    if wires or regs:
        lines.append("")

    return lines


# =============================================================================
# Flat Assignment Emission (Combinational, no AlwaysComb)
# =============================================================================


def _wrap_line(line: str, prefix: str, max_width: int) -> str:
    """Wrap a line at operator boundaries, respecting max_width."""
    if max_width is None or len(line) <= max_width:
        return line

    first_budget = max_width - len(prefix)
    if len(line) <= first_budget:
        return line

    # Use the position of `=` as the alignment column for continuation lines
    eq_pos = line.find(" = ")
    if eq_pos >= 0:
        cont_prefix = " " * (eq_pos + 3)
    else:
        cont_prefix = prefix

    return _wrap_line_impl(line, prefix, cont_prefix, max_width)


def _wrap_line_impl(line: str, prefix: str, cont_prefix: str, max_width: int) -> str:
    """Internal recursive wrap logic."""
    if max_width is None or len(line) <= max_width:
        return line

    first_budget = max_width - len(prefix)
    if len(line) <= first_budget:
        return line

    split_ops = [" = ", " | ", " & ", " + ", " ? ", " : "]

    for op_str in split_ops:
        idx = 0
        while idx < first_budget:
            pos = line.find(op_str, idx)
            if pos == -1 or pos > first_budget:
                break
            before = pos - 1
            after = pos + len(op_str)
            if before >= 0 and after < len(line) and line[before] == ")" and line[after] == "(":
                tail = _wrap_line_impl(line[after:], cont_prefix, cont_prefix, max_width)
                return line[:before + 1] + op_str.rstrip() + "\n" + cont_prefix + tail
            idx = pos + len(op_str)

    return line


def _emit_flat_assigns(connections, optimizable_regs=None) -> list[str]:
    """Emit assign statements for connections outside AlwaysComb."""
    if optimizable_regs is None:
        optimizable_regs = {}

    assigns = []
    for sink, source in connections:
        if isinstance(sink, RegNext):
            continue
        
        # Handle optimized regs
        if source in optimizable_regs:
            canonical_port = optimizable_regs[source]
            # Skip assign if sink is the canonical port
            if sink is canonical_port:
                continue
            # Emit assign from canonical port with comment
            reg_name = source.name
            assigns.append((sink, _emit_expr(sink), _emit_expr(canonical_port), f"// optimized from {reg_name}"))
            continue
        
        assigns.append((sink, _emit_expr(sink), _emit_expr(source), None))

    if not assigns:
        return []

    max_lhs = max(len(lhs) for _, lhs, _, _ in assigns)
    lines = []
    for sink, lhs, rhs, inline_comment in assigns:
        # Emit pre-comment if sink has one
        pre_comment = getattr(sink, 'comment', None)
        if pre_comment:
            lines.extend(_emit_comment(pre_comment, 1))
        padded = f"  assign {lhs:<{max_lhs}} = {rhs};"
        if inline_comment:
            padded += f" {inline_comment}"
        lines.append(_wrap_line(padded, "  ", utils.max_line_width))
    lines.append("")
    return lines


# =============================================================================
# AlwaysComb Emission
# =============================================================================


def _emit_always_comb(ctx: AlwaysCombContext) -> list[str]:
    """Emit always_comb block from context."""
    lines = []
    lines.extend(_emit_comment(getattr(ctx, "comment", None), 1))
    lines.append("  always_comb begin")
    for item in ctx.assignments:
        if isinstance(item, tuple):
            sink, source = item
            lines.append(f"    {_emit_expr(sink)} = {_emit_expr(source)};")
        elif isinstance(item, (WhenContext, ElseWhenContext, OtherwiseContext)):
            lines.extend(_emit_conditional(item, 2))
        elif isinstance(item, SwitchContext):
            lines.extend(_emit_switch(item, 2))
        else:
            raise ValueError(f"Unexpected item in AlwaysComb: {type(item).__name__}")
    lines.append("  end")
    lines.append("")
    return lines


# =============================================================================
# Conditional Emission (When/ElseWhen/Otherwise)
# =============================================================================


def _emit_body_items(items, indent: int) -> list[str]:
    """Emit body items (assignments, When/Switch) at given indent level."""
    prefix = "  " * indent
    lines = []
    for item in items:
        if isinstance(item, tuple):
            sink, source = item
            lines.append(f"{prefix}{_emit_expr(sink)} = {_emit_expr(source)};")
        elif isinstance(item, (WhenContext, ElseWhenContext, OtherwiseContext)):
            lines.extend(_emit_conditional(item, indent))
        elif isinstance(item, SwitchContext):
            lines.extend(_emit_switch(item, indent))
    return lines


def _emit_conditional(ctx, indent: int) -> list[str]:
    """Emit if/else based on context type."""
    prefix = "  " * indent
    lines = []
    lines.extend(_emit_comment(getattr(ctx, "comment", None), indent))

    if isinstance(ctx, OtherwiseContext):
        lines.append(f"{prefix}else begin")
    elif isinstance(ctx, ElseWhenContext):
        cond_str = _emit_expr(ctx.condition)
        cond_str = cond_str.strip("()")
        lines.append(f"{prefix}else if ({cond_str}) begin")
    else:
        cond_str = _emit_expr(ctx.condition)
        cond_str = cond_str.strip("()")
        lines.append(f"{prefix}if ({cond_str}) begin")

    lines.extend(_emit_body_items(ctx.assignments, indent + 1))

    lines.append(f"{prefix}end")
    return lines


# =============================================================================
# Switch Emission
# =============================================================================


def _emit_switch(ctx: SwitchContext, indent: int) -> list[str]:
    """Emit case statement."""
    prefix = "  " * indent
    inner = "  " * (indent + 1)
    lines = []
    lines.extend(_emit_comment(getattr(ctx, "comment", None), indent))

    sel_str = _emit_expr(ctx.select)
    lines.append(f"{prefix}case ({sel_str})")

    from .utils import enum_mode

    for item in ctx.assignments:
        if isinstance(item, CaseContext):
            if item.enum_info:
                enum_type, value_name = item.enum_info
                if enum_mode == "package":
                    case_val = f"{enum_type.__name__}_t::{value_name}"
                else:
                    case_val = f"{enum_type.__name__}_{value_name}"
            else:
                case_width = get_node_width(ctx.select)
                case_val = f"{case_width}'d{item.value}"
            lines.extend(_emit_comment(getattr(item, "comment", None), indent + 1))
            lines.append(f"{inner}{case_val}: begin")
            lines.extend(_emit_body_items(item.assignments, indent + 2))
            lines.append(f"{inner}end")
        elif isinstance(item, DefaultContext):
            lines.extend(_emit_comment(getattr(item, "comment", None), indent + 1))
            lines.append(f"{inner}default: begin")
            lines.extend(_emit_body_items(item.assignments, indent + 2))
            lines.append(f"{inner}end")

    lines.append(f"{prefix}endcase")
    return lines


# =============================================================================
# RegNext Emission (always_ff blocks)
# =============================================================================


def _emit_reg_block_single(reg, next_node, reg_names, reg_comments) -> list[str]:
    """Emit a single always_ff block for one Reg."""
    lines = []
    lines.extend(_emit_comment(getattr(reg, "comment", None), 1))
    clk_name = reg._clk.name
    name = reg_names[reg]
    comment = reg_comments[reg]

    if reg._rst:
        rst_name = reg._rst.name
        rst_typ = reg._rst.typ
        reset_cond = f"!{rst_name}" if rst_typ.is_active_low() else rst_name

        if rst_typ.is_async():
            edge = "negedge" if rst_typ.is_active_low() else "posedge"
            lines.append(f"  always_ff @(posedge {clk_name} or {edge} {rst_name}) begin")
            lines.append(f"    if ({reset_cond}) begin")
            lines.append(f"      {name} <= {reg._emit_init_value()};{comment}")
            lines.append("    end else begin")
            lines.append(f"      {name} <= {_emit_expr(next_node)};{comment}")
            lines.append("    end")
            lines.append("  end")
        else:
            lines.append(f"  always_ff @(posedge {clk_name}) begin")
            lines.append(f"    if ({reset_cond}) begin")
            lines.append(f"      {name} <= {reg._emit_init_value()};{comment}")
            lines.append("    end else begin")
            lines.append(f"      {name} <= {_emit_expr(next_node)};{comment}")
            lines.append("    end")
            lines.append("  end")
    else:
        lines.append(f"  always_ff @(posedge {clk_name}) begin")
        lines.append(f"    {name} <= {_emit_expr(next_node)};{comment}")
        lines.append("  end")

    lines.append("")
    return lines


def _emit_reg_blocks(mod: Module, graph, optimizable_regs=None) -> list[str]:
    """Emit always_ff blocks for Reg/RegNext."""
    if optimizable_regs is None:
        optimizable_regs = {}

    lines = []
    reg_nodes = [n for n in graph.nodes if isinstance(n, Reg)]

    use_grouping = type(mod).__dict__.get("group_always_ff", utils.group_always_ff)

    # Precompute names: use OutputPort name for optimizable regs, otherwise use Reg name
    reg_names = {reg: optimizable_regs[reg].name if reg in optimizable_regs else reg.name for reg in reg_nodes}
    
    # Precompute comments for optimized regs
    reg_comments = {reg: f" // optimized from {reg.name}" if reg in optimizable_regs else "" for reg in reg_nodes}

    if use_grouping:
        # Group by (clk, rst) - using actual nodes as keys
        reg_map = {}

        for reg in reg_nodes:
            if reg.next is None:
                continue
            key = (reg._clk, reg._rst)
            if key not in reg_map:
                reg_map[key] = []
            reg_map[key].append((reg, reg.next))

        for (clk, rst), regs in reg_map.items():
            if not regs:
                continue

            clk_name = clk.name
            max_r = max(len(reg_names[reg]) for reg, _ in regs)

            for reg, _ in regs:
                lines.extend(_emit_comment(getattr(reg, "comment", None), 1))

            if rst:
                rst_name = rst.name
                rst_typ = rst.typ
                
                if rst_typ.is_async():
                    edge = "negedge" if rst_typ.is_active_low() else "posedge"
                    lines.append(f"  always_ff @(posedge {clk_name} or {edge} {rst_name}) begin")
                    reset_cond = f"!{rst_name}" if rst_typ.is_active_low() else rst_name
                    lines.append(f"    if ({reset_cond}) begin")
                    for reg, next_node in regs:
                        lines.append(f"      {reg_names[reg]:<{max_r}} <= {reg._emit_init_value()};{reg_comments[reg]}")
                    lines.append("    end else begin")
                    for reg, next_node in regs:
                        lines.append(f"      {reg_names[reg]:<{max_r}} <= {_emit_expr(next_node)};{reg_comments[reg]}")
                    lines.append("    end")
                    lines.append("  end")
                else:
                    lines.append(f"  always_ff @(posedge {clk_name}) begin")
                    reset_cond = f"!{rst_name}" if rst_typ.is_active_low() else rst_name
                    lines.append(f"    if ({reset_cond}) begin")
                    for reg, next_node in regs:
                        lines.append(f"      {reg_names[reg]:<{max_r}} <= {reg._emit_init_value()};{reg_comments[reg]}")
                    lines.append("    end else begin")
                    for reg, next_node in regs:
                        lines.append(f"      {reg_names[reg]:<{max_r}} <= {_emit_expr(next_node)};{reg_comments[reg]}")
                    lines.append("    end")
                    lines.append("  end")
            else:
                lines.append(f"  always_ff @(posedge {clk_name}) begin")
                max_r = max(len(reg_names[reg]) for reg, _ in regs)
                for reg, next_node in regs:
                    lines.append(f"    {reg_names[reg]:<{max_r}} <= {_emit_expr(next_node)};{reg_comments[reg]}")
                lines.append("  end")

            lines.append("")
    else:
        # One always_ff per Reg
        for reg in reg_nodes:
            if reg.next is None:
                continue
            lines.extend(_emit_reg_block_single(reg, reg.next, reg_names, reg_comments))

    return lines


# =============================================================================
# Instance Emission
# =============================================================================


def _emit_instances(mod: Module) -> list[str]:
    """Emit child module instances."""
    lines = []

    if not mod._children:
        return lines

    # Build port connections for each child using loads/drivers
    instance_connections = {}  # child_module -> {port_name: connected_node}

    for child in mod._children:
        instance_connections[child] = {}

        # Check child's input ports (they have drivers)
        for node in child._graph.nodes:
            if isinstance(node, (InputPort, InoutPort)) and node.drivers:
                # node is child's input/inout, node.drivers[0] is what drives it
                instance_connections[child][node.name] = node.drivers[0]
            elif isinstance(node, OutputPort) and node.loads:
                # node is child's output, node.loads[0] is what it drives
                instance_connections[child][node.name] = node.loads[0]

    # Emit instances
    for child in mod._children:
        inst_name = child._instance_name
        lines.extend(_emit_instance(child, instance_connections.get(child, {}), inst_name))

    return lines


def _emit_instance(mod, port_conns: dict, inst_name: str = None) -> list[str]:
    """Emit an instance."""
    lines = []
    lines.extend(_emit_comment(getattr(mod, "comment", None), 1))
    module_name = mod._graph.emitted_name
    if inst_name is None:
        inst_name = mod._graph.module_name.lower()

    # Add array range for array instances
    count = getattr(mod, "_instance_count", 1)
    if isinstance(count, Parameter) or (isinstance(count, int) and count > 1):
        if isinstance(count, Parameter):
            inst_name = f"{inst_name}[{count.name}-1:0]"
        else:
            inst_name = f"{inst_name}[{count - 1}:0]"

    # Emit parameter overrides
    overrides = getattr(mod, "_param_overrides", None)
    if overrides:
        param_strs = []
        for pname, val in overrides.items():
            if isinstance(val, Parameter):
                param_strs.append(f".{pname}({val.name})")
            else:
                param_strs.append(f".{pname}({val})")
        lines.append(f"  {module_name} #({', '.join(param_strs)}) {inst_name} (")
    else:
        lines.append(f"  {module_name} {inst_name} (")

    # Get all ports from the module
    all_ports = []
    for node in mod._graph.nodes:
        if isinstance(node, (InputPort, OutputPort, InoutPort)):
            all_ports.append(node.name)

    if not all_ports:
        return lines

    max_port = max(len(pn) for pn in all_ports)

    for i, port_name in enumerate(all_ports):
        comma = "," if i < len(all_ports) - 1 else ""
        conn = port_conns.get(port_name)
        if conn is None:
            conn_str = "/* unconnected */"
        else:
            conn_str = _emit_expr(conn)
        lines.append(f"    .{port_name:<{max_port}} ({conn_str}){comma}")

    lines.append("  );")
    lines.append("")

    return lines


# =============================================================================
# Expression Emission
# =============================================================================


BINARY_OP_MAP = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
    "mod": "%",
    "and": "&",
    "or": "|",
    "xor": "^",
    "eq": "==",
    "ne": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "lshift": "<<",
    "rshift": ">>",
}


def _emit_expr(node) -> str:
    """Emit a node as an expression."""
    if node is None:
        return "'0"

    # Handle primitive types
    if isinstance(node, (InputPort, OutputPort, InoutPort, Wire, Reg, RegNext)):
        # Check if this register is optimized to drive an output port directly
        if isinstance(node, Reg) and hasattr(node, '_optimized_to'):
            return node._optimized_to.name
        return node.name if node.name else "_unnamed"

    if isinstance(node, Literal):
        width = node.width or 1
        value = node.value & ((1 << width) - 1) if node.value < 0 else node.value
        return f"{width}'d{value}"

    if isinstance(node, EnumVal):
        from .utils import enum_mode

        if enum_mode == "package":
            type_name = f"{node.enum_type.__name__}_t"
            return f"{type_name}::{node.value_name}"
        return f"{node.enum_type.__name__}_{node.value_name}"

    if isinstance(node, BinOp):
        left = _emit_expr(node.drivers[0])
        right = _emit_expr(node.drivers[1])
        op = BINARY_OP_MAP.get(node.op, node.op)
        return f"({left} {op} {right})"

    if isinstance(node, UnaryOp):
        operand = _emit_expr(node.drivers[0])
        unary_map = {"not": "~", "neg": "-"}
        op = unary_map.get(node.op, node.op)
        return f"{op}{operand}"

    if isinstance(node, Mux):
        sel = _emit_expr(node.drivers[0])
        then_ = _emit_expr(node.drivers[1])
        else_ = _emit_expr(node.drivers[2])
        return f"({sel} ? {then_} : {else_})"

    if isinstance(node, Cat):
        parts = [_emit_expr(p) for p in node.parts]
        return "{" + ", ".join(parts) + "}"

    if isinstance(node, Slice):
        expr = _emit_expr(node.expr)
        if node.hi == node.lo:
            return f"{expr}[{node.hi}]"
        return f"{expr}[{node.hi}:{node.lo}]"

    if isinstance(node, Index):
        expr = _emit_expr(node.expr)
        return f"{expr}[{node.index}]"

    if isinstance(node, ZeroExtend):
        expr = _emit_expr(node.expr)
        inner_width = get_node_width(node.expr)
        extend_bits = node.width - inner_width
        return f"{{{extend_bits}'d0, {expr}}}"

    if isinstance(node, SignExtend):
        expr = _emit_expr(node.expr)
        inner_width = get_node_width(node.expr)
        extend_bits = node.width - inner_width
        msb = inner_width - 1
        return f"{{{extend_bits}{{{expr}[{msb}]}}, {expr}}}"

    if isinstance(node, Replicate):
        expr = _emit_expr(node.expr)
        return f"{{{node.count}{{{expr}}}}}"

    if isinstance(node, ReductionOp):
        expr = _emit_expr(node.expr)
        op_map = {"and": "&", "or": "|", "xor": "^"}
        op = op_map.get(node.op, node.op)
        return f"{op}{expr}"

    if isinstance(node, SIntCast):
        expr = _emit_expr(node.expr)
        return f"$signed({expr})"

    if isinstance(node, UIntCast):
        expr = _emit_expr(node.expr)
        return f"$unsigned({expr})"

    # Fallback
    return node.name if hasattr(node, "name") else "_unknown"



