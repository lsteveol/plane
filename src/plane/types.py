from enum import Enum


class ResetType(Enum):
    Sync = "sync"
    Async = "async"


class ResetPolarity(Enum):
    ActiveHigh = "active_high"
    ActiveLow = "active_low"


class GlobalClockResetDefaults:
    """Global defaults for clock/reset behavior across all modules."""

    clock_name = "clk"
    al_reset_name = "rstn"  # Active low reset name
    ah_reset_name = "rst"  # Active high reset name
    reset_type = ResetType.Async
    reset_polarity = ResetPolarity.ActiveLow


_global_defaults = GlobalClockResetDefaults()


class Clock:
    """Clock signal type marker."""

    def __init__(self, name: str = None):
        self.name = name or _global_defaults.clock_name


class Reset:
    """Base reset class with type and polarity parameters."""

    def __init__(
        self,
        reset_type: ResetType = None,
        polarity: ResetPolarity = None,
        name: str = None,
    ):
        self.reset_type = reset_type or _global_defaults.reset_type
        self.polarity = polarity or _global_defaults.reset_polarity
        self.name = name or self._get_default_name()

    def _get_default_name(self):
        if self.polarity == ResetPolarity.ActiveLow:
            return _global_defaults.al_reset_name
        return _global_defaults.ah_reset_name

    def is_async(self) -> bool:
        """Check if reset is asynchronous."""
        return self.reset_type == ResetType.Async

    def is_sync(self) -> bool:
        """Check if reset is synchronous."""
        return self.reset_type == ResetType.Sync

    def is_active_low(self) -> bool:
        """Check if reset is active low."""
        return self.polarity == ResetPolarity.ActiveLow

    def is_active_high(self) -> bool:
        """Check if reset is active high."""
        return self.polarity == ResetPolarity.ActiveHigh


class AsyncReset(Reset):
    """Async reset - forces reset_type to Async, polarity can be overridden."""

    def __init__(self, polarity: ResetPolarity = None, name: str = None):
        super().__init__(reset_type=ResetType.Async, polarity=polarity, name=name)


class SyncReset(Reset):
    """Sync reset - forces reset_type to Sync, polarity can be overridden."""

    def __init__(self, polarity: ResetPolarity = None, name: str = None):
        super().__init__(reset_type=ResetType.Sync, polarity=polarity, name=name)


class AsyncLowReset(AsyncReset):
    """Async active-low reset - fully constrained, no overrides allowed."""

    def __init__(self, name: str = None):
        super().__init__(polarity=ResetPolarity.ActiveLow, name=name)


class AsyncHighReset(AsyncReset):
    """Async active-high reset - fully constrained, no overrides allowed."""

    def __init__(self, name: str = None):
        super().__init__(polarity=ResetPolarity.ActiveHigh, name=name)


class SyncLowReset(SyncReset):
    """Sync active-low reset - fully constrained, no overrides allowed."""

    def __init__(self, name: str = None):
        super().__init__(polarity=ResetPolarity.ActiveLow, name=name)


class SyncHighReset(SyncReset):
    """Sync active-high reset - fully constrained, no overrides allowed."""

    def __init__(self, name: str = None):
        super().__init__(polarity=ResetPolarity.ActiveHigh, name=name)


class _NumericBase:
    """Base class for UInt, SInt, Bits — shared Parameter handling."""

    signed = False

    def __init__(self, width: int):
        from .base import Parameter

        if isinstance(width, Parameter):
            self.width = int(width)
            self._param = width.name
        else:
            self.width = width
            self._param = None


class UInt(_NumericBase):
    """Unsigned integer type."""

    pass


class SInt(_NumericBase):
    """Signed integer type."""

    signed = True


class Bits(_NumericBase):
    """Backward-compatible alias for UInt."""

    pass


class Bool:
    width = 1
    signed = False


class EnumVal:
    """Enum value — carries type info for named SV emission.

    Behaves like an int for comparisons but tracks enum type and value name.
    """

    __slots__ = ("enum_type", "value", "value_name", "width")

    def __init__(self, enum_type, value, value_name, width):
        self.enum_type = enum_type
        self.value = value
        self.value_name = value_name
        self.width = width

    def __int__(self):
        return self.value

    def __index__(self):
        return self.value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if isinstance(other, EnumVal):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, (EnumVal, int)):
            return self.value != int(other) if isinstance(other, EnumVal) else self.value != other
        return NotImplemented

    def __lt__(self, other):
        return self.value < int(other)

    def __le__(self, other):
        return self.value <= int(other)

    def __gt__(self, other):
        return self.value > int(other)

    def __ge__(self, other):
        return self.value >= int(other)

    def __repr__(self):
        return f"{self.enum_type.__name__}.{self.value_name}"


class _PlaneEnumMeta(type):
    """Metaclass for PlaneEnum that returns EnumVal for enum value access."""

    def __getattribute__(cls, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        enum_vals = super().__getattribute__("_enum_vals")
        if name in enum_vals:
            return enum_vals[name]
        return super().__getattribute__(name)


class PlaneEnum(metaclass=_PlaneEnumMeta):
    """Base class for user-defined enums.

    Subclass to create custom enum types. Values are stored as class attributes
    with integer values. The registry tracks all subclasses for package emission.

    Example:
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1
            DONE = 2

        self.r = Reg(MyState, name="state")
        self.r @= MyState.IDLE  # emits: state <= MyState_t::IDLE;
    """

    _registry = set()
    values: tuple = ()
    _enum_vals: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        PlaneEnum._registry.add(cls)
        cls._enum_vals = {}
        raw_vals = [(name, val) for name, val in cls.__dict__.items()
                     if not name.startswith("_") and isinstance(val, int)]
        n = len(raw_vals)
        width = max(1, (n - 1).bit_length()) if n > 1 else 1
        for name, val in raw_vals:
            cls._enum_vals[name] = EnumVal(cls, val, name, width)


class Vec:
    """Type representing a fixed-size array. Not a Node."""

    def __init__(self, typ, depth: int):
        self.typ = typ
        self.depth = depth


class Input:
    """Direction marker — not a Node. Used with IO() to create input ports."""

    def __init__(self, typ):
        self.typ = typ


class Output:
    """Direction marker — not a Node. Used with IO() to create output ports."""

    def __init__(self, typ):
        self.typ = typ


class Inout:
    """Direction marker — not a Node. Used with IO() to create inout ports."""

    def __init__(self, typ):
        self.typ = typ


class Flipped:
    """Wrap a direction marker or Bundle to reverse all field directions."""

    def __init__(self, inner):
        self.inner = inner


class Bundle:
    """Base class for structured interfaces with typed, directed fields.

    Subclass and declare fields as Input(T), Output(T), or Inout(T).
    When used with IO(), fields are expanded into flat ports using their
    declared directions. Use Flipped(Bundle()) to reverse all directions.

    Fields can be declared as class attributes or instance attributes in __init__.

    Example:
        class MyBundle(Bundle):
            data = Input(Bits(8))
            valid = Output(Bool())

        self.io = IO(MyBundle(), name="s")
        # Expands to: s_data (InputPort), s_valid (OutputPort)

        class MyParamBundle(Bundle):
            def __init__(self, width):
                self.data = Input(Bits(width))
                self.valid = Output(Bool())

        self.io = IO(MyParamBundle(width=8), name="s")
    """

    def __init__(self):
        pass
