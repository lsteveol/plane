from .connect import Builder
from .types import Clock, Reset
from .utils import check_width_mismatch, get_width


class Node:
    """Base class for all hardware nodes."""

    def __init__(self, name: str = None, comment: str = None):
        self._module = Builder.current_module()
        if not self._module:
            raise RuntimeError("Node created outside of Module context")

        self.comment: str = comment

        # Generate auto-name if not provided (for internal nodes)
        if name is None:
            type_name = self.__class__.__name__.lower()
            name = self._module._get_auto_name(type_name)

        # Check for name collision BEFORE appending to graph
        for node in self._module._graph.nodes:
            if node.name == name:
                raise ValueError(f"Node name {name!r} is already used in this module")

        self.name = name

        self.drivers: list[Node] = []
        self.loads: list[Node] = []
        self._attributes: list = []
        self._module._graph.nodes.append(self)

        # Auto-register implicit clock/reset if this node has Clock/Reset type
        if hasattr(self, "typ") and self.typ:
            if isinstance(self.typ, Clock) and self._module._implicit_clock is None:
                self._module._implicit_clock = self
            elif isinstance(self.typ, Reset) and self._module._implicit_reset is None:
                self._module._implicit_reset = self

    def __matmul__(self, source):
        """Connection operator: self @= source assigns source to self."""
        if isinstance(source, int):
            from .nodes import Literal
            from .utils import get_width

            width = get_width(self.typ) if hasattr(self, "typ") and self.typ else None
            source = Literal(source, width)
        mod = Builder.current_module()
        if not mod:
            return self
        _connect(self, source, mod)
        return self


def _resolve_fanout(source, sink, mod):
    """Resolve fanout from a child output port.

    If source is an OutputPort from a child module, handles the connection
    (loads, drivers, intermediate wire if needed) and returns True.
    Returns False if no fanout resolution was needed (caller should proceed with normal connection).
    """
    from .nodes import OutputPort, Wire

    if not isinstance(source, OutputPort) or source._module is mod:
        return False

    if not source.loads:
        # First load — track via loads only, no graph.connections
        source.loads.append(sink)
        sink.drivers.append(source)
        return True

    # Check if there's already an intermediate wire
    existing_wire = None
    for load in source.loads:
        if isinstance(load, Wire):
            existing_wire = load
            break

    if existing_wire:
        # Wire already exists — just connect to it
        if sink._module is mod:
            mod._graph.connections.append((sink, existing_wire))
        existing_wire.loads.append(sink)
        sink.drivers.append(existing_wire)
        return True

    # First actual fanout — create intermediate wire
    # Reject fanout from array instance outputs — the intermediate wire would
    # be created with the port's type (1-bit) but the array output is sliced
    # across N instances, so the effective width is port_width × count.
    # The user must create an explicit wire with the correct width.
    inst_count = getattr(source._module, "_instance_count", 1)
    is_array_instance = isinstance(inst_count, Parameter) or (isinstance(inst_count, int) and inst_count > 1)
    if is_array_instance:
        inst_name = source._module._instance_name
        raise ConnectionError(
            f"Array instance output '{inst_name}.{source.name}' cannot drive "
            f"multiple sinks. The intermediate wire would have incorrect width. "
            f"Use an explicit wire:\n"
            f"    self.wire = Wire(UInt(<array_width>), name=\"wire\")\n"
            f"    self.wire @= {inst_name}.{source.name}\n"
            f"    self.sink1 @= self.wire\n"
            f"    self.sink2 @= self.wire"
        )

    inst_name = source._module._instance_name
    suggested_wire_name = f"_{inst_name}_{source.name}"
    wire_name = mod._get_unique_wire_name(suggested_wire_name)
    wire = Wire(source.typ, name=wire_name)

    # Redirect existing loads to the wire
    for load in source.loads[:]:
        source.loads.remove(load)
        load.drivers.remove(source)
        if load._module is mod:
            mod._graph.connections.append((load, wire))
        wire.loads.append(load)
        load.drivers.append(wire)

    # Connect wire to source via loads only (no graph.connections)
    source.loads.append(wire)
    wire.drivers.append(source)

    # Connect new sink to wire
    if sink._module is mod:
        mod._graph.connections.append((sink, wire))
    wire.loads.append(sink)
    sink.drivers.append(wire)

    return True


