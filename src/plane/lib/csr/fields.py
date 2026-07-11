class Field:
    """Base class for CSR fields."""

    def __init__(
        self,
        name: str,
        width: int = None,
        offset: int = 0,
        reset: int = 0,
        connection=None,
        description: str = "",
        metadata: dict = None,
    ):
        from plane.base import Parameter
        from plane.utils import get_node_width

        self.name = name
        self.offset = offset
        self.reset = reset
        self.connection = connection
        self.description = description
        self.metadata = metadata or {}

        if width is not None and connection is not None:
            conn_width = get_node_width(connection)
            if isinstance(conn_width, Parameter):
                raise ValueError(
                    f"Field '{name}': connection has parameterized width; "
                    f"provide an explicit integer width instead"
                )
            if conn_width != width:
                raise ValueError(
                    f"Field '{name}': width={width} does not match connection width={conn_width}"
                )
            self.width = width
        elif width is not None:
            self.width = width
        elif connection is not None:
            conn_width = get_node_width(connection)
            if isinstance(conn_width, Parameter):
                raise ValueError(
                    f"Field '{name}': connection has parameterized width; "
                    f"provide an explicit integer width instead"
                )
            self.width = conn_width
        else:
            raise ValueError(
                f"Field '{name}': width is required (provide width or connection)"
            )

    @property
    def access(self) -> str:
        raise NotImplementedError

    @property
    def uvm_access(self) -> str:
        """UVM RAL access type. Defaults to `access` but can be overridden for custom field types."""
        return self.access

    def create_port(self, port_name: str):
        raise NotImplementedError

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo: int, read_en=None):
        raise NotImplementedError

    def to_yaml(self, path=None) -> str:
        from .yaml_io import dump_yaml, field_to_dict

        return dump_yaml(field_to_dict(self), path)

    @classmethod
    def from_yaml(cls, path):
        from .yaml_io import field_from_dict, load_yaml

        return field_from_dict(load_yaml(path))


class RWField(Field):
    """Read-write field backed by a flop with output port."""

    @property
    def access(self) -> str:
        return "RW"

    def create_port(self, port_name):
        from plane import IO, Output, Reg, UInt

        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")
        self._port = IO(Output(UInt(self.width)), name=port_name)
        self._port @= self._reg

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Mux, UInt, Wire

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")

        next_val @= Mux(
            write_en,
            write_data[bit_lo + self.width - 1 : bit_lo] & byte_en_mask[bit_lo + self.width - 1 : bit_lo],
            self._reg,
        )

        self._reg @= next_val
        return self._reg


class ROField(Field):
    """Read-only field - value from external input port."""

    @property
    def access(self) -> str:
        return "RO"

    def create_port(self, port_name):
        from plane import IO, Input, UInt

        self._port = IO(Input(UInt(self.width)), name=port_name)

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        return self._port


class WOField(Field):
    """Write-only field backed by a flop with output port. Reads as 0."""

    @property
    def access(self) -> str:
        return "WO"

    def create_port(self, port_name):
        from plane import IO, Output, Reg, UInt

        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")
        self._port = IO(Output(UInt(self.width)), name=port_name)
        self._port @= self._reg

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Literal, Mux, UInt, Wire

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")

        next_val @= Mux(
            write_en,
            write_data[bit_lo + self.width - 1 : bit_lo] & byte_en_mask[bit_lo + self.width - 1 : bit_lo],
            self._reg,
        )

        self._reg @= next_val
        return Literal(0, self.width)


class W1CField(Field):
    """Write-1-to-clear field backed by a flop with output port.

    Writing 1 to a bit clears it, writing 0 leaves it unchanged.
    Typically used for interrupt status registers.
    """

    @property
    def access(self) -> str:
        return "W1C"

    def create_port(self, port_name):
        from plane import IO, Output, Reg, UInt

        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")
        self._port = IO(Output(UInt(self.width)), name=port_name)
        self._port @= self._reg

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Mux, UInt, Wire

        wdata_masked = Wire(UInt(self.width), name=f"{self.name}_wdata_masked")
        wdata_masked @= write_data[bit_lo + self.width - 1 : bit_lo] & byte_en_mask[bit_lo + self.width - 1 : bit_lo]

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")
        next_val @= Mux(write_en, self._reg & ~wdata_masked, self._reg)

        self._reg @= next_val
        return self._reg


class W1SField(Field):
    """Write-1-to-set field backed by a flop with output port.

    Writing 1 to a bit sets it, writing 0 leaves it unchanged.
    """

    @property
    def access(self) -> str:
        return "W1S"

    def create_port(self, port_name):
        from plane import IO, Output, Reg, UInt

        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")
        self._port = IO(Output(UInt(self.width)), name=port_name)
        self._port @= self._reg

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Mux, UInt, Wire

        wdata_masked = Wire(UInt(self.width), name=f"{self.name}_wdata_masked")
        wdata_masked @= write_data[bit_lo + self.width - 1 : bit_lo] & byte_en_mask[bit_lo + self.width - 1 : bit_lo]

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")
        next_val @= Mux(write_en, self._reg | wdata_masked, self._reg)

        self._reg @= next_val
        return self._reg


class RCField(Field):
    """Read-clear field backed by a flop with input port.

    Reading the field clears it to 0. The connection (input port) sets
    new bits (OR-ed with current value). Typically used for interrupt status.

    next = read_en ? 0 : (reg | connection)
    """

    @property
    def access(self) -> str:
        return "RC"

    def create_port(self, port_name):
        from plane import IO, Input, Reg, UInt

        self._port = IO(Input(UInt(self.width)), name=port_name)
        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Literal, Mux, UInt, Wire

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")
        if read_en is not None:
            next_val @= Mux(read_en, Literal(0, self.width), self._reg | self._port)
        else:
            next_val @= self._reg | self._port

        self._reg @= next_val
        return self._reg


class RCWField(Field):
    """Read-clear-write field backed by a flop with input port.

    Writing sets a new value. Reading clears to 0. The connection (input port)
    sets new bits (OR-ed with current value when not writing or reading).

    next = we ? wdata_masked : (read_en ? 0 : (reg | connection))
    """

    @property
    def access(self) -> str:
        return "RCW"

    def create_port(self, port_name):
        from plane import IO, Input, Reg, UInt

        self._port = IO(Input(UInt(self.width)), name=port_name)
        self._reg = Reg(UInt(self.width), init=self.reset, name=f"{port_name}_reg")

    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Literal, Mux, UInt, Wire

        wdata_masked = Wire(UInt(self.width), name=f"{self.name}_wdata_masked")
        wdata_masked @= write_data[bit_lo + self.width - 1 : bit_lo] & byte_en_mask[bit_lo + self.width - 1 : bit_lo]

        next_val = Wire(UInt(self.width), name=f"{self.name}_next")

        if read_en is not None:
            next_val @= Mux(
                write_en,
                wdata_masked,
                Mux(read_en, Literal(0, self.width), self._reg | self._port),
            )
        else:
            next_val @= Mux(write_en, wdata_masked, self._reg | self._port)

        self._reg @= next_val
        return self._reg
