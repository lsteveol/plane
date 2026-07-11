from .base import Module, Node
from .connect import Builder
from .types import (
    Bits,
    Bool,
    Bundle,
    Flipped,
    SInt,
    UInt,
    Vec,
)
from .types import (
    Inout as InoutType,
)
from .types import (
    Input as InputType,
)
from .types import (
    Output as OutputType,
)
from .utils import validate_identifier


class VecProxy:
    """Wrapper for Vec elements. Not a Node — holds expanded Wire/InputPort/OutputPort nodes."""

    def __init__(self, elements, element_type, depth):
        self.elements = elements
        self.element_type = element_type
        self.depth = depth

    def __getitem__(self, index):
        if isinstance(index, int):
            return self.elements[index]
        result = self.elements[-1]
        for i in range(self.depth - 2, -1, -1):
            result = Mux(index == i, self.elements[i], result)
        return result

    def __setitem__(self, index, value):
        pass

    def __matmul__(self, source):
        """Handle Vec @= Vec, Vec @= int, Vec @= Literal."""
        if isinstance(source, VecProxy):
            if source.depth != self.depth:
                raise TypeError(f"Vec depth mismatch: {self.depth} != {source.depth}")
            for a, b in zip(self.elements, source.elements):
                a @= b
        elif isinstance(source, int):
            width = getattr(self.element_type, "width", 1)
            for elem in self.elements:
                elem @= Literal(source, width)
        elif isinstance(source, Literal):
            for elem in self.elements:
                elem @= source
        else:
            raise TypeError(f"Cannot assign {type(source).__name__} to Vec")
        return self


def _expand_vec(node_cls, typ, name, flip_count=0):
    """Expand a Vec type into individual nodes. Returns a VecProxy."""
    elements = []
    for i in range(typ.depth):
        elem_name = f"{name}_{i}"
        if isinstance(typ.typ, Bundle) or (
            isinstance(typ.typ, type) and issubclass(typ.typ, Bundle)
        ):
            elem = _expand_bundle(typ.typ, elem_name, flip_count, _PORT_MAP)
        else:
            elem = node_cls(typ.typ, name=elem_name)
        elements.append(elem)
    return VecProxy(elements, typ.typ, typ.depth)


class BundleProxy:
    """Wrapper for Bundle fields. Not a Node — holds expanded port/wire/reg nodes."""

    def __init__(self, fields: dict):
        self._fields = fields

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._fields:
            return self._fields[name]
        raise AttributeError(f"Bundle has no field {name!r}")

    def __matmul__(self, source):
        if not isinstance(source, BundleProxy):
            raise TypeError(f"Cannot assign {type(source).__name__} to Bundle")
        for name, sink_node in self._fields.items():
            if name not in source._fields:
                raise ConnectionError(f"Field {name} not found in source bundle")
            source_node = source._fields[name]

            # Nested bundle: recurse
            if isinstance(sink_node, BundleProxy):
                sink_node @= source_node
                continue

            sink_dir = getattr(sink_node, "_direction", None)
            source_dir = getattr(source_node, "_direction", None)

            # If either node is not a port, use normal assignment
            if sink_dir is None or source_dir is None:
                sink_node @= source_node
                continue

            if sink_dir != source_dir:
                # Different directions: Output drives Input
                if sink_dir == "Input" and source_dir == "Output":
                    sink_node @= source_node
                elif sink_dir == "Output" and source_dir == "Input":
                    source_node @= sink_node
                else:
                    raise ConnectionError(
                        f"Invalid direction combination for field {name}: {sink_dir} and {source_dir}"
                    )
            else:
                # Same direction: check module relationship
                sink_mod = sink_node._module
                source_mod = source_node._module

                if sink_mod == source_mod:
                    # Same module: let normal assignment handle it
                    sink_node @= source_node
                elif source_mod in sink_mod._children:
                    # sink is parent, source is child
                    if sink_dir == "Input":
                        source_node @= sink_node
                    else:
                        sink_node @= source_node
                elif sink_mod in source_mod._children:
                    # sink is child, source is parent
                    if sink_dir == "Input":
                        sink_node @= source_node
                    else:
                        source_node @= sink_node
                else:
                    raise ConnectionError(
                        f"Cannot connect bundles from unrelated modules: {name}"
                    )

        return self


