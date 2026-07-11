from dataclasses import dataclass, field

from .connect import Builder
from .nodes import Node
from .types import EnumVal


@dataclass
class AlwaysCombAssignments:
    """Wrapper for conditional assignments with nice repr."""

    _items: list = field(default_factory=list)

    def append(self, item):
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, i):
        return self._items[i]


class ConditionalContext:
    """Base class for conditional contexts (When, Switch, AlwaysComb)."""

    def __init__(self):
        self.comment: str = None
        self.assignments = AlwaysCombAssignments()
        self.parent = None
        self.module = Builder.current_module()

    def _add_assignment(self, sink: Node, source: Node):
        """Add an assignment from within this context."""
        self.assignments.append((sink, source))

    def __enter__(self):
        self.module._push_context(self)
        return self

    def __exit__(self, *args):
        # Pop from stack
        self.module._pop_context()

        # Add THIS context to parent (for nesting)
        parent = self.module._get_current_context()
        if parent and hasattr(parent, "assignments"):
            parent.assignments.append(self)


class AlwaysCombContext(ConditionalContext):
    """AlwaysComb context - collects assignments for always_comb block."""

    def __exit__(self, *args):
        self.module._pop_context()
        # Store in module for emit (don't add to parent - this is top-level)
        if not hasattr(self.module, "_always_comb_blocks"):
            self.module._always_comb_blocks = []
        self.module._always_comb_blocks.append(self)


class WhenContext(ConditionalContext):
    """When/ElseWhen/Otherwise context."""

    def __init__(self, condition: Node = None, parent: ConditionalContext = None):
        super().__init__()
        self.condition = condition  # None for Otherwise
        self.parent = parent


class ElseWhenContext(WhenContext):
    """ElseWhen context."""

    pass


class OtherwiseContext(WhenContext):
    """Otherwise context."""

    def __init__(self, parent: ConditionalContext = None):
        super().__init__(condition=None, parent=parent)


class SwitchContext(ConditionalContext):
    """Switch/Case/Default context."""

    def __init__(self, select: Node):
        super().__init__()
        self.select = select
        self.cases: dict = {}
        self.default: list = []  # Default() assignments


class CaseContext(ConditionalContext):
    """Case(value) context inside Switch."""

    def __init__(self, switch_ctx: SwitchContext, value, enum_info=None):
        super().__init__()
        self.value = value
        self.switch_ctx = switch_ctx
        self.enum_info = enum_info  # (enum_type, value_name) or None


class DefaultContext(ConditionalContext):
    """Default() context inside Switch."""

    def __init__(self, switch_ctx: SwitchContext):
        super().__init__()
        self.switch_ctx = switch_ctx


# Entry point functions


def _check_in_always_comb():
    """Ensure AlwaysComb is the first (outermost) context in the stack."""
    mod = Builder.current_module()
    if not mod._conditional_stack:
        raise RuntimeError("When/Switch must be used inside AlwaysComb block")
    if isinstance(mod._conditional_stack[0], AlwaysCombContext):
        return
    raise RuntimeError("When/Switch must be used inside AlwaysComb block")


def When(condition: Node, comment: str = None):
    """When(condition) - if block."""
    _check_in_always_comb()
    ctx = WhenContext(condition)
    ctx.comment = comment
    return ctx


def ElseWhen(condition: Node, comment: str = None):
    """ElseIf(condition) - else if block."""
    mod = Builder.current_module()
    parent = mod._get_when_chain()
    if parent is None:
        raise RuntimeError("ElseWhen must follow When")
    ctx = ElseWhenContext(condition, parent)
    ctx.comment = comment
    return ctx


def Otherwise(comment: str = None):
    """Otherwise() - else block."""
    mod = Builder.current_module()
    parent = mod._get_when_chain()
    if parent is None:
        raise RuntimeError("Otherwise must follow When or ElseWhen")
    ctx = OtherwiseContext(parent)
    ctx.comment = comment
    return ctx


def Switch(select: Node, comment: str = None):
    """Switch(select) - case statement."""
    _check_in_always_comb()
    ctx = SwitchContext(select)
    ctx.comment = comment
    return ctx


def Case(value, comment: str = None):
    """Case(value) - specific case value."""
    mod = Builder.current_module()
    parent = mod._get_current_context() if mod._conditional_stack else None
    if parent is None or not isinstance(parent, SwitchContext):
        raise RuntimeError("Case must be inside Switch")
    enum_info = (value.enum_type, value.value_name) if isinstance(value, EnumVal) else None
    case_value = value.value if isinstance(value, EnumVal) else value
    ctx = CaseContext(parent, case_value, enum_info)
    ctx.comment = comment
    return ctx


def Default(comment: str = None):
    """Default() - default case."""
    mod = Builder.current_module()
    parent = None
    for ctx in mod._conditional_stack:
        if isinstance(ctx, SwitchContext):
            parent = ctx
            break
    if parent is None:
        raise RuntimeError("Default must be inside Switch")
    ctx = DefaultContext(parent)
    ctx.comment = comment
    return ctx


def AlwaysComb(comment: str = None):
    """AlwaysComb() - always_comb block context."""
    ctx = AlwaysCombContext()
    ctx.comment = comment
    return ctx


class ClockResetContext:
    """Context manager to temporarily override implicit clock/reset."""

    def __init__(self, clk: Node = None, rst: Node = None):
        self.clk = clk
        self.rst = rst
        self._saved_clk = None
        self._saved_rst = None

    def __enter__(self):
        mod = Builder.current_module()
        self._saved_clk = mod._implicit_clock
        self._saved_rst = mod._implicit_reset
        if self.clk:
            mod._implicit_clock = self.clk
        if self.rst:
            mod._implicit_reset = self.rst
        return self

    def __exit__(self, *args):
        mod = Builder.current_module()
        mod._implicit_clock = self._saved_clk
        mod._implicit_reset = self._saved_rst


def ClockReset(clk: Node = None, rst: Node = None):
    """Context manager to set implicit clock/reset."""
    return ClockResetContext(clk, rst)
