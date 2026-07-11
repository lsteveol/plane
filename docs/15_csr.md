# CSR Generation

plane includes a library for defining control and status registers (CSRs) in Python and generating the corresponding SystemVerilog, UVM RAL models, YAML descriptions, and HTML documentation.

## Overview

The CSR library lets you:

- Define registers and fields with access types (RW, RO, WO, W1C, W1S, RC, RCW)
- Build hardware modules with bus adapters (default, APB3, APB4)
- Generate collateral: UVM RAL models, YAML, and HTML documentation
- Extend with custom field types

## Defining a Register Block

A `RegisterBlock` contains one or more `Register` instances. Each register has fields with offsets and widths:

```python
from plane.lib.csr import RegisterBlock, Register, RWField, ROField

block = RegisterBlock(
    name="timer",
    registers=[
        Register(
            name="ctrl",
            offset=0,
            fields=[
                RWField(name="enable", width=1, offset=0, reset=0),
                RWField(name="mode", width=3, offset=4, reset=5),
            ],
        ),
        Register(
            name="status",
            offset=4,
            fields=[
                ROField(name="done", width=1, offset=0),
            ],
        ),
    ],
    width=32,
    address_space=256,
)
```

Parameters:
- `width`: Bus data width (e.g., 32 for a 32-bit bus)
- `address_space`: Total address space allocated to this block

## Field Types

| Type | Access | Description |
|------|--------|-------------|
| `RWField` | RW | Read-write. Writing sets the value, reading returns it. |
| `ROField` | RO | Read-only. Value comes from an external input port. |
| `WOField` | WO | Write-only. Writing sets the value, reading returns 0. |
| `W1CField` | W1C | Write-1-to-clear. Writing 1 clears bits, writing 0 leaves unchanged. |
| `W1SField` | W1S | Write-1-to-set. Writing 1 sets bits, writing 0 leaves unchanged. |
| `RCField` | RC | Read-clear. Reading clears to 0. External input sets bits via OR. |
| `RCWField` | RCW | Read-clear-write. Combines read-clear and write behavior. |

All field constructors accept:
- `name`: Field name
- `width`: Bit width (optional if `connection` is provided — width is inferred from the connection)
- `offset`: Bit offset within the register (default 0)
- `reset`: Reset value (default 0)
- `connection`: External signal to connect (see Connections below)
- `description`: Human-readable description (for documentation)

If `width` is omitted, it is derived from the connection's width. If both `width` and `connection` are provided, they must match. Connections with parameterized widths are rejected — provide an explicit integer `width` in that case.

## Connections

Fields with external signals use the `connection` parameter. The direction depends on the access type:

- **Output fields** (RW, WO, W1C, W1S): The field's output port drives the connected signal.
  ```python
  self.enable_out = Wire(Bool(), name="enable_out")
  RWField(name="enable", width=1, offset=0, connection=self.enable_out)
  # Or infer width from the connection:
  RWField(name="enable", offset=0, connection=self.enable_out)
  ```

- **Input fields** (RO, RC, RCW): The connected signal drives the field's input port.
  ```python
  self.status_in = Wire(UInt(8), name="status_in")
  ROField(name="status", width=8, offset=0, connection=self.status_in)
  # Or infer width from the connection:
  ROField(name="status", offset=0, connection=self.status_in)
  ```

Sliced connections are supported — width is inferred from the slice:
```python
self.big_wire = Wire(UInt(32), name="big_wire")
RWField(name="low4", offset=0, connection=self.big_wire[3:0])  # width=4 inferred
```

**Note:** The `connection` parameter is only required when generating hardware via `block.build()`. When building a `RegisterBlock` for collateral-only flows (YAML, UVM RAL, HTML documentation), you can leave `connection=None` or omit it entirely.

## Custom Field Types

You can create custom field behavior by subclassing an existing field type. The recommended approach is to subclass the field whose access type matches your needs, then override only `create_logic()`:

```python
from plane.lib.csr import RWField

class RWToggleField(RWField):
    """Write-1-to-toggle: writing 1 toggles bits, writing 0 keeps them."""
    
    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        from plane import Mux, UInt, Wire
        
        next_val = Wire(UInt(self.width), name=f"{self.name}_next", 
                       comment="Write-1-to-toggle: XOR with masked write data")
        
        wdata_slice = write_data[bit_lo + self.width - 1 : bit_lo]
        byte_en_slice = byte_en_mask[bit_lo + self.width - 1 : bit_lo]
        
        # Toggle: XOR current value with masked write data
        toggle_val = self._reg ^ (wdata_slice & byte_en_slice)
        next_val @= Mux(write_en, toggle_val, self._reg)
        
        self._reg @= next_val
        return self._reg
```

Use it like any built-in field:

```python
RWToggleField(name="toggle", width=4, offset=4, reset=0, connection=self.toggle_out)
```