def _get_bundle_fields(bundle_instance):
    """Extract field names and values from a Bundle instance or class.

    Checks instance __dict__ first, then falls back to class attributes.
    Returns list of (field_name, value) tuples. Value is either a direction
    marker (Input/Output/Inout) or a raw Bundle class.
    """
    bundle_cls = type(bundle_instance) if isinstance(bundle_instance, Bundle) else bundle_instance
    if not issubclass(bundle_cls, Bundle):
        return []

    fields = []
    seen = set()
    for attr_name, attr_val in vars(bundle_cls).items():
        if attr_name.startswith("_"):
            continue
        if isinstance(attr_val, (InputType, OutputType, InoutType)):
            if isinstance(attr_val.typ, Bundle):
                raise TypeError(
                    f"Cannot wrap Bundle with direction marker. "
                    f"Declare nested Bundles directly without Input/Output/Inout. "
                    f"Got: {attr_name} = {type(attr_val).__name__}({type(attr_val.typ).__name__})"
                )
            fields.append((attr_name, attr_val))
            seen.add(attr_name)
        elif isinstance(attr_val, type) and issubclass(attr_val, Bundle):
            fields.append((attr_name, attr_val))
            seen.add(attr_name)
        elif isinstance(attr_val, Bundle):
            fields.append((attr_name, attr_val))
            seen.add(attr_name)

    if isinstance(bundle_instance, Bundle):
        for attr_name, attr_val in bundle_instance.__dict__.items():
            if attr_name in seen:
                continue
            if isinstance(attr_val, (InputType, OutputType, InoutType)):
                if isinstance(attr_val.typ, Bundle):
                    raise TypeError(
                        f"Cannot wrap Bundle with direction marker. "
                        f"Declare nested Bundles directly without Input/Output/Inout. "
                        f"Got: {attr_name} = {type(attr_val).__name__}({type(attr_val.typ).__name__})"
                    )
                fields.append((attr_name, attr_val))
            elif isinstance(attr_val, type) and issubclass(attr_val, Bundle):
                fields.append((attr_name, attr_val))
            elif isinstance(attr_val, Bundle):
                fields.append((attr_name, attr_val))

    return fields


def _expand_bundle(bundle_instance, prefix, flip_count, port_cls_map=None):
    """Expand a Bundle into flat nodes. Returns a BundleProxy.

    Args:
        bundle_instance: Bundle instance (or class) to expand
        prefix: Name prefix for generated nodes
        flip_count: Number of Flipped wrappers (odd = reverse directions)
        port_cls_map: If provided, use these classes for ports. If None, use Wire.
    """
    bundle_cls = type(bundle_instance) if isinstance(bundle_instance, Bundle) else bundle_instance
    if prefix is None:
        prefix = bundle_cls.__name__.lower()
    fields = _get_bundle_fields(bundle_instance)

    result = {}
    for field_name, field_val in fields:
        field_name_full = f"{prefix}_{field_name}"

        if isinstance(field_val, (InputType, OutputType, InoutType)):
            effective_marker = _flip_marker(type(field_val), flip_count)
            typ = field_val.typ

            if isinstance(typ, Vec):
                if port_cls_map:
                    node_cls = port_cls_map.get(effective_marker, Wire)
                    result[field_name] = _expand_vec(node_cls, typ, field_name_full, flip_count)
                else:
                    result[field_name] = _expand_vec(Wire, typ, field_name_full)
            else:
                if port_cls_map:
                    node_cls = port_cls_map.get(effective_marker, Wire)
                    result[field_name] = node_cls(typ, name=field_name_full)
                else:
                    result[field_name] = Wire(typ, name=field_name_full)

        elif isinstance(field_val, type) and issubclass(field_val, Bundle):
            result[field_name] = _expand_bundle(
                field_val, field_name_full, flip_count, port_cls_map
            )
        elif isinstance(field_val, Bundle):
            result[field_name] = _expand_bundle(
                type(field_val), field_name_full, flip_count, port_cls_map
            )

    return BundleProxy(result)


