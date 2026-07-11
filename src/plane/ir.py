from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# =============================================================================
# Expression IR (frozen for structural equality)
# =============================================================================

# Forward type alias — IRExpr resolves at runtime to the union of all IR
# expression dataclasses below. Using Any here satisfies static analysis.
IRExpr = Any


@dataclass(frozen=True)
class IRRef:
    name: str


@dataclass(frozen=True)
class IRLit:
    width: int
    value: int


@dataclass(frozen=True)
class IRBinOp:
    op: str
    left: IRExpr
    right: IRExpr


@dataclass(frozen=True)
class IRUnaryOp:
    op: str
    operand: IRExpr


@dataclass(frozen=True)
class IRMux:
    sel: IRExpr
    then_: IRExpr
    else_: IRExpr


@dataclass(frozen=True)
class IRCat:
    parts: tuple[IRExpr, ...]


@dataclass(frozen=True)
class IRSlice:
    expr: IRExpr
    hi: int
    lo: int


@dataclass(frozen=True)
class IRIndex:
    expr: IRExpr
    index: int


@dataclass(frozen=True)
class IRZeroExtend:
    expr: IRExpr
    width: int


@dataclass(frozen=True)
class IRSignExtend:
    expr: IRExpr
    width: int


@dataclass(frozen=True)
class IRReductionOp:
    op: str
    operand: IRExpr


@dataclass(frozen=True)
class IRSignedCast:
    operand: IRExpr


@dataclass(frozen=True)
class IRUnsignedCast:
    operand: IRExpr


# =============================================================================
# Module Structure IR
# =============================================================================


@dataclass(frozen=True)
class IRPort:
    name: str
    direction: str  # "input" / "output" / "inout"
    width: int


@dataclass(frozen=True)
class IRWire:
    name: str
    width: int


@dataclass(frozen=True)
class IRReg:
    name: str
    width: int
    init: str


@dataclass(frozen=True)
class IRFlatAssign:
    sink: IRExpr
    src: IRExpr


@dataclass(frozen=True)
class IRInstance:
    module_name: str
    inst_name: str
    ports: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class IRWhen:
    condition: IRExpr | None  # None for Otherwise
    body: tuple[IRBodyItem, ...]


@dataclass(frozen=True)
class IRSwitch:
    select: IRExpr
    cases: tuple[tuple[int, tuple[IRBodyItem, ...]], ...]
    default: tuple[IRBodyItem, ...]


@dataclass(frozen=True)
class IRAlwaysComb:
    body: tuple[IRBodyItem, ...]


# Forward declaration for body items (IRFlatAssign | IRWhen | IRSwitch)
IRBodyItem = Any


@dataclass(frozen=True)
class IRModule:
    module_name: str
    ports: tuple[IRPort, ...]
    wires: tuple[IRWire, ...]
    regs: tuple[IRReg, ...]
    flat_assigns: tuple[IRFlatAssign, ...]
    always_comb: tuple[IRAlwaysComb, ...]
    reg_blocks_sv: tuple[str, ...]
    instances: tuple[IRInstance, ...]


# =============================================================================
# Build IR from elaborated Module
# =============================================================================


def _to_ir_expr(node) -> IRExpr:
    """Convert a Node to an IR expression."""
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
        SignExtend,
        SIntCast,
        Slice,
        UIntCast,
        UnaryOp,
        Wire,
        ZeroExtend,
    )
    from .types import EnumVal

    if node is None:
        return IRLit(1, 0)

    if isinstance(node, (InputPort, OutputPort, InoutPort, Wire)):
        return IRRef(node.name)

    if isinstance(node, Reg):
        return IRRef(node.name)

    if isinstance(node, RegNext):
        return IRRef(node.name)

    if isinstance(node, Literal):
        return IRLit(node.width or 1, node.value)

    if isinstance(node, EnumVal):
        return IRLit(node.width, node.value)

    if isinstance(node, BinOp):
        return IRBinOp(
            node.op,
            _to_ir_expr(node.drivers[0]),
            _to_ir_expr(node.drivers[1]),
        )

    if isinstance(node, UnaryOp):
        return IRUnaryOp(node.op, _to_ir_expr(node.drivers[0]))

    if isinstance(node, Mux):
        return IRMux(
            _to_ir_expr(node.drivers[0]),
            _to_ir_expr(node.drivers[1]),
            _to_ir_expr(node.drivers[2]),
        )

    if isinstance(node, Cat):
        return IRCat(tuple(_to_ir_expr(p) for p in node.parts))

    if isinstance(node, Slice):
        return IRSlice(_to_ir_expr(node.expr), node.hi, node.lo)

    if isinstance(node, Index):
        return IRIndex(_to_ir_expr(node.expr), node.index)

    if isinstance(node, ZeroExtend):
        return IRZeroExtend(_to_ir_expr(node.expr), node.width)

    if isinstance(node, SignExtend):
        return IRSignExtend(_to_ir_expr(node.expr), node.width)

    if isinstance(node, ReductionOp):
        return IRReductionOp(node.op, _to_ir_expr(node.expr))

    if isinstance(node, SIntCast):
        return IRSignedCast(_to_ir_expr(node.expr))

    if isinstance(node, UIntCast):
        return IRUnsignedCast(_to_ir_expr(node.expr))

    if hasattr(node, "name"):
        return IRRef(node.name)

    return IRLit(1, 0)


