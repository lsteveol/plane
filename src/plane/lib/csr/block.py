
from .register import Register


def default_adapter(csr):
    """Default CSR adapter — exposes PlaneCSR ports directly."""
    from plane import IO, AsyncLowReset, Bool, Clock, Input, Output, UInt

    csr.io_clk = IO(Input(Clock()), name="clk")
    csr.io_rst = IO(Input(AsyncLowReset()), name="rst")
    csr.io_addr = IO(Input(UInt(csr._addr_width)), name="addr")
    csr.io_write_en = IO(Input(Bool()), name="write_en")
    csr.io_read_en = IO(Input(Bool()), name="read_en")
    csr.io_write_data = IO(Input(UInt(csr._data_width)), name="write_data")
    csr.io_byte_en = IO(Input(UInt(csr._data_width // 8)), name="byte_en")
    csr.io_read_data = IO(Output(UInt(csr._data_width)), name="read_data")

    csr.bus_addr @= csr.io_addr
    csr.bus_write_en @= csr.io_write_en
    csr.bus_read_en @= csr.io_read_en
    csr.bus_write_data @= csr.io_write_data
    csr.bus_byte_en @= csr.io_byte_en
    csr.io_read_data @= csr.bus_rdata


class RegisterBlock:
    """A block of registers with address mapping."""

    def __init__(
        self,
        name: str,
        registers: list[Register] = None,
        width: int = 32,
        address_space: int = 256,
        description: str = "",
        module_name: str = None,
        instance_name: str = None,
        metadata: dict = None,
        unique_field_names: bool = False,
        bare_field_ports: bool = False,
    ):
        self.name = name
        self.module_name = module_name or name
        self.instance_name = instance_name
        self.registers = registers or []
        self.width = width
        self.address_space = address_space
        self.description = description
        self.metadata = metadata or {}
        self.unique_field_names = unique_field_names
        self.bare_field_ports = bare_field_ports if unique_field_names else False

    @property
    def addr_width(self) -> int:
        return max(1, (self.address_space - 1).bit_length())

    def to_yaml(self, path=None) -> str:
        from .yaml_io import block_to_dict, dump_yaml

        return dump_yaml(block_to_dict(self), path)

    @classmethod
    def from_yaml(cls, path, base_dir=None):
        from .yaml_io import block_from_dict, load_yaml

        return block_from_dict(load_yaml(path), base_dir=base_dir)

    def to_html(self, output_dir):
        from .html import generate_html

        generate_html(self, output_dir)

    def to_uvm_ral(self, output_path=None) -> str:
        from .uvm_ral import generate_uvm_ral

        return generate_uvm_ral(self, output_path)

    def to_c_header(self, output_path=None, prefix_block_name=True) -> str:
        from .c_header import generate_c_header

        return generate_c_header(self, output_path, prefix_block_name)

    def to_system_child(self, file, name, offset, address_space, description=""):
        from .system import SystemChild

        return SystemChild(
            kind="block",
            file=file,
            obj=self,
            name=name,
            offset=offset,
            address_space=address_space,
            description=description,
        )

    def _validate(self):
        """Validate register block for errors. Raises ValueError on first error."""
        errors = []
        seen_reg_offsets = set()
        seen_reg_names = set()
        block_seen_field_names = set()

        for reg in self.registers:
            if reg.name in seen_reg_names:
                errors.append(f"Duplicate register name: {reg.name}")
            seen_reg_names.add(reg.name)

            if reg.offset in seen_reg_offsets:
                errors.append(f"Duplicate register offset {reg.offset}: {reg.name}")
            seen_reg_offsets.add(reg.offset)

            total_field_width = sum(f.width for f in reg.fields)
            if total_field_width > self.width:
                errors.append(
                    f"Register {reg.name} field width {total_field_width} > bus width {self.width}"
                )

            used_bits = set()
            seen_field_names = set()
            for fld in reg.fields:
                if fld.name in seen_field_names:
                    errors.append(f"Duplicate field name: {fld.name} in register {reg.name}")
                seen_field_names.add(fld.name)

                if self.unique_field_names:
                    if fld.name in block_seen_field_names:
                        errors.append(f"Duplicate field name across block: {fld.name}")
                    block_seen_field_names.add(fld.name)

                for bit in range(fld.offset, fld.offset + fld.width):
                    if bit in used_bits:
                        errors.append(
                            f"Field {fld.name} overlaps at bit {bit} in register {reg.name}"
                        )
                    used_bits.add(bit)

                if fld.offset + fld.width > self.width:
                    errors.append(
                        f"Field {fld.name} extends beyond bus width in register {reg.name}"
                    )

                if fld.reset >= (1 << fld.width):
                    errors.append(
                        f"Field {fld.name} reset value {fld.reset} too large for width {fld.width}"
                    )

        if errors:
            raise ValueError("RegisterBlock validation failed:\n  - " + "\n  - ".join(errors))

    def build(self, adapter_fn=default_adapter):
        """Build CSR hardware into parent module.

        The adapter_fn is called inside _CSR.elaborate() to declare ports
        and map them to internal bus_* signals.

        Args:
            adapter_fn: Function that takes the CSR module and declares ports.
                       Default is default_adapter which exposes PlaneCSR ports.
                       Use apb3_adapter or apb4_adapter for APB protocol.
        """
        from plane import Module
        from plane.nodes import instance

        self._validate()

        if not self.registers:
            return None

        block = self
        registers = block.registers
        width = block.width
        addr_width = block.addr_width
        module_name = block.module_name
        bare_field_ports = block.bare_field_ports

        class _CSR(Module):
            def elaborate(self):
                from plane import (
                    Bool,
                    Cat,
                    Literal,
                    Replicate,
                    UInt,
                    Wire,
                )

                self._addr_width = addr_width
                self._data_width = width

                self.bus_addr = Wire(UInt(addr_width), name="bus_addr")
                self.bus_write_en = Wire(Bool(), name="bus_write_en")
                self.bus_read_en = Wire(Bool(), name="bus_read_en")
                self.bus_write_data = Wire(UInt(width), name="bus_write_data")
                self.bus_byte_en = Wire(UInt(width // 8), name="bus_byte_en")
                self.bus_rdata = Wire(UInt(width), name="bus_rdata")

                adapter_fn(self)

                byte_en_mask = Wire(UInt(width), name="byte_en_mask")
                byte_en_mask @= Cat(*reversed([Replicate(self.bus_byte_en[i], 8) for i in range(width // 8)]))

                reg_read_data = []
                for reg in registers:
                    addr_match = Wire(Bool(), name=f"{reg.name}_addr_match")
                    addr_match.comment = f"Register {reg.name} Control Logic"
                    addr_match @= self.bus_addr == reg.offset

                    reg_we = Wire(Bool(), name=f"{reg.name}_we")
                    reg_we @= addr_match & self.bus_write_en

                    reg_read_en = Wire(Bool(), name=f"{reg.name}_read_en")
                    reg_read_en @= addr_match & self.bus_read_en

                    read_parts = []
                    bit_lo = 0
                    for fld in reg.fields:
                        port_name = fld.name if bare_field_ports else f"{reg.name}_{fld.name}"
                        fld.create_port(port_name)
                        
                        if hasattr(fld, "_reg"):
                            fld._reg.comment = f"Register: {reg.name}\nAddress:  0x{reg.offset:04X}\nType:     {fld.access}"
                        
                        node = fld.create_logic(
                            reg_we,
                            self.bus_write_data,
                            byte_en_mask,
                            fld.offset,
                            read_en=reg_read_en,
                        )

                        if fld.offset > bit_lo:
                            read_parts.append(Literal(0, fld.offset - bit_lo))

                        if node is not None:
                            read_parts.append(node)
                        bit_lo = fld.offset + fld.width

                    if bit_lo < width:
                        read_parts.append(Literal(0, width - bit_lo))

                    if read_parts:
                        reg_data = Cat(*reversed(read_parts))
                        reg_read_data.append((addr_match, reg_data))

                read_data_expr = None
                for addr_match, reg_data in reg_read_data:
                    gated = Replicate(addr_match, width) & reg_data
                    if read_data_expr is None:
                        read_data_expr = gated
                    else:
                        read_data_expr |= gated
                self.bus_rdata @= read_data_expr

        csr = instance(_CSR(desired_name=module_name), name=block.instance_name)

        for reg in registers:
            for fld in reg.fields:
                if fld.connection is None:
                    continue
                if fld.access in ("RO", "RC", "RCW"):
                    fld._port @= fld.connection
                elif fld.access in ("RW", "WO", "W1C", "W1S"):
                    fld.connection @= fld._port

        return csr