By inheriting `access` as `"RW"`, the field works with `connection=`, UVM RAL generation, YAML serialization, and HTML documentation without modification.

See [docs/examples/custom_field.py](examples/custom_field.py) for a complete runnable example.

### UVM Access Type

If your custom field needs a different UVM access type than its hardware `access` type, override the `uvm_access` property:

```python
class CustomField(Field):
    @property
    def access(self) -> str:
        return "CUSTOM"  # Used for hardware generation
    
    @property
    def uvm_access(self) -> str:
        return "RW"  # Used for UVM RAL generation (defaults to access)
```

This is useful when your custom behavior doesn't map to a standard UVM access type, but you want it to appear as a standard type in the RAL model.

### Extension Contract

If you need a completely new access type, subclass `Field` directly and implement:

- `access` property: Return a string identifying the access type
- `uvm_access` property (optional): Return the UVM RAL access type (defaults to `access`)
- `create_port(port_name)`: Create the field's IO port(s) and backing register
- `create_logic(write_en, write_data, byte_en_mask, bit_lo, read_en)`: Implement read/write logic, return the read data node

**Note:** Custom access types not in the built-in lists (`RW`, `RO`, `WO`, `W1C`, `W1S`, `RC`, `RCW`) won't auto-wire `connection=` in `block.build()`. If you need different connection behavior or other functionality not supported by `RegisterBlock`, you can subclass it and override methods like `build()` as needed. You can also use the existing implementation as a reference to create your own CSR builder from scratch.

## Building Hardware

Call `block.build()` to generate the CSR module. By default, it uses the `default_adapter` which exposes raw bus signals:

```python
class Top(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        self.addr = IO(Input(UInt(8)), name="addr")
        self.write_en = IO(Input(Bool()), name="write_en")
        self.read_en = IO(Input(Bool()), name="read_en")
        self.write_data = IO(Input(UInt(32)), name="write_data")
        
        block = RegisterBlock(...)
        self.csr = block.build()
        
        self.csr.io_clk @= self.clk
        self.csr.io_rst @= self.rst
        self.csr.io_addr @= self.addr
        self.csr.io_write_en @= self.write_en
        self.csr.io_read_en @= self.read_en
        self.csr.io_write_data @= self.write_data
        self.csr.io_byte_en @= Literal(0b1111, 4)
```

## Bus Adapters

For standard bus protocols, use adapters that wrap the bus interface:

### APB3

```python
from plane.lib.amba.apb import APB3Bundle, apb3_adapter

class Top(Module):
    def elaborate(self):
        self.apb = IO(APB3Bundle(addr_width=8, data_width=32), name="apb")
        
        block = RegisterBlock(...)
        self.csr = block.build(adapter_fn=apb3_adapter)
        
        self.apb @= self.csr.apb
```

The APB3 adapter handles the two-phase protocol (setup/enable) internally.

### APB4

```python
from plane.lib.amba.apb import APB4Bundle, apb4_adapter

self.csr = block.build(adapter_fn=apb4_adapter)
```

APB4 adds byte strobes (`pstrb`) and protection signals (`pprot`).

## Field Naming Options

By default, field ports are named `{register}_{field}`. You can control this with two flags:

- `unique_field_names=True`: Validates that all field names are unique across the block
- `bare_field_ports=True`: Uses bare field names (no register prefix) for ports

```python
block = RegisterBlock(
    name="timer",
    registers=[...],
    unique_field_names=True,
    bare_field_ports=True,  # ports named "enable" instead of "ctrl_enable"
)
```

`bare_field_ports` requires `unique_field_names=True` to avoid port name collisions.

## Register Systems

`RegisterSystem` groups multiple blocks or sub-systems into a hierarchical address map:

```python
from plane.lib.csr import RegisterSystem, SystemChild

system = RegisterSystem(
    name="soc",
    children=[
        SystemChild(kind="block", file="timer.yaml", obj=timer_block, name="timer0", offset=0x1000, address_space=0x100),
        SystemChild(kind="block", file="uart.yaml", obj=uart_block, name="uart0", offset=0x2000, address_space=0x100),
    ],
)
```

Systems are used for collateral generation (UVM RAL, HTML docs), not hardware generation.

## Gotchas

- **Field offsets must not overlap** — The validator checks for bit overlaps within a register.
- **Register offsets must be unique** — Duplicate register offsets are rejected.
- **Field widths must fit in the bus** — Total field width in a register can't exceed `block.width`.
- **Reset values must fit in field width** — A 3-bit field can't have reset=8.
- **Connections are directional** — Output fields (RW/WO/W1C/W1S) drive the connection; input fields (RO/RC/RCW) are driven by it.
- **Custom access types need manual connection handling** — Unknown access strings aren't in build()'s connection-direction lists.

## Next

Read the [CSR Collateral Generation](16_csr_collateral.md) section to learn about generating UVM RAL models, YAML descriptions, and HTML documentation.
