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

Use `connection=` to drive an external wire from a field. **Only applies when NOT calling `build()`** — when you're defining a block without building the full hardware:

```python
self.enable_wire = Wire(UInt(1), name="enable")
block = RegisterBlock(
    name="timer",
    width=32,
    registers=[
        Register(
            name="ctrl",
            offset=0x00,
            fields=[RWField(name="enable", width=1, offset=0, reset=0, connection=self.enable_wire)],
        ),
    ],
)
# When you call block.build(adapter=...), connections are ignored.
# The block's ports become the module's ports via the adapter.
```

Omit `connection=` when calling `build()` — the adapter handles port connections.

## Building hardware

```python
top = block.build(adapter=apb3_adapter)
emitVerilog(top, filename="timer.sv")
```

The adapter selects the bus interface. The block's ports become the module's ports.

## Bus adapters

- `apb3_adapter` / `APB3Bundle` — APB3
- `apb4_adapter` / `APB4Bundle` — APB4
- `default_adapter` — auto-select based on available adapters

`bus_read_en` flows from the adapter to RC/RCW fields.

## Register systems

Compose multiple blocks into an address-mapped system:

```python
system = RegisterSystem(
    name="chip",
    children=[
        SystemChild(block=timer_block, instance_name="timer", base=0x1000),
        SystemChild(block=uarta_block, instance_name="uart", base=0x2000),
    ],
)

# Build top-level module with all blocks address-mapped
top = system.build(adapter=apb3_adapter)
emitVerilog(top, filename="chip.sv")
```

Multi-instance:

```python
SystemChild(block=timer_block, instance_name="timer0", base=0x1000),
SystemChild(block=timer_block, instance_name="timer1", base=0x1100),
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
