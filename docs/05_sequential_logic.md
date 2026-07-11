# Sequential Logic

plane supports clocked registers with flexible clock and reset resolution. Registers are grouped by clock/reset domain into separate `always_ff` blocks.

## Basic Register

`Reg(T)` creates a register of type `T`. The clock is resolved from the module's implicit clock (set by declaring a `Clock` port):

```python
from plane import *

class Counter(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.out = IO(Output(UInt(8)), name="out")
        self.counter = Reg(UInt(8), init=0, name="counter")
        self.counter @= self.counter + Literal(1, 8)
        self.out @= self.counter
```

Emits:

```verilog
always_ff @(posedge clk) begin
  counter <= (counter + 8'd1);
end
```

## Init Value

`init` sets the reset value. Pass an int or `Literal`:

```python
self.r = Reg(UInt(8), init=42, name="r")
```

## Clock Resolution

`Reg` resolves clock in this order:

1. Explicit `clk=` parameter
2. Module's implicit clock
3. **Error** if neither is available

### Setting the Implicit Clock

The implicit clock is automatically set when you declare a `Clock` port. You can also set it explicitly:

```python
class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.set_clock(self.clk)  # explicit, though automatic for first Clock port
```

For multiple clock domains, pass `clk=` explicitly on each reg:

```python
self.r1 = Reg(UInt(8), clk=self.clk1, name="r1")
self.r2 = Reg(UInt(8), clk=self.clk2, name="r2")
```

Emits two separate `always_ff` blocks, one per clock.

### set_clock / set_reset

Use `set_clock()` and `set_reset()` to override the implicit clock/reset for all subsequent `Reg` nodes:

```python
class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")

        self.set_clock(self.clk)
        self.set_reset(self.rst)

        # All Regs here use clk and rst implicitly
        self.r = Reg(UInt(8), name="r")
```

This is useful when you want to set clock/reset before declaring ports, or when using the `ClockReset` context manager internally.

## Reset

plane supports async and sync resets, active-high and active-low:

| Type | Sensitivity | Condition |
|------|-------------|-----------|
| `AsyncLowReset` | `posedge clk or negedge rst` | `!rst` |
| `AsyncHighReset` | `posedge clk or posedge rst` | `rst` |
| `SyncLowReset` | `posedge clk` | `!rst` (inside block) |
| `SyncHighReset` | `posedge clk` | `rst` (inside block) |

Async reset example:

```python
self.rst = IO(Input(AsyncLowReset()), name="rst")
self.r = Reg(UInt(8), init=0, name="r")
```

Emits:

```verilog
always_ff @(posedge clk or negedge rst) begin
  if (!rst) begin
    r <= 8'd0;
  end else begin
    r <= (r + 8'd1);
  end
end
```

Sync reset example:

```python
self.rst = IO(Input(SyncHighReset()), name="rst")
```

Emits:

```verilog
always_ff @(posedge clk) begin
  if (rst) begin
    r <= 8'd0;
  end else begin
    r <= (r + 8'd1);
  end
end
```

Reset is optional. If no reset port is declared, `always_ff` has no reset logic.

## RegNext

`RegNext(next, ...)` is a convenience that takes the next value in the constructor. Infers type from `next`:

```python
self.r = RegNext(self.a, name="r")
# Equivalent to:
# self.r = Reg(self.a.typ, name="r")
# self.r @= self.a
```

## ClockReset Context Manager

Temporarily override implicit clock/reset within a block:

```python
with ClockReset(self.fast_clk, self.fast_rst):
    self.r = Reg(UInt(8), name="r")  # uses fast_clk
```

## always_ff Grouping

By default, all registers sharing the same clock and reset are grouped into a single `always_ff` block. You can disable this to emit one `always_ff` per register:

**Per-module** (class attribute):

```python
class M(Module):
    group_always_ff = False

    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.r1 = Reg(Bits(8), name="r1")
        self.r1 @= 1
        self.r2 = Reg(Bits(8), name="r2")
        self.r2 @= 2
```

Emits two separate `always_ff` blocks, one per register.

**Global config**:

```python
from plane.utils import group_always_ff
group_always_ff = False
```

Module attribute takes precedence over the global config.

## Register-to-Port Optimization

When a register drives an output port, plane automatically optimizes away the intermediate register and assign statement:

```python
class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.in1 = IO(Input(UInt(8)), name="in1")
        self.out1 = IO(Output(UInt(8)), name="out1")
        
        self.r = Reg(UInt(8), name="r")
        self.r @= self.in1
        self.out1 @= self.r  # Direct connection to output port
```

Emits:

```verilog
module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out1
);

  always_ff @(posedge clk) begin
    out1 <= in1; // optimized from r
  end

endmodule
```

The optimization eliminates:
- The intermediate `logic [7:0] r;` declaration
- The `assign out1 = r;` statement
- Uses `out1` directly in the `always_ff` block

### Multiple Loads

When a register has multiple loads including output ports, the first output port becomes the canonical name. Other loads are assigned from it:

```python
self.out1 @= self.r  # First output port
self.out2 @= self.r  # Other output port
self.wire @= self.r  # Wire load
```

Emits:

```verilog
assign out2 = out1; // optimized from r
assign wire = out1; // optimized from r

always_ff @(posedge clk) begin
  out1 <= in1; // optimized from r
end
```

The optimization applies when:
- The register has at least one output port load
- The register's `optimize` parameter is `True` (default)
- The global `optimize_reg_to_port` config is `True` (default)

### Disabling Optimization

**Per-register** (useful for debugging or specific naming requirements):

```python
self.r = Reg(UInt(8), name="r", optimize=False)
```

**Global config**:

```python
from plane.utils import optimize_reg_to_port
optimize_reg_to_port = False
```

## Auto-Naming Registers

When you don't provide a name for a register, plane automatically generates one:

```python
class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.in1 = IO(Input(UInt(8)), name="in1")
        
        self.r1 = Reg(UInt(8))  # auto_reg_0
        self.r1 @= self.in1
        
        self.r2 = RegNext(self.in1)  # auto_reg_1
```

Emits:

```verilog
module M (
  input  logic       clk,
  input  logic [7:0] in1
);

  logic [7:0] auto_reg_0;
  logic [7:0] auto_reg_1;

  always_ff @(posedge clk) begin
    auto_reg_0 <= in1;
    auto_reg_1 <= in1;
  end

endmodule
```

Auto-generated names follow the pattern `auto_reg_N` where N is a module-scoped counter. The counter increments for each auto-named register and skips names that conflict with user-defined names.

## Gotchas

- **Clock is required** — `Reg` will raise `RuntimeError` if no clock is available.
- **Reset is optional** — No reset port means no reset logic in `always_ff`.
- **First clock wins** — Only the first `Clock` port becomes implicit. Use `clk=` for additional domains.

## Next

Read the [Control Flow](06_control_flow.md) section to learn about `AlwaysComb`, `When`/`ElseWhen`/`Otherwise`, and `Switch`/`Case`.