def _resolve_port_name(typ, name):
    """Resolve port name from type if not provided."""
    if name is None and hasattr(typ, "name"):
        name = typ.name
    return name


class Port(Node):
    """Base class for ports."""

    _direction = "port"

    def __new__(cls, typ=None, name: str = None, comment: str = None):
        if isinstance(typ, Vec):
            return _expand_vec(cls, typ, name)
        return super().__new__(cls)

    def __init__(self, typ=None, name: str = None, comment: str = None):
        if isinstance(typ, Vec):
            return
        name = _resolve_port_name(typ, name)
        if name is None:
            raise ValueError(f"{self._direction} port must have a name")
        validate_identifier(name, "port name")
        self.typ = typ
        super().__init__(name, comment)


class InputPort(Port):
    _direction = "Input"


class OutputPort(Port):
    _direction = "Output"


class InoutPort(Port):
    _direction = "Inout"


_PORT_MAP = {
    InputType: InputPort,
    OutputType: OutputPort,
    InoutType: InoutPort,
}

_FLIP_MAP = {
    InputType: OutputType,
    OutputType: InputType,
    InoutType: InoutType,
}


def _unwrap_flipped(marker):
    """Unwrap Flipped markers. Returns (inner, flipped_count)."""
    count = 0
    inner = marker
    while isinstance(inner, Flipped):
        inner = inner.inner
        count += 1
    return inner, count


def _flip_marker(marker_type, count):
    """Flip a direction marker type if count is odd."""
    if count % 2 == 1:
        return _FLIP_MAP.get(marker_type, marker_type)
    return marker_type


def IO(marker, name: str = None, comment: str = None):
    """Create a port from a direction marker, Bundle, or Vec of Bundles.

    Args:
        marker: Input(T), Output(T), Inout(T), Bundle, or Vec(Bundle),
                optionally wrapped in Flipped
        name: Port name (required for primitives, prefix for Vec/Bundle)
        comment: Optional comment to attach to the port
    """
    inner, flip_count = _unwrap_flipped(marker)

    if isinstance(inner, Bundle):
        if name is None:
            raise ValueError("Bundle port must have a name (used as prefix)")
        validate_identifier(name, "port name")
        return _expand_bundle(inner, name, flip_count, _PORT_MAP)

    if isinstance(inner, Vec):
        if name is None:
            raise ValueError("Vec port must have a name (used as prefix)")
        validate_identifier(name, "port name")
        if isinstance(inner.typ, Bundle) or (
            isinstance(inner.typ, type) and issubclass(inner.typ, Bundle)
        ):
            return _expand_vec(InputPort, inner, name, flip_count)
        raise TypeError(
            f"IO(Vec({inner.typ.__name__}, ...)) requires a direction marker. "
            f"Use IO(Input(Vec(...)), name=...) or IO(Output(Vec(...)), name=...)."
        )

    effective_marker = _flip_marker(type(inner), flip_count)

    typ = inner.typ
    port_cls = _PORT_MAP[effective_marker]

    if isinstance(typ, Vec):
        return _expand_vec(port_cls, typ, name)

    name = _resolve_port_name(typ, name)
    if name is None:
        raise ValueError("Port must have a name")
    validate_identifier(name, "port name")
    return port_cls(typ, name, comment)


