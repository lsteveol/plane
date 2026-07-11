# Parameters

`Parameter` creates a SystemVerilog module parameter. Parameters control widths, counts, and other compile-time values.

## Declaring Parameters

Assign a `Parameter` as a module attribute in `elaborate`:

```python
from plane import *

class ShiftReg(Module):
    def elaborate(self):
        self.WIDTH = Parameter("WIDTH", 8)
        self.clk = IO(Input(Clock()), name="clk")
        self.din = IO(Input(UInt(self.WIDTH)), name="din")
        self.dout = IO(Output(UInt(self.WIDTH)), name="dout")
        self.r = Reg(UInt(self.WIDTH), name="r")
        self.r @= self.din
        self.dout @= self.r
```

Emits:

```verilog
module ShiftReg #(
  parameter int WIDTH = 8
) (
  input  logic             clk,
  input  logic [WIDTH-1:0] din,
  output logic [WIDTH-1:0] dout
);

  always_ff @(posedge clk) begin
    dout <= din;
  end

endmodule
```

## Overriding Parameters

Override parameters at instantiation with `params=`:

```python
class Top(Module):
    def elaborate(self):
        self.din = IO(Input(UInt(16)), name="din")
        self.dout = IO(Output(UInt(16)), name="dout")
        sr = instance(ShiftReg(), name="sr", params=(("WIDTH", 16),))
        sr.din @= self.din
        self.dout @= sr.dout
```

### Passing Parameters Through

You can also pass a parent parameter to a child, propagating the parameter:

```python
class Top(Module):
    def elaborate(self):
        self.WIDTH = Parameter("WIDTH", 16)
        self.clk = IO(Input(Clock()), name="clk")
        self.din = IO(Input(UInt(self.WIDTH)), name="din")
        self.dout = IO(Output(UInt(self.WIDTH)), name="dout")
        sr = instance(ShiftReg(), name="sr", params=(("WIDTH", self.WIDTH),))
        sr.clk @= self.clk
        sr.din @= self.din
        self.dout @= sr.dout
```

Emits:

```verilog
module Top #(
  parameter int WIDTH = 16
) (
  input  logic             clk,
  input  logic [WIDTH-1:0] din,
  output logic [WIDTH-1:0] dout
);

  ShiftReg #(.WIDTH(WIDTH)) sr (
    .clk (clk),
    .din (din),
    .dout (dout)
  );

endmodule
```

## Parameter Arithmetic

Parameters support integer arithmetic:

```python
self.WIDTH = Parameter("WIDTH", 8)
self.HALF = self.WIDTH // 2  # 4
self.DOUBLE = self.WIDTH * 2  # 16
```

## Multiple Parameters

Declare multiple parameters as module attributes:

```python
class FIFO(Module):
    def elaborate(self):
        self.WIDTH = Parameter("WIDTH", 8)
        self.DEPTH = Parameter("DEPTH", 16)
        self.data_in = IO(Input(Vec(UInt(self.WIDTH), self.DEPTH)), name="data_in")
```

## Gotchas

- **Parameters are module-level** — They are scanned from `dir(mod)` at emit time. Assign as module attributes.
- **Parameter types are `int`** — String and real parameters are not yet supported.
- **Width checking is skipped** for parameterized types — `check_width_mismatch` does not warn when a type uses a parameter.

## Next

Read the [BlackBoxes](10_blackboxes.md) section to learn about external modules.
