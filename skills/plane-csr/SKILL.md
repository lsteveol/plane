---
name: plane-csr
description: plane CSR subsystem — RegisterBlock/RegisterSystem, field types, bus adapters, YAML/UVM RAL/HTML collateral. Use when defining registers, building CSR hardware, or generating register collateral.
---

# plane CSR usage

## Install

Requires Python 3.12+.

```bash
uv add plane-hdl
```

## Imports

```python
from plane import *
from plane.lib.csr import (
    RegisterBlock, Register, RegisterSystem, SystemChild,
    Field, RWField, ROField, WOField, W1CField, W1SField,
    RCField, RCWField, default_adapter,
)
from plane.lib.amba.apb import APB3Bundle, APB4Bundle, apb3_adapter, apb4_adapter
```

## Defining a block

```python
block = RegisterBlock(
    name="timer",
    width=32,
    registers=[
        Register(
            name="ctrl",
            offset=0x00,
            fields=[
                RWField(name="enable", width=1, offset=0, reset=0),
                RWField(name="mode", width=2, offset=1, reset=0),
                ROField(name="status", width=1, offset=3),
            ],
        ),
        Register(
            name="count",
            offset=0x04,
            fields=[RWField(name="value", width=32, offset=0, reset=0)],
        ),
    ],
)
```

## Field types

| Type | Semantics |
|------|-----------|
| `RWField` | Read-write, backed by flop with output port |
| `ROField` | Read-only, value from external input port |
| `WOField` | Write-only, backed by flop; reads as 0 |
| `W1CField` | Write-1-to-clear (interrupt status) |
| `W1SField` | Write-1-to-set |
| `RCField` | Read-clear; needs read-enable from bus adapter |
| `RCWField` | Read-clear-write; needs read-enable from bus adapter |

`width` is optional when `connection` is provided — it is inferred from the connection's width. If both are given, they must match. Parameterized-width connections are rejected.

## Field connections

`connection=` wires a field's port to an external signal during `build()`. Define the block and its connection wires inside `elaborate()`:

- **Output fields** (RW, WO, W1C, W1S): the field port drives the connected signal.
- **Input fields** (RO, RC, RCW): the connected signal drives the field port.

```python
class Top(Module):
    def elaborate(self):
        self.enable_out = Wire(Bool(), name="enable_out")
        self.status_in = Wire(Bool(), name="status_in")
        block = RegisterBlock(
            name="timer",
            width=32,
            registers=[
                Register(
                    name="ctrl",
                    offset=0x00,
                    fields=[
                        RWField(name="enable", width=1, offset=0, reset=0, connection=self.enable_out),
                        ROField(name="status", width=1, offset=1, connection=self.status_in),
                    ],
                ),
            ],
        )
        self.csr = block.build(adapter_fn=apb3_adapter)
        # ...connect self.csr.apb etc.
```

`connection=` is optional for collateral-only flows (YAML, UVM RAL, HTML, C header). `width` is inferred from the connection when omitted.

## Building hardware

`block.build()` returns a CSR submodule — call it **inside a `Module.elaborate()`** and connect its bus ports. `adapter_fn` selects the bus interface.

```python
from plane.lib.amba.apb import APB3Bundle, apb3_adapter

class Top(Module):
    def elaborate(self):
        self.apb = IO(APB3Bundle(addr_width=8, data_width=32), name="apb")
        block = RegisterBlock(...)  # define as above
        self.csr = block.build(adapter_fn=apb3_adapter)
        self.apb @= self.csr.apb

emitVerilog(Top(), filename="timer.sv")
```

With `default_adapter` (omit `adapter_fn`), the CSR exposes raw `io_*` ports (`io_clk`, `io_addr`, `io_write_en`, `io_read_en`, `io_write_data`, `io_byte_en`) you wire individually.

## Bus adapters