class Wire(Node):
    def __new__(cls, typ=None, name: str = None, comment: str = None):
        if isinstance(typ, Vec):
            return _expand_vec(Wire, typ, name)
        if isinstance(typ, Bundle):
            return _expand_bundle(typ, name, 0)
        return super().__new__(cls)

    def __init__(self, typ=None, name: str = None, comment: str = None):
        if isinstance(typ, Vec):
            return
        if isinstance(typ, Bundle):
            return

        from .connect import Builder

        if name is None and hasattr(typ, "name"):
            name = typ.name
        if name is None:
            name = Builder.current_module()._get_unique_wire_auto_name()
        validate_identifier(name, "wire name")
        self.typ = typ
        super().__init__(name, comment)


def _expand_reg_bundle(bundle_instance, name, init, clk, rst):
    """Expand a Bundle into flat Reg nodes. Returns a BundleProxy."""
    bundle_cls = type(bundle_instance) if isinstance(bundle_instance, Bundle) else bundle_instance
    if name is None:
        name = bundle_cls.__name__.lower()
    fields = _get_bundle_fields(bundle_instance)

    result = {}
    for field_name, field_val in fields:
        field_name_full = f"{name}_{field_name}"

        if isinstance(field_val, (InputType, OutputType, InoutType)):
            typ = field_val.typ
            if isinstance(typ, Vec):
                elements = []
                for i in range(typ.depth):
                    elem = Reg(
                        typ.typ,
                        init=init,
                        clk=clk,
                        rst=rst,
                        name=f"{field_name_full}_{i}",
                    )
                    elements.append(elem)
                result[field_name] = VecProxy(elements, typ.typ, typ.depth)
            else:
                result[field_name] = Reg(typ, init=init, clk=clk, rst=rst, name=field_name_full)

        elif isinstance(field_val, type) and issubclass(field_val, Bundle):
            result[field_name] = _expand_reg_bundle(field_val, field_name_full, init, clk, rst)

    return BundleProxy(result)


class Reg(Node):
    """Base register class with clock/reset resolution."""

    def __new__(cls, typ, init=None, clk=None, rst=None, name=None, optimize=True, comment=None):
        if isinstance(typ, Bundle):
            return _expand_reg_bundle(typ, name, init, clk, rst)
        return super().__new__(cls)

    def __init__(
        self,
        typ,
        init=None,
        clk: Node = None,
        rst: Node = None,
        name: str = None,
        optimize: bool = True,
        comment: str = None,
    ):
        if isinstance(typ, Bundle):
            return
        
        # Get module from Builder context before calling super().__init__
        from .connect import Builder
        module = Builder.current_module()
        
        # Auto-generate name if not provided
        if name is None:
            name = module._get_unique_reg_name()
        
        validate_identifier(name, "reg name")
        super().__init__(name, comment)
        self.typ = typ
        self.next = None
        self._optimize = optimize

        # Validate typ is a valid type
        self._validate_type(typ)

        # Convert init to Literal if int, store EnumVal as-is
        from .types import EnumVal

        if isinstance(init, int):
            from .utils import get_width

            width = get_width(self.typ)
            self.init = Literal(init, width)
        elif isinstance(init, (EnumVal, Literal)):
            self.init = init
        else:
            self.init = init

        # Resolve clock - ERROR if none available
        self._clk = clk or self._module._implicit_clock
        if not self._clk:
            raise RuntimeError(
                f"Reg {self.name!r} has no clock defined. "
                "Provide clk= parameter or define a Clock input first."
            )

        # Resolve reset (optional)
        self._rst = rst or self._module._implicit_reset

    def _validate_type(self, typ):
        """Validate that typ is a valid register type."""
        if typ is None:
            raise TypeError(
                f"Reg {self.name!r} has no type. Provide a valid type (Bits, Bool, Enum, etc.)."
            )
        # Check for Bits, UInt, SInt, or Bool
        if isinstance(typ, (Bits, UInt, SInt, Bool)):
            return
        # Check for Vec
        if isinstance(typ, Vec):
            return
        # Check for Bundle
        if isinstance(typ, Bundle):
            return
        # Check for Enum (sublass of PlaneEnum)
        from .types import PlaneEnum

        if isinstance(typ, type) and issubclass(typ, PlaneEnum):
            return
        raise TypeError(
            f"Reg {self.name!r} has invalid type {typ!r}. "
            "Expected Bits, Bool, Enum, or similar type."
        )

    def __matmul__(self, source):
        """When reg @= expr, set the next value and update drivers/loads."""
        from .control import AlwaysCombContext
        from .utils import get_width

        if (
            self._module._conditional_stack
            and isinstance(self._module._conditional_stack[0], AlwaysCombContext)
        ):
            module_name = self._module._graph.module_name
            raise RuntimeError(
                f"Reg {self.name!r} assigned inside AlwaysComb context in module "
                f"{module_name!r}.\n"
                f"Reg is for sequential logic (always_ff). For combinational logic, "
                f"use Wire.\n"
                f"Example:\n"
                f"  # Wrong:\n"
                f"  with AlwaysComb():\n"
                f"      my_reg @= some_value\n"
                f"\n"
                f"  # Right:\n"
                f"  my_wire = Wire(Bits(8))\n"
                f"  with AlwaysComb():\n"
                f"      my_wire @= some_value\n"
                f"  my_reg @= my_wire"
            )

        # Auto-convert int to Literal (EnumVal already handled by PlaneEnum)
        if isinstance(source, int):
            source = Literal(source, get_width(self.typ))
        elif isinstance(source, Literal) and source.width is None:
            source.width = get_width(self.typ)
        self.next = source
        self.drivers = [source]
        if hasattr(source, "loads"):
            source.loads.append(self)
        return self

    def _emit_init_value(self) -> str:
        """Emit the init/reset value for this reg."""
        from .types import EnumVal
        from .utils import get_width

        if self.init and isinstance(self.init, Literal):
            width = self.init.width or get_width(self.typ)
            return f"{width}'d{self.init.value}"
        if self.init and isinstance(self.init, EnumVal):
            from .emit import _emit_expr
            return _emit_expr(self.init)
        # Default to 0
        width = get_width(self.typ)
        return f"{width}'d0"


