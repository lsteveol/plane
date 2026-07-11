import re
import warnings

from .types import Bits, Bool, Clock, PlaneEnum, Reset, SInt, UInt

# Width mismatch check mode: "silent", "warn", or "error"
width_mismatch_mode = "warn"

# Enum emission mode: "package" (typedef enum) or "localparam" (per-module localparams)
enum_mode = "package"

# Group all Regs with same clk/rst into one always_ff block. If False, emit one per Reg.
group_always_ff = True

# Optimize Reg → OutputPort assignments. If True, eliminate intermediate assign statements
# when a Reg drives an OutputPort directly. Can be overridden per-Reg with optimize=False.
optimize_reg_to_port = True

# Max line width for emitted expressions. Set to None to disable wrapping.
max_line_width = 120

# Prefix for all plane-emitted module names (BlackBoxes excluded).
# Example: module_prefix = "my_prefix" -> Counter becomes my_prefix_Counter
module_prefix = None

# Convert CamelCase module names to snake_case (BlackBoxes excluded).
# Example: MyApbFanout becomes my_apb_fanout
# Applied BEFORE module_prefix, so: MyApbFanout -> my_apb_fanout -> my_prefix_my_apb_fanout
convert_module_names_to_snake_case = False


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case.

    Handles acronyms (IOController -> io_controller),
    digits (APB3Adapter -> apb3_adapter), and leaves already-snake names unchanged.
    """
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


class WidthMismatchError(TypeError):
    pass


def get_node_width(node) -> int:
    """Get width of any node (port, wire, reg, or expression)."""
    if node is None:
        return 1
    if hasattr(node, "width") and node.width is not None:
        return node.width
    if hasattr(node, "typ") and node.typ:
        return get_width(node.typ)
    return 1


def check_width_mismatch(sink, source):
    """Check sink/source width and warn or error based on mode."""
    sink_w = get_node_width(sink)
    src_w = get_node_width(source)

    # Skip if either width involves a parameterized type
    sink_typ = getattr(sink, "typ", None)
    src_typ = getattr(source, "typ", None)
    for t in (sink_typ, src_typ):
        if getattr(t, "_param", None):
            return

    if sink_w == src_w:
        return

    msg = f"Width mismatch: {sink.name} ({sink_w}) <- {getattr(source, 'name', 'expr')} ({src_w})"

    if width_mismatch_mode == "error":
        raise WidthMismatchError(msg)
    elif width_mismatch_mode == "warn":
        warnings.warn(msg, UserWarning, stacklevel=3)


def get_width(typ):
    """Get width from a type, defaulting to 1."""
    if typ is None:
        return 1
    if isinstance(typ, (Bits, UInt, SInt)):
        return typ.width if hasattr(typ, "width") else 1
    if isinstance(typ, (Bool, Clock, Reset)):
        return 1
    if isinstance(typ, type) and issubclass(typ, PlaneEnum):
        n = len(typ._enum_vals)
        return max(1, (n - 1).bit_length())
    if hasattr(typ, "width"):
        return typ.width
    return 1


def is_signed(typ) -> bool:
    """Check if a type is signed."""
    return getattr(typ, "signed", False)


def validate_identifier(name: str, context: str = "identifier") -> None:
    """Validate that a name is a valid SystemVerilog identifier.

    Args:
        name: The name to validate
        context: Description of what this name is for (e.g., "port name", "wire name")

    Raises:
        ValueError: If the name is invalid
    """
    if not name:
        raise ValueError(f"{context} cannot be empty")

    # SystemVerilog identifiers: start with letter or underscore,
    # contain letters, digits, underscore, or dollar sign
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_$]*$"
    if not re.match(pattern, name):
        raise ValueError(
            f"Invalid {context} {name!r}: must start with letter or underscore, "
            f"and contain only letters, digits, underscore, or dollar sign"
        )

    # Check for SystemVerilog keywords (partial list - most common ones)
    keywords = {
        "module",
        "endmodule",
        "input",
        "output",
        "inout",
        "wire",
        "logic",
        "reg",
        "always",
        "always_ff",
        "always_comb",
        "initial",
        "assign",
        "if",
        "else",
        "case",
        "endcase",
        "default",
        "for",
        "while",
        "function",
        "endfunction",
        "task",
        "endtask",
        "generate",
        "endgenerate",
        "begin",
        "end",
        "parameter",
        "localparam",
        "signed",
        "unsigned",
        "packed",
        "array",
        "struct",
        "union",
        "enum",
        "interface",
        "endinterface",
    }
    if name.lower() in keywords:
        raise ValueError(f"Invalid {context} {name!r}: cannot use SystemVerilog keyword")