- `apb3_adapter` / `APB3Bundle` — APB3
- `apb4_adapter` / `APB4Bundle` — APB4
- `default_adapter` — exposes raw `io_*` bus ports (`io_clk`, `io_addr`, `io_write_en`, `io_read_en`, `io_write_data`, `io_byte_en`)

`bus_read_en` flows from the adapter to RC/RCW fields.

## Register systems

`RegisterSystem` groups blocks/sub-systems into a hierarchical address map for **collateral generation only** (UVM RAL, HTML, YAML, C header) — not hardware generation. Build each block's hardware separately via `block.build()`.

```python
system = RegisterSystem(
    name="soc",
    children=[
        timer_block.to_system_child(file="timer.yaml", name="timer0", offset=0x1000, address_space=0x100),
        uart_block.to_system_child(file="uart.yaml", name="uart0", offset=0x2000, address_space=0x100),
    ],
)
system.to_uvm_ral("soc_ral.sv")
system.to_html("soc.html")
```

Or construct `SystemChild` directly: `SystemChild(kind="block", file="timer.yaml", obj=timer_block, name="timer0", offset=0x1000, address_space=0x100)`.

Multi-instance (same block, distinct name/offset):

```python
timer_block.to_system_child(file="timer.yaml", name="timer0", offset=0x1000, address_space=0x100),
timer_block.to_system_child(file="timer.yaml", name="timer1", offset=0x1100, address_space=0x100),
```

## Collateral

**YAML** — round-trip block definitions:

```python
block.to_yaml("timer.yaml")
loaded = RegisterBlock.from_yaml("timer.yaml")
```

**UVM RAL** — generate register model:

```python
ral = block.to_uvm_ral()  # returns string
# Naming: <block>_<reg>, no _reg/_block suffix
# No package wrapper; user includes into their own package
# Access map: RCW -> WRC
# Volatility: RO/W1C/W1S/RC/RCW = volatile
```

**Name collision:** `build()` emits an SV module named `module_name` (defaults to `name`), while `to_uvm_ral()` emits a class named `name`. If they match and both are compiled in the same scope, you get a duplicate identifier. Set `module_name` distinct from `name` (e.g., `RegisterBlock(name="timer", module_name="timer_csr", ...)`), or wrap the RAL in a package without a wildcard `import` into the module's scope.

**HTML** — generate documentation:

```python
block.to_html("timer.html")
system.to_html("chip.html")
```

**C Header** — generate firmware header files:

```python
block.to_c_header("timer.h")
system.to_c_header("headers/")  # writes one .h per block + one per system
block.to_c_header("timer.h", prefix_block_name=False)  # omit block prefix
```

Generated defines:
- `TIMER_CTRL_ADDR` — register address
- `TIMER_CTRL_RESET` — computed reset value
- `TIMER_CTRL_ENABLE_OFFSET` — field bit offset
- `TIMER_CTRL_ENABLE_WIDTH` — field width
- `TIMER_CTRL_ENABLE_MASK` — field bitmask
- `TIMER_CTRL_ENABLE_BYTE_OFFSET` — byte index for byte-level access

Generic macros included in every header:
- `REG_READ(base, offset)` / `REG_WRITE(base, offset, val)` — 32-bit register access
- `GET_FIELD(reg, field)` / `UPDATE_FIELD(reg, field, val)` — 32-bit field extraction/update
- `FIELD8_WRITE(base, offset, field, val)` — 8-bit direct write (field must be sole byte occupant)
- `FIELD16_WRITE(base, offset, field, val)` — 16-bit direct write (field must be sole halfword occupant)

Comments from `description` and `metadata` attributes are included. Empty lines are omitted.

## Block options

- `unique_field_names=True` — enforce cross-block field name uniqueness
- `bare_field_ports=True` — use bare field names for ports (no block prefix)
- `bare_field_ports` forced `False` when `unique_field_names=False`
- YAML omits flags when `False`; defaults to `False` when missing