class RegNext(Reg):
    """Register with explicit next value (D input to flop)."""

    def __init__(
        self,
        next: Node,
        init=None,
        clk: Node = None,
        rst: Node = None,
        name: str = None,
        optimize: bool = True,
        comment: str = None,
    ):
        from .types import EnumVal

        typ = getattr(next, "typ", None) or (next.enum_type if isinstance(next, EnumVal) else None)
        super().__init__(typ=typ, init=init, clk=clk, rst=rst, name=name, optimize=optimize, comment=comment)

        self.next = next
        self.drivers = [next]
        if hasattr(next, "loads"):
            next.loads.append(self)


class Literal(Node):
    def __init__(self, value: int, width: int = None):
        super().__init__()
        self.value = value
        self.width = width


def _node_width(node):
    """Get width of a node for internal use during construction."""
    if hasattr(node, "width") and node.width is not None:
        return node.width
    if hasattr(node, "typ") and node.typ:
        from .utils import get_width
        return get_width(node.typ)
    return 1


def _wrap_int(val, other_node):
    """Wrap an int in a Literal, inferring width from the other operand."""
    if isinstance(val, int):
        width = _node_width(other_node)
        return Literal(val, width)
    return val


class BinOp(Node):
    def __init__(self, op: str, a: Node, b: Node):
        super().__init__()
        self.op = op
        a = _wrap_int(a, b)
        b = _wrap_int(b, a)
        self.drivers = [a, b]
        if hasattr(a, "loads"):
            a.loads.append(self)
        if hasattr(b, "loads"):
            b.loads.append(self)
        self.width = 1 if op in {"eq", "ne", "lt", "le", "gt", "ge"} else max(_node_width(a), _node_width(b))


class UnaryOp(Node):
    def __init__(self, op: str, a: Node):
        super().__init__()
        self.op = op
        self.drivers = [a]
        if hasattr(a, "loads"):
            a.loads.append(self)
        self.width = _node_width(a)