def _connect(sink, source, mod):
    """Shared connection logic for @= operator and assign()."""
    if mod._conditional_stack:
        ctx = mod._conditional_stack[-1]
        if hasattr(ctx, "_add_assignment"):
            ctx._add_assignment(sink, source)
        elif hasattr(ctx, "assignments"):
            ctx.assignments.append((sink, source))
        return

    if mod._when_chain is not None:
        mod._when_chain = None

    if getattr(sink, "_direction", None) == "Input" and sink._module is mod:
        raise ConnectionError(
            f"Cannot assign to input port {sink.name!r}. "
            f"Input ports are driven externally, not by internal logic."
        )

    if sink.drivers and type(sink).__name__ != "InoutPort":
        raise ConnectionError(
            f"Reassigning {sink.name!r} - already driven by {sink.drivers[0].name!r}. "
            f"Use conditional (When/Switch) to build mux, or Inout for tristate."
        )

    if _resolve_fanout(source, sink, mod):
        return

    # Skip width check for array instance sinks — the Verilog tool handles
    # width slicing/broadcasting based on connection width vs port width.
    inst_count = getattr(sink._module, "_instance_count", 1) if sink._module is not mod else 1
    is_array_instance_sink = (
        sink._module is not mod
        and (isinstance(inst_count, Parameter) or (isinstance(inst_count, int) and inst_count > 1))
    )
    if not is_array_instance_sink:
        check_width_mismatch(sink, source)

    if sink._module is mod:
        mod._graph.connections.append((sink, source))
    if hasattr(source, "loads"):
        source.loads.append(sink)
    sink.drivers.append(source)


def assign(sink, source):
    """Assign source to sink. Works on any Node, including Slice/Index."""
    mod = Builder.current_module()
    if not mod:
        return sink
    _connect(sink, source, mod)
    return sink


class Parameter:
    """Module parameter (SV `parameter`).

    Module-agnostic data object. Assign to a module attribute to register it.
    Use `int(param)` to get the concrete default value.

    Example:
        self.WIDTH = Parameter("WIDTH", 8)
        self.a = IO(Input(Bits(self.WIDTH)), name="a")
    """

    def __init__(self, name: str, default: int):
        self.name = name
        self.default = default

    def __int__(self) -> int:
        return self.default

    def __index__(self) -> int:
        return self.default

    def __add__(self, other):
        return int(self) + other

    def __radd__(self, other):
        return other + int(self)

    def __sub__(self, other):
        return int(self) - other

    def __rsub__(self, other):
        return other - int(self)

    def __mul__(self, other):
        return int(self) * other

    def __rmul__(self, other):
        return other * int(self)

    def __floordiv__(self, other):
        return int(self) // other

    def __rfloordiv__(self, other):
        return other // int(self)

    def __mod__(self, other):
        return int(self) % other

    def __lshift__(self, other):
        return int(self) << other

    def __rshift__(self, other):
        return int(self) >> other


