# Data Types

plane provides hardware types for integers, booleans, clocks, resets, enums, and structured data.

## Unsigned Integers

`UInt(width)` represents an unsigned N-bit value:

```python
from plane import *

class Adder(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.s = IO(Output(UInt(9)), name="s")
        self.s @= self.a + self.b
```

`Bits(width)` is an alias for `UInt(width)` — use whichever you prefer.

## Signed Integers

`SInt(width)` represents a signed N-bit value. Emits as `logic signed`:

```python
class SignedAdder(Module):
    def elaborate(self):
        self.a = IO(Input(SInt(8)), name="a")
        self.b = IO(Input(SInt(8)), name="b")
        self.c = IO(Output(SInt(8)), name="c")
        self.c @= self.a + self.b
```

Emits:

```verilog
module SignedAdder (
  input logic signed [7:0] a,
  input logic signed [7:0] b,
  output logic signed [7:0] c
);

  assign c = (a + b);

endmodule
```

## Casting

Convert between signed and unsigned with `asUInt()` and `asSInt()`:

```python
class CastExample(Module):
    def elaborate(self):
        self.a = IO(Input(SInt(8)), name="a")
        self.u = IO(Output(UInt(8)), name="u")
        self.u @= asUInt(self.a)
```

Emits `$unsigned(a)` in Verilog.

## Bool

`Bool` is a 1-bit unsigned type:

```python
self.valid = IO(Output(Bool()), name="valid")
```

## Clock and Reset

Clock and reset types mark special signals:

```python
self.clk = IO(Input(Clock()), name="clk")
self.rst = IO(Input(AsyncLowReset()), name="rst")
```

Reset variants:

| Type | Behavior |
|------|----------|
| `AsyncLowReset` | Async, active-low (default) |
| `AsyncHighReset` | Async, active-high |
| `SyncLowReset` | Sync, active-low |
| `SyncHighReset` | Sync, active-high |

### Implicit Clock and Reset

When you declare a `Clock` or `Reset` port, plane automatically registers it as the module's implicit clock/reset. Every `Reg` created in that module will use it unless you pass `clk=` or `rst=` explicitly:

```python
class WithImplicit(Module):
    def elaborate(self):
        # These set the implicit clock and reset for the module
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")

        # No clk/rst needed — resolved automatically
        self.r = Reg(UInt(8), name="counter")
        self.r @= self.r + Literal(1, 8)
```

Only the **first** clock or reset port becomes implicit. If you need multiple clock domains, pass `clk=` explicitly:

```python
self.fast_r = Reg(UInt(8), clk=self.fast_clk, name="fast_r")
```

You can override the implicit clock/reset with `set_clock()` and `set_reset()`, or use the `ClockReset` context manager to temporarily change them (see [Control Flow](06_control_flow.md)).

If a `Reg` has no clock available (neither explicit nor implicit), plane raises a `RuntimeError`.

## Enums

Define an enum by subclassing `PlaneEnum`:

```python
class MyState(PlaneEnum):
    IDLE = 0
    RUNNING = 1
    DONE = 2

class StateReg(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.state = Reg(MyState, name="state")
        self.state @= MyState.RUNNING
```

Enum width is computed automatically from the number of values. Values are accessed as `MyState.IDLE`, `MyState.RUNNING`, etc.

### Emission Modes

plane supports two enum emission modes controlled by the global `enum_mode` setting in `plane.utils`:

**Package mode** (default) — emits a SystemVerilog package with `typedef enum`:

```python
from plane.utils import enum_mode
enum_mode = "package"  # default
```

```verilog
package M_pkg;
  typedef enum logic [1:0] { IDLE, RUNNING, DONE } MyState_t;
endpackage

module M (
  input  logic clk
);

  import M_pkg::*;

  MyState_t state;

  always_ff @(posedge clk) begin
    state <= MyState_t::RUNNING;
  end

endmodule
```

**Localparam mode** — emits per-module `localparam` definitions:

```python
enum_mode = "localparam"
```

```verilog
module M (
  input  logic clk
);

  localparam MyState_IDLE = 2'd0, MyState_RUNNING = 2'd1, MyState_DONE = 2'd2;

  logic [1:0] state;

  always_ff @(posedge clk) begin
    state <= MyState_RUNNING;
  end

endmodule
```

### Enum Operations

Enum values work with all standard hardware operations:

**Comparison:**

```python
with When(self.state == MyState.RUNNING):
    self.valid @= 1
```

**Mux:**

```python
self.out @= Mux(self.sel, MyState.DONE, MyState.IDLE)
```

**Switch/Case:**

```python
with Switch(self.state):
    with Case(MyState.IDLE):
        self.next @= MyState.RUNNING
    with Default():
        self.next @= MyState.IDLE
```

**Reset value:**

```python
self.state = Reg(MyState, init=MyState.RUNNING, name="state")
```

### Gotchas

- **Package mode requires SystemVerilog** — `typedef enum` and `import` are SV features. Use localparam mode for Verilog-2005 compatibility.
- **Ports emit as `logic [N:0]`** — Enum-typed ports always emit as bit vectors. The enum type info is preserved for internal wires and regs.

## Vec

`Vec(typ, depth)` is a fixed-size array type. Used with `IO`, `Wire`, and `Reg` to expand into individual elements:

```python
self.data_in = IO(Input(Vec(UInt(8), 4)), name="data_in")
```

Access elements with `self.data_in[0]`, `self.data_in[1]`, etc.

## Bundle

`Bundle` defines structured interfaces:

```python
class AXILite(Bundle):
    addr = Output(UInt(32))
    data = Input(UInt(8))
    valid = Output(Bool())
```

Use with `IO` to expand into flat ports:

```python
self.axi = IO(AXILite(), name="axi")
# Expands to: axi_addr, axi_data, axi_valid
```

## Width Inference

`Literal(value, width)` lets you specify an explicit width. If width is `None`, it's inferred from context (e.g., assigned to a reg of known type):

```python
self.r @= Literal(0)  # width inferred from self.r.typ
self.r @= Literal(42, 8)  # explicit 8-bit width
```

## Gotchas

- **Signed/unsigned mixing** — plane does not auto-promote. Use `asSInt()` or `asUInt()` explicitly.

## Next

Read the [Modules & Ports](03_modules_and_ports.md) section to learn about module construction, port declaration, and naming.