class Mux(Node):
    def __init__(self, sel: Node, then_: Node, else_: Node):
        super().__init__()
        then_ = _wrap_int(then_, else_)
        else_ = _wrap_int(else_, then_)
        self.drivers = [sel, then_, else_]
        if hasattr(sel, "loads"):
            sel.loads.append(self)
        if hasattr(then_, "loads"):
            then_.loads.append(self)
        if hasattr(else_, "loads"):
            else_.loads.append(self)
        self.width = max(_node_width(then_), _node_width(else_))


class Cat(Node):
    def __init__(self, *parts: Node):
        super().__init__()
        self.parts = parts
        for part in parts:
            self.drivers.append(part)
            if hasattr(part, "loads"):
                part.loads.append(self)
        self.width = sum(_node_width(p) for p in parts)


class Slice(Node):
    def __init__(self, expr: Node, hi: int, lo: int):
        super().__init__()
        self.expr = expr
        self.hi = hi
        self.lo = lo
        self.width = hi - lo + 1
        expr.loads.append(self)


class Index(Node):
    def __init__(self, expr: Node, index: int):
        super().__init__()
        self.expr = expr
        self.index = index
        self.width = 1
        expr.loads.append(self)


class _ExtendBase(Node):
    """Base class for ZeroExtend/SignExtend."""

    _op = None

    def __init__(self, expr: Node, width: int):
        super().__init__()
        self.expr = expr
        self.width = width
        self.drivers = [expr]
        expr.loads.append(self)


class ZeroExtend(_ExtendBase):
    _op = "zero"


class SignExtend(_ExtendBase):
    _op = "sign"


class Replicate(Node):
    """Replicate expression: {count{expr}}."""

    def __init__(self, expr: Node, count: int):
        super().__init__()
        from .utils import get_width

        self.expr = expr
        self.count = count
        self.width = (get_width(expr.typ) if hasattr(expr, "typ") else expr.width) * count
        self.drivers = [expr]
        expr.loads.append(self)


class ReductionOp(Node):
    """Reduction operator: AND, OR, XOR across all bits."""

    def __init__(self, op: str, expr: Node):
        super().__init__()
        self.op = op
        self.expr = expr
        self.drivers = [expr]
        self.width = 1
        expr.loads.append(self)


def AndR(expr: Node) -> ReductionOp:
    return ReductionOp("and", expr)


def OrR(expr: Node) -> ReductionOp:
    return ReductionOp("or", expr)


def XorR(expr: Node) -> ReductionOp:
    return ReductionOp("xor", expr)


class _CastBase(Node):
    """Base class for SIntCast/UIntCast."""

    _op = None

    def __init__(self, expr: Node):
        super().__init__()
        self.expr = expr
        self.drivers = [expr]
        self.width = _node_width(expr)
        expr.loads.append(self)


class SIntCast(_CastBase):
    """Cast expression to signed: $signed(expr)."""

    _op = "signed"


class UIntCast(_CastBase):
    """Cast expression to unsigned: $unsigned(expr)."""

    _op = "unsigned"


def asSInt(expr: Node) -> SIntCast:
    return SIntCast(expr)


def asUInt(expr: Node) -> UIntCast:
    return UIntCast(expr)


def zext(expr: Node, width: int) -> ZeroExtend:
    return ZeroExtend(expr, width)


def sext(expr: Node, width: int) -> SignExtend:
    return SignExtend(expr, width)