class Graph:
    """Represents a module's hardware graph."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self.emitted_name = None
        self.nodes: list[Node] = []
        self.connections: list[tuple[Node, Node]] = []


class Module:
    """Base class for all hardware modules."""

    def __init__(self, desired_name: str = None):
        self.comment: str = None
        self._children: list[Module] = []
        self._graph = Graph(desired_name or self.__class__.__name__)
        self._conditional_stack: list = []
        self._when_chain = None
        self._switch_chain = None
        self._implicit_clock: Node = None
        self._implicit_reset: Node = None
        self._name_counters: dict = {}
        self._instance_names: list[str] = []
        self._instance_name: str = None
        self._is_blackbox = False
        self._elaborated = False
        self._reg_counter = 0
        self._wire_counter = 0

    def _get_auto_name(self, type_name: str) -> str:
        """Generate auto-name for unnamed node."""
        counter = self._name_counters.get(type_name, 0)
        self._name_counters[type_name] = counter + 1
        return f"{type_name}_{counter}"

    def _get_unique_reg_name(self) -> str:
        """Generate a unique register name with conflict checking."""
        used_names = {node.name for node in self._graph.nodes}
        
        while True:
            name = f"auto_reg_{self._reg_counter}"
            self._reg_counter += 1
            if name not in used_names:
                return name

    def _get_unique_wire_auto_name(self) -> str:
        """Generate a unique wire name with conflict checking."""
        used_names = {node.name for node in self._graph.nodes}

        while True:
            name = f"auto_wire_{self._wire_counter}"
            self._wire_counter += 1
            if name not in used_names:
                return name

    def _get_unique_instance_name(self, base_name: str, explicit: str = None) -> str:
        """Get a unique instance name by checking against used names."""
        name = explicit or base_name

        if name not in self._instance_names:
            self._instance_names.append(name)
            return name

        counter = 1
        while True:
            candidate = f"{name}_{counter}"
            if candidate not in self._instance_names:
                self._instance_names.append(candidate)
                return candidate
            counter += 1

    def _get_unique_wire_name(self, suggested_name: str) -> str:
        """Get a unique wire name by checking against existing node names."""
        name = suggested_name
        used_names = {node.name for node in self._graph.nodes}

        if name not in used_names:
            return name

        counter = 1
        while True:
            candidate = f"{name}_{counter}"
            if candidate not in used_names:
                return candidate
            counter += 1

    def set_clock(self, clk: "Node"):
        """Set implicit clock for this module."""
        self._implicit_clock = clk

    def set_reset(self, rst: "Node"):
        """Set implicit reset for this module."""
        self._implicit_reset = rst

    def elaborate(self):
        """User implements this to create hardware."""
        raise NotImplementedError()

    def _validate(self):
        """Validate module graph after elaboration."""
        from .nodes import OutputPort, Reg

        # Check for Reg without next value
        for node in self._graph.nodes:
            if isinstance(node, Reg) and node.next is None:
                raise RuntimeError(
                    f"Reg {node.name!r} has no next value assigned. "
                    "Use `reg @= next_value` to set the next value."
                )

        # Collect all nodes assigned in conditional contexts
        assigned_in_conditionals = set()

        def _collect(ctx):
            for item in ctx.assignments:
                if isinstance(item, tuple):
                    assigned_in_conditionals.add(item[0])
                elif hasattr(item, "assignments"):
                    _collect(item)

        if hasattr(self, "_always_comb_blocks"):
            for ac in self._always_comb_blocks:
                _collect(ac)

        # Check for undriven output ports (skip child instances - their outputs
        # are driven by parent connections)
        if self._instance_name is None:
            from .nodes import Index, Slice

            for node in self._graph.nodes:
                if not isinstance(node, OutputPort):
                    continue

                # Fully driven by direct assignment
                if node.drivers or node in assigned_in_conditionals:
                    continue

                # Look for partial drives (Slice/Index of this port)
                partial_drives = []
                for n in self._graph.nodes:
                    if isinstance(n, (Slice, Index)) and n.expr is node:
                        if n.drivers or n in assigned_in_conditionals:
                            partial_drives.append(n)

                if not partial_drives:
                    raise RuntimeError(
                        f"Output port {node.name!r} is undriven. "
                        "Assign a value using `port @= expr`."
                    )

                # Check bit coverage from partial drives
                width = get_width(node.typ)
                covered = set()
                for p in partial_drives:
                    if isinstance(p, Index):
                        covered.add(p.index)
                    else:
                        for bit in range(p.lo, p.hi + 1):
                            covered.add(bit)

                uncovered = set(range(width)) - covered
                if uncovered:
                    raise RuntimeError(
                        f"Output port {node.name!r} has uncovered bits: {sorted(uncovered)}. "
                        "All bits must be assigned."
                    )

    def _validate_input_ports(self):
        """Check for undriven input ports on all instantiated children."""
        from .nodes import InputPort

        for child in self._children:
            for node in child._graph.nodes:
                if isinstance(node, InputPort) and not node.drivers:
                    raise RuntimeError(
                        f"Input port {node.name!r} on {child._graph.module_name} is undriven. "
                        "Connect it to a source using `port @= expr`."
                    )

    def suggest_name(self, name: str):
        """Override the module's emission name."""
        self._graph.module_name = name
        return self

    def _push_context(self, ctx):
        """Enter a conditional context."""
        self._conditional_stack.append(ctx)
        if ctx.__class__.__name__ == "WhenContext" and self._when_chain is None:
            self._when_chain = ctx
        if ctx.__class__.__name__ == "SwitchContext" and self._switch_chain is None:
            self._switch_chain = ctx

    def _pop_context(self):
        """Exit current conditional context."""
        if self._conditional_stack:
            return self._conditional_stack.pop()
        return None

    def _get_current_context(self):
        """Get current conditional context."""
        return self._conditional_stack[-1] if self._conditional_stack else None

    def _get_when_chain(self):
        """Get the root WhenContext for else chain."""
        return self._when_chain

    def _get_switch_chain(self):
        """Get the root SwitchContext for default chain."""
        return self._switch_chain


class BlackBox(Module):
    """External module — elaborates ports but emitter skips module body."""

    def __init__(self):
        super().__init__()
        self._is_blackbox = True
