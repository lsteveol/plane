---
name: plane-hdl
description: Idioms for describing hardware in plane (a Python HDL emitting SystemVerilog). Use when writing plane Modules, ports, registers, control flow, bundles, or emitting Verilog.
---

# plane HDL usage

## Module shape

```python
from plane import *

class MyMod(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        self.in1 = IO(Input(UInt(8)), name="in1")
        self.out = IO(Output(UInt(8)), name="out")
        # ... hardware
```

- `@=` connects hardware signals. Plain `=` is Python attribute assignment.
- `a == b` returns a hardware node (1-bit comparison), not a Python bool. Use in `When()`, not Python `if`.

## Types

- `UInt(n)` / `SInt(n)` — unsigned/signed bit vector
- `Bool()` — 1-bit
- `Clock()` / `Reset()`
- `PlaneEnum` subclass — enum with named values
- `Vec(typ, depth)` — fixed-size array

## Reset types

- `AsyncLowReset` / `AsyncHighReset` — async resets
- `SyncLowReset` / `SyncHighReset` — sync resets
- `GlobalClockResetDefaults` — module-level defaults

## Bundles & Vecs

**Bundle** groups named fields with direction markers:

```python
class AXILite(Bundle):
    addr = Output(UInt(32))
    data = Input(UInt(8))
    valid = Output(Bool())

class Top(Module):
    def elaborate(self):
        self.axi = IO(AXILite(), name="axi")  # expands to prefixed ports
        self.axi.addr @= Literal(0, 32)
```

- Nested bundles: declare as class ref or instance; prefixes chain (`bus_inner_a`)
- `Flipped(T)` reverses directions; stackable
- `Vec(typ, depth)`: flat ports `name_0`, `name_1`, ...; `[int]` = element, `[node]` = mux tree; `@=` broadcasts

## Combinational / sequential

- `AlwaysComb()` — context manager for combinational block
- `Reg(T, init=, clk=, rst=, name=)` — implicit always_ff (clock required)
- `RegNext(next, init=)` — register with next value

## Control flow

**When / ElseWhen / Otherwise** — if-else chains:

```python
with AlwaysComb():
    with When(self.sel):
        self.w @= self.a + self.b
    with ElseWhen(self.a > self.b):
        self.w @= self.a - self.b
    with Otherwise():
        self.w @= Literal(0, 8)
```

**Switch / Case / Default** — case statements:

```python
with AlwaysComb():
    with Switch(self.sel):
        with Case(0):
            self.w @= self.a
        with Case(1):
            self.w @= self.b
        with Case(2):
            self.w @= self.c
        with Default():
            self.w @= self.d
```

**With enums**, `Case` emits named values automatically:

```python
class MyOp(PlaneEnum):
    ADD = 0
    SUB = 1
    MUL = 2

with AlwaysComb():
    with Switch(self.op):
        with Case(MyOp.ADD):
            self.w @= self.a + self.b
        with Case(MyOp.SUB):
            self.w @= self.a - self.b
        with Default():
            self.w @= self.a
```

**Default assignment pattern** — assign before `When` to avoid latches:

```python
with AlwaysComb():
    self.w @= Literal(0, 8)  # default
    with When(self.en):
        self.w @= Literal(1, 8)
```

## Comments

`comment=` on `Reg`, `Wire`, `Port`, `IO`, `AlwaysComb`, `When`, `Switch`, `Case`. Multi-line via `"\n"`.

## Expressions

- Operators: `& | ^ + - << >>`
- `Cat(...)`, `Replicate(n, val)`, `Slice`, `Index`
- `Mux(sel, a, b)`
- `zext` / `sext` (ZeroExtend / SignExtend)
- `asUInt` / `asSInt`
- Reductions: `AndR`, `OrR`, `XorR`
- `Literal(v, w)` — constant with explicit width

## Blackboxes

```python
class MyIP(BlackBox):
    def __init__(self):
        super().__init__()
        self.clk = IO(Input(Clock()), name="clk")
        self.data_in = IO(Input(UInt(32)), name="data_in")
        self.data_out = IO(Output(UInt(32)), name="data_out")
        self.valid = IO(Output(Bool()), name="valid")
```

Use for external IP or vendor primitives not described in plane.

## Instantiation

```python
add = instance(Adder(), name="adder")
add.a @= self.a
add.b @= self.b
self.out @= add.s
```

- Returns module reference; access ports as `inst.port_name`
- Unconnected ports allowed; fanout auto-resolves

### Array Instances

Use `count=` for Verilog array instances (e.g., vendor cells):

```python
mux = instance(TSMCMux(), name="u_mux", count=4)
mux.a @= self.sig_a  # 4-bit to 1-bit port → tool slices
mux.s @= self.sel    # 1-bit to 1-bit port → tool broadcasts
self.out @= mux.y    # 1-bit port to 4-bit → tool slices
```

Emits `TSMCMux u_mux[3:0]`. The Verilog tool handles width slicing/broadcasting.

> **⚠️ Width checks are disabled for array instances.** Ensure widths are correct — the downstream tool will catch mismatches.

For output fanout, use an explicit wire:

```python
self.mux_y = Wire(UInt(4), name="mux_y")
self.mux_y @= mux.y
self.out @= self.mux_y
self.debug @= self.mux_y
```

## Utilities

`from plane import utils` or `from plane.utils import ...`:

- `utils.group_always_ff` (bool, default `True`) — group Regs with same clk/rst
- `utils.enum_mode` (`"package"` | `"localparam"`) — enum emission
- `utils.width_mismatch_mode` (`"silent"` | `"warn"` | `"error"`)
- `utils.optimize_reg_to_port` (bool) — optimize Reg→OutputPort assigns
- `utils.max_line_width` (int or `None`)
- `utils.module_prefix` (str or `None`) — prefix for all plane-emitted module names (BlackBoxes excluded)
- `utils.convert_module_names_to_snake_case` (bool, default `False`) — convert CamelCase module names to snake_case (BlackBoxes excluded)
- `utils.to_snake_case(name)` — helper function for CamelCase → snake_case conversion
- `utils.WidthMismatchError`

Order of transformations (for non-BlackBox modules): snake_case → dedup suffix → prefix.

## Emit

```python
# Return SystemVerilog as string
sv = emitVerilog(MyMod())

# Write directly to file
emitVerilog(MyMod(), filename="output.sv")
```
