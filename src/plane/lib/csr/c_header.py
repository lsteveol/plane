from pathlib import Path

from .block import RegisterBlock
from .system import RegisterSystem


def generate_c_header(node, output_dir=None, prefix_block_name=True):
    """Generate C header file(s) for a block or system.

    For a RegisterBlock: returns the header string, optionally writes to output_dir (file path).
    For a RegisterSystem: writes one .h file per unique block + one per system to output_dir (directory).
    """
    if isinstance(node, RegisterBlock):
        result = _gen_block_header(node, prefix_block_name)
        if output_dir is not None:
            Path(output_dir).write_text(result)
        return result
    elif isinstance(node, RegisterSystem):
        if output_dir is None:
            raise ValueError("output_dir is required for RegisterSystem C header generation")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _collect_and_emit_system(node, output_dir, set(), set(), prefix_block_name)
    else:
        raise TypeError(f"Expected RegisterBlock or RegisterSystem, got {type(node).__name__}")


def _format_metadata(d):
    """Format metadata dict as 'key=value' string, or None if empty."""
    if not d:
        return None
    parts = []
    for k, v in d.items():
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _gen_block_comment(block):
    """Generate multi-line comment for a block."""
    lines = ["/*"]
    lines.append(f" * {block.name}")
    if block.description:
        lines.append(f" * Description: {block.description}")
    meta = _format_metadata(block.metadata)
    if meta:
        lines.append(f" * Metadata: {meta}")
    lines.append(" */")
    return "\n".join(lines)


def _gen_reg_comment(reg):
    """Generate multi-line comment for a register."""
    lines = ["/*"]
    lines.append(f" * {reg.name}")
    if reg.description:
        lines.append(f" * Description: {reg.description}")
    meta = _format_metadata(reg.metadata)
    if meta:
        lines.append(f" * Metadata: {meta}")
    lines.append(" */")
    return "\n".join(lines)


def _gen_field_comment(fld):
    """Generate multi-line comment for a field (includes Access)."""
    lines = ["/*"]
    lines.append(f" * {fld.name}")
    if fld.description:
        lines.append(f" * Description: {fld.description}")
    lines.append(f" * Access: {fld.access}")
    meta = _format_metadata(fld.metadata)
    if meta:
        lines.append(f" * Metadata: {meta}")
    lines.append(" */")
    return "\n".join(lines)


def _gen_field_macros_block():
    """Generate the generic field access macros block."""
    return """#ifndef PLANE_FIELD_MACROS
#define PLANE_FIELD_MACROS

/* Register access (32-bit) */
#define REG_READ(base, offset)        (*((volatile uint32_t *)((uintptr_t)(base) + (offset))))
#define REG_WRITE(base, offset, val) (*((volatile uint32_t *)((uintptr_t)(base) + (offset))) = (uint32_t)(val))

/* Field access (32-bit RMW) */
#define GET_FIELD(reg, field)          (((uint32_t)(reg) >> field##_OFFSET) & field##_MASK)
#define UPDATE_FIELD(reg, field, val) (((uint32_t)(reg) & ~((uint32_t)field##_MASK << field##_OFFSET)) | (((val) & field##_MASK) << field##_OFFSET))

/* Field write (8-bit direct — no RMW, user must ensure field is sole byte occupant or accept corruption */
#define FIELD8_WRITE(base, offset, field, val) \\
    (*((volatile uint8_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \\
        (uint8_t)((val) & field##_MASK))

/* Field write (16-bit direct — no RMW, user must ensure field is sole halfword occupant or accept corruption */
#define FIELD16_WRITE(base, offset, field, val) \\
    (*((volatile uint16_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \\
        (uint16_t)((val) & field##_MASK))

#endif"""


def _gen_block_header(block, prefix_block_name=True):
    """Generate C header string for a RegisterBlock."""
    guard = f"{block.name.upper()}_H"
    prefix = f"{block.name.upper()}_" if prefix_block_name else ""

    lines = []
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")
    lines.append(_gen_block_comment(block))
    lines.append("")

    for reg in block.registers:
        reg_upper = reg.name.upper()
        lines.append(_gen_reg_comment(reg))
        lines.append(f"#define {prefix}{reg_upper}_ADDR          0x{reg.offset:04X}")

        reset_val = sum(f.reset << f.offset for f in reg.fields)
        lines.append(f"#define {prefix}{reg_upper}_RESET         0x{reset_val:08X}")
        lines.append("")

        if reg.fields:
            max_field_name_len = max(len(f.name) for f in reg.fields)
            max_define_len = len(f"{prefix}{reg_upper}_{'X' * max_field_name_len}_BYTE_OFFSET")

            for fld in reg.fields:
                byte_offset = fld.offset // 8
                mask = (1 << fld.width) - 1

                offset_define = f"{prefix}{reg_upper}_{fld.name.upper()}_OFFSET"
                width_define = f"{prefix}{reg_upper}_{fld.name.upper()}_WIDTH"
                mask_define = f"{prefix}{reg_upper}_{fld.name.upper()}_MASK"
                byte_offset_define = f"{prefix}{reg_upper}_{fld.name.upper()}_BYTE_OFFSET"

                lines.append(_gen_field_comment(fld))
                lines.append(f"#define {offset_define.ljust(max_define_len)} {fld.offset}")
                lines.append(f"#define {width_define.ljust(max_define_len)} {fld.width}")
                lines.append(f"#define {mask_define.ljust(max_define_len)} 0x{mask:X}")
                lines.append(f"#define {byte_offset_define.ljust(max_define_len)} {byte_offset}")
                lines.append("")

    lines.append(_gen_field_macros_block())
    lines.append("")
    lines.append(f"#endif /* {guard} */")
    lines.append("")

    return "\n".join(lines)


def _gen_system_header(system, prefix_block_name=True):
    """Generate C header string for a RegisterSystem."""
    guard = f"{system.name.upper()}_H"

    lines = []
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")
    lines.append(_gen_block_comment(system))
    lines.append("")

    seen_children = set()
    for child in system.children:
        child_name = child.obj.name
        if child_name not in seen_children:
            seen_children.add(child_name)
            lines.append(f'#include "{child_name}.h"')

    if seen_children:
        lines.append("")

    lines.append("/* Child block/system offsets */")
    for child in system.children:
        lines.append(f"#define {system.name.upper()}_{child.name.upper()}_OFFSET    0x{child.offset:04X}")

    lines.append("")
    lines.append(f"#endif /* {guard} */")
    lines.append("")

    return "\n".join(lines)


def _collect_and_emit_system(system, output_dir, emitted_blocks, emitted_systems, prefix_block_name):
    """Recursively walk system tree, write unique block headers and system headers."""
    for child in system.children:
        if isinstance(child.obj, RegisterBlock):
            if child.obj.name not in emitted_blocks:
                emitted_blocks.add(child.obj.name)
                header_content = _gen_block_header(child.obj, prefix_block_name)
                (output_dir / f"{child.obj.name}.h").write_text(header_content)
        elif isinstance(child.obj, RegisterSystem):
            _collect_and_emit_system(child.obj, output_dir, emitted_blocks, emitted_systems, prefix_block_name)

    if system.name not in emitted_systems:
        emitted_systems.add(system.name)
        header_content = _gen_system_header(system, prefix_block_name)
        (output_dir / f"{system.name}.h").write_text(header_content)
