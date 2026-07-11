# Bundles & Vecs

plane supports structured interfaces with `Bundle` and arrays with `Vec`.

## Bundle

A `Bundle` groups named fields with direction markers:

```python
from plane import *

class AXILite(Bundle):
    addr = Output(UInt(32))
    data = Input(UInt(8))
    valid = Output(Bool())
```

Use with `IO` to expand into flat, prefixed ports:

```python
class Top(Module):
    def elaborate(self):
        self.axi = IO(AXILite(), name="axi")
        self.axi.addr @= Literal(0, 32)
        self.axi.valid @= Literal(1)
```

Emits:

```verilog
module Top (
  input  logic [7:0]  axi_data,
  output logic [31:0] axi_addr,
  output logic        axi_valid
);

  assign axi_addr  = 32'd0;
  assign axi_valid = 1'd1;

endmodule
```

Access fields with `self.axi.addr`, `self.axi.data`, etc.

## Nested Bundles

Bundles can contain other bundles. Use either a class reference or an instance:

```python
class Inner(Bundle):
    a = Output(UInt(4))
    b = Input(UInt(4))

class Outer(Bundle):
    inner = Inner()  # or Inner (class reference)
    valid = Output(Bool())
```

Fields are prefixed with the parent name: `bus_inner_a`, `bus_inner_b`, `bus_valid`.

## Flipped

`Flipped()` reverses direction markers (`Input` <-> `Output`, `Inout` stays `Inout`):

```python
class AXILite(Bundle):
    addr = Output(UInt(32))
    data = Input(UInt(8))
    valid = Output(Bool())

class Top(Module):
    def elaborate(self):
        # Flipped: addr and valid become inputs, data becomes output
        self.in_bus = IO(Flipped(AXILite()), name="in_bus")
        self.in_bus.data @= self.in_bus.addr  # drive the output
```

Emits:

```verilog
module Top (
  input  logic [31:0] in_bus_addr,
  input  logic        in_bus_valid,
  output logic [7:0]  in_bus_data
);

  assign in_bus_data = in_bus_addr;

endmodule
```

`Flipped` is stackable — `Flipped(Flipped(T))` is `T`.

## Record-Style Dynamic Bundles

For data-driven interfaces (e.g., parsing a CSV of signals), you can build a Bundle from a list at runtime. This is **not a built-in plane class** — it's a user-defined pattern and your implementation may vary depending on your use case:

```python
from plane import *

class RecordBundle(Bundle):
    def __init__(self, signals):
        for name, direction, typ in signals:
            if isinstance(typ, type) and issubclass(typ, Bundle):
                setattr(self, name, typ())
            else:
                setattr(self, name, direction(typ))

signals = [
    ("data", Input, UInt(8)),
    ("valid", Output, Bool()),
    ("ready", Input, Bool()),
    ("addr", Input, UInt(32)),
]

class Top(Module):
    def elaborate(self):
        self.io = IO(RecordBundle(signals), name="s")
        self.io.valid @= Literal(1)
```

Emits:

```verilog
module Top (
  input  logic [7:0]  s_data,
  input  logic        s_ready,
  input  logic [31:0] s_addr,
  output logic        s_valid
);

  assign s_valid = 1'd1;

endmodule
```

Each signal is a tuple of `(name, Direction, Type)`. Nested bundles pass the class directly — the check `isinstance(typ, type) and issubclass(typ, Bundle)` handles them.

## Vec

`Vec(typ, depth)` creates a fixed-size array. Used with `IO`, `Wire`, and `Reg`:

```python
from plane import *

class VecSwap(Module):
    def elaborate(self):
        self.data_in = IO(Input(Vec(UInt(8), 4)), name="data_in")
        self.data_out = IO(Output(Vec(UInt(8), 4)), name="data_out")
        self.data_out[0] @= self.data_in[1]
        self.data_out[1] @= self.data_in[0]
        self.data_out[2] @= self.data_in[2]
        self.data_out[3] @= self.data_in[3]
```

Emits:

```verilog
module VecSwap (
  input  logic [7:0] data_in_0,
  input  logic [7:0] data_in_1,
  input  logic [7:0] data_in_2,
  input  logic [7:0] data_in_3,
  output logic [7:0] data_out_0,
  output logic [7:0] data_out_1,
  output logic [7:0] data_out_2,
  output logic [7:0] data_out_3
);

  assign data_out_0 = data_in_1;
  assign data_out_1 = data_in_0;
  assign data_out_2 = data_in_2;
  assign data_out_3 = data_in_3;

endmodule
```

## Vec Indexing

Index with an integer for a specific element:

```python
self.data_in[0]  # specific element
```

Index with a hardware node for a mux-based select (emits a priority mux tree):

```python
sel = IO(Input(UInt(2)), name="sel")
val = self.data_in[sel]  # mux tree
```

## Vec Assignment

Assign to all elements at once:

```python
self.data_out @= self.data_in  # broadcasts to all elements
```

## Gotchas

- **Bundle fields need direction markers** — Use `Input(T)`, `Output(T)`, or `Inout(T)`.
- **Nested bundles without direction** — Declare nested bundles directly without `Input`/`Output` wrapping.
- **Vec ports expand to flat signals** — `Vec(UInt(8), 4)` becomes `name_0`, `name_1`, etc.

## Next

Read the [Module Instantiation](08_module_instantiation.md) section to learn about child modules, port connections, and deduplication.
