# Getting Started

plane is a Python-based hardware description language (HDL) inspired by [Chisel](https://www.chisel-lang.org/). You describe digital circuits as Python classes, and plane emits SystemVerilog.

## Installation

```bash
pip install plane
```

## Your First Module

A plane circuit is a `Module` subclass with an `elaborate` method:

```python
from plane import *

class Blink(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        self.led = IO(Output(Bool()), name="led")
        self.counter = Reg(UInt(24), init=0, name="counter")
        self.counter @= self.counter + Literal(1, 24)
        self.led @= self.counter[23]
```

Call `emitVerilog()` to generate SystemVerilog:

```python
print(emitVerilog(Blink()))
```

Which produces:

```verilog
module Blink (
  input  logic clk,
  input  logic rst,
  output logic led
);

  logic [23:0] counter;

  assign led = counter[23];

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      counter <= 24'd0;
    end else begin
      counter <= (counter + 24'd1);
    end
  end

endmodule
```

## How It Works

- **`IO(Input(...))` and `IO(Output(...))`** declare ports with direction and type
- **`Reg(T)`** creates a clocked register of type `T`
- **`@=`** is the connection operator — it assigns hardware signals (like Chisel's `:=`)
- **`+`, `-`, `&`, `|`, etc.** operate on hardware signals, producing expression nodes (not Python values)
- **`emitVerilog()`** elaborates the module, collects child modules, deduplicates identical ones, and emits SystemVerilog

## Key Differences from Verilog

| Verilog | plane |
|---------|-------|
| `wire [7:0] a;` | `Wire(UInt(8))` |
| `assign out = a & b;` | `out @= a & b` |
| `always_ff @(posedge clk)` | `Reg(UInt(8))` (implicit clock) |
| `module Foo #(parameter W=8)` | `Parameter("W", 8)` |

## Gotchas

- **`@=` not `=`** — Use `@=` to connect hardware signals. Plain `=` is just Python attribute assignment.
- **Comparisons return nodes** — `a == b` produces a 1-bit hardware comparison, not a Python boolean. Use it in `When()` conditions, not Python `if` statements.
- **Clock is required** — `Reg` needs a clock. Define a `Clock` input first, or pass `clk=` explicitly.

## Next

Read the [Data Types](02_data_types.md) section to learn about `UInt`, `SInt`, `Bool`, `PlaneEnum`, `Bundle`, and `Vec`.