def _to_ir_body(assignments) -> tuple[IRBodyItem, ...]:
    """Convert a list of conditional assignments to IR body items."""
    from .control import (
        CaseContext,
        DefaultContext,
        ElseWhenContext,
        OtherwiseContext,
        SwitchContext,
        WhenContext,
    )

    result = []
    for item in assignments:
        if isinstance(item, tuple):
            sink, source = item
            result.append(IRFlatAssign(_to_ir_expr(sink), _to_ir_expr(source)))
        elif isinstance(item, (WhenContext, ElseWhenContext, OtherwiseContext)):
            cond = _to_ir_expr(item.condition) if item.condition is not None else None
            body = _to_ir_body(item.assignments)
            result.append(IRWhen(cond, body))
        elif isinstance(item, SwitchContext):
            sel = _to_ir_expr(item.select)
            cases = []
            default_body = ()
            for sub in item.assignments:
                if isinstance(sub, CaseContext):
                    case_body = _to_ir_body(sub.assignments)
                    cases.append((sub.value, case_body))
                elif isinstance(sub, DefaultContext):
                    default_body = _to_ir_body(sub.assignments)
            result.append(IRSwitch(sel, tuple(cases), default_body))
    return tuple(result)


def _to_ir_always_comb(ctx) -> IRAlwaysComb:
    """Convert an AlwaysCombContext to IR."""
    return IRAlwaysComb(_to_ir_body(ctx.assignments))


def build_ir(mod) -> IRModule:
    """Build a frozen IRModule from an elaborated Module."""
    from .nodes import (
        InoutPort,
        InputPort,
        OutputPort,
        Reg,
        RegNext,
        Wire,
    )
    from .utils import get_width

    graph = mod._graph

    # Collect ports
    ports = []
    for node in graph.nodes:
        if isinstance(node, InputPort):
            ports.append(IRPort(node.name, "input", get_width(node.typ)))
        elif isinstance(node, OutputPort):
            ports.append(IRPort(node.name, "output", get_width(node.typ)))
        elif isinstance(node, InoutPort):
            ports.append(IRPort(node.name, "inout", get_width(node.typ)))

    # Collect wires
    wires = []
    for node in graph.nodes:
        if isinstance(node, Wire):
            wires.append(IRWire(node.name, get_width(node.typ)))

    # Collect regs
    regs = []
    for node in graph.nodes:
        if isinstance(node, (Reg, RegNext)):
            init = node._emit_init_value()
            regs.append(IRReg(node.name, get_width(node.typ), init))

    # Collect flat assignments (skip RegNext)
    flat_assigns = []
    for sink, source in graph.connections:
        if isinstance(sink, RegNext):
            continue
        flat_assigns.append(IRFlatAssign(_to_ir_expr(sink), _to_ir_expr(source)))

    # AlwaysComb blocks — convert to structured IR
    always_comb = ()
    if hasattr(mod, "_always_comb_blocks") and mod._always_comb_blocks:
        always_comb = tuple(_to_ir_always_comb(ac) for ac in mod._always_comb_blocks)

    # Reg blocks — emit as canonical SV strings
    reg_blocks_sv = ()
    if regs:
        from .emit import _emit_reg_blocks

        reg_lines = _emit_reg_blocks(mod, graph)
        if reg_lines:
            reg_blocks_sv = ("\n".join(reg_lines),)

    # Instances
    instances = []
    for child in mod._children:
        child_ports = []
        for node in child._graph.nodes:
            if isinstance(node, InputPort) and node.drivers:
                src_name = getattr(node.drivers[0], "name", "_unknown")
                child_ports.append((node.name, src_name))
            elif isinstance(node, OutputPort) and node.loads:
                dst_name = getattr(node.loads[0], "name", "_unknown")
                child_ports.append((node.name, dst_name))

        instances.append(
            IRInstance(
                child._graph.module_name,
                child._instance_name or child._graph.module_name.lower(),
                tuple(child_ports),
            )
        )

    return IRModule(
        module_name=graph.module_name,
        ports=tuple(ports),
        wires=tuple(wires),
        regs=tuple(regs),
        flat_assigns=tuple(flat_assigns),
        always_comb=always_comb,
        reg_blocks_sv=reg_blocks_sv,
        instances=tuple(instances),
    )
