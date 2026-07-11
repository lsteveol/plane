# BlackBoxes

`BlackBox` declares an external module whose body is not emitted. Use it for primitives, vendor IPs, or modules defined elsewhere.

## Basic BlackBox

```python
from plane import *

class DDRPad(BlackBox):
    def elaborate(self):
        self.io = IO(Inout(UInt(1)), name="io")
        self.din = IO(Input(UInt(1)), name="din")
        self.oe = IO(Input(Bool()), name="oe")
        self.dout = IO(Output(UInt(1)), name="dout")

class Top(Module):
    def elaborate(self):
        self.io = IO(Inout(UInt(1)), name="io")
        self.din = IO(Input(UInt(1)), name="din")
        self.oe = IO(Input(Bool()), name="oe")
        self.dout = IO(Output(UInt(1)), name="dout")
        pad = instance(DDRPad(), name="pad")
        pad.io @= self.io
        pad.din @= self.din
        pad.oe @= self.oe
        self.dout @= pad.dout
```

Emits:

```verilog
module Top (
  input  logic din,
  input  logic oe,
  inout  wire  io,
  output logic dout
);

  DDRPad pad (
    .io   (io),
    .din  (din),
    .oe   (oe),
    .dout (dout)
  );

endmodule
```

Note that `DDRPad` is not emitted — only the instance in `Top`.

## BlackBox with Parameters

BlackBoxes can have parameters just like regular modules:

```python
class BRAM(BlackBox):
    def elaborate(self):
        self.WIDTH = Parameter("WIDTH", 8)
        self.DEPTH = Parameter("DEPTH", 256)
        self.clk = IO(Input(Clock()), name="clk")
        self.addr = IO(Input(UInt(self.DEPTH.bit_length())), name="addr")
        self.dout = IO(Output(UInt(self.WIDTH)), name="dout")
```

## Gotchas

- **BlackBox body is not emitted** — The module definition must exist in another file or be provided by the toolchain.
- **Port connections work normally** — Use `@=` to connect parent signals to child ports.
- **Unconnected ports are allowed** — plane does not require all BlackBox ports to be connected.

## Next

Read the [Attributes](11_attributes.md) section to learn about synthesis annotations.