def instance(
    module: "Module",
    name: str = None,
    params: tuple = (),
    count=1,
) -> "Module":
    """Elaborate module and add to parent's children.

    Args:
        module: Child module to instantiate
        name: Optional instance name. If not provided, uses module class name.
              If name conflicts, auto-appends suffix (_1, _2, etc.)
        params: Parameter overrides as ((name, value), ...) tuples.
                Value can be int or Parameter.
        count: Number of instances (for Verilog array instances). Can be int
               (>= 1) or Parameter. When count > 1, emits `inst_name[N-1:0]`.
               Port connections pass through unchanged — the Verilog tool
               handles width slicing/broadcasting.

    Returns:
        The elaborated module with instance name set
    """
    from .base import Parameter

    parent = Builder.current_module()
    if parent:
        parent._children.append(module)

    # Set instance name with auto-disambiguation
    base_name = module._graph.module_name.lower()
    module._instance_name = parent._get_unique_instance_name(base_name, name)

    # Validate count
    if isinstance(count, int):
        if count < 1:
            raise ValueError(f"count must be >= 1 for instance '{module._instance_name}' ({module._graph.module_name}), got {count}")
    elif not isinstance(count, Parameter):
        raise TypeError(f"count must be int or Parameter for instance '{module._instance_name}' ({module._graph.module_name}), got {type(count).__name__}")

    # Store parameter overrides for emission
    module._param_overrides = dict(params) if params else None

    # Store instance count for array instance emission
    module._instance_count = count

    Builder.push(module)
    module.elaborate()
    Builder.pop()
    module._validate()
    return module


class Attribute:
    """Base class for annotations attached to nodes.

    Subclass and override `content()` to return the string to emit
    before the node's declaration. The emitter prints it as-is,
    so the user is responsible for formatting (attributes, comments, etc.).

    Example:
        class DontTouchAttribute(Attribute):
            def content(self) -> str:
                return '(* dont_touch = "true" *)'

        self.w = Wire(Bits(8), name="w")
        DontTouchAttribute(self.w)  # auto-registers with the node
    """

    def __init__(self, node: Node):
        self.node = node
        node._attributes.append(self)

    def content(self) -> str:
        """Return the string to emit before the declaration."""
        raise NotImplementedError


# Add operators to Node class
# NOTE: __eq__, __ne__, __lt__, etc. are overridden to return BinOp nodes (DSL comparison).
# They do NOT return booleans. Use `is` for identity checks.
Node._operators_added = False


def _add_operators():
    if Node._operators_added:
        return

    Node.__add__ = lambda self, other: BinOp("add", self, other)
    Node.__sub__ = lambda self, other: BinOp("sub", self, other)
    Node.__mul__ = lambda self, other: BinOp("mul", self, other)
    Node.__radd__ = lambda self, other: BinOp("add", other, self)
    Node.__rsub__ = lambda self, other: BinOp("sub", other, self)
    Node.__rmul__ = lambda self, other: BinOp("mul", other, self)
    Node.__truediv__ = lambda self, other: BinOp("div", self, other)
    Node.__floordiv__ = lambda self, other: BinOp("div", self, other)
    Node.__mod__ = lambda self, other: BinOp("mod", self, other)
    Node.__neg__ = lambda self: UnaryOp("neg", self)

    Node.__and__ = lambda self, other: BinOp("and", self, other)
    Node.__or__ = lambda self, other: BinOp("or", self, other)
    Node.__xor__ = lambda self, other: BinOp("xor", self, other)
    Node.__rand__ = lambda self, other: BinOp("and", other, self)
    Node.__ror__ = lambda self, other: BinOp("or", other, self)
    Node.__rxor__ = lambda self, other: BinOp("xor", other, self)
    Node.__invert__ = lambda self: UnaryOp("not", self)

    Node.__eq__ = lambda self, other: BinOp("eq", self, other)
    Node.__ne__ = lambda self, other: BinOp("ne", self, other)
    Node.__lt__ = lambda self, other: BinOp("lt", self, other)
    Node.__le__ = lambda self, other: BinOp("le", self, other)
    Node.__gt__ = lambda self, other: BinOp("gt", self, other)
    Node.__ge__ = lambda self, other: BinOp("ge", self, other)

    Node.__lshift__ = lambda self, other: BinOp("lshift", self, other)
    Node.__rshift__ = lambda self, other: BinOp("rshift", self, other)

    def _getitem(self, key):
        if isinstance(key, slice):
            return Slice(self, key.start, key.stop)
        return Index(self, key)

    Node.__getitem__ = _getitem

    Node._operators_added = True


_add_operators()
