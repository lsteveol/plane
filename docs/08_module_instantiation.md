# Module Instantiation

Child modules are instantiated with `instance()`. plane collects all child modules, deduplicates identical ones, and emits them alongside the parent.

## Basic Instantiation

```python
from plane import *

class Adder(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.s = IO(Output(UInt(8)), name="s")
        self.s @= self.a + self.b

class Top(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.out = IO(Output(UInt(8)), name="out")
        add = instance(Adder(), name="adder")
        add.a @= self.a
        add.b @= self.b
        self.out @= add.s
```

Emits:

```verilog
module Top (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  Adder adder (
    .a (a),
    .b (b),
    .s (out)
  );

endmodule

module Adder (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] s
);

  assign s = (a + b);

endmodule
```

## Port Connections

Connect child ports with `@=`. The connection is resolved at emission time — unconnected ports are omitted.

```python
add = instance(Adder())
add.a @= self.a
add.b @= self.b
self.sum @= add.s
```

## Fanout Resolution

When a child output port drives multiple sinks, plane automatically creates an intermediate wire:

```python
add = instance(Adder())
add.a @= self.a
add.b @= self.b
self.sum @= add.s
self.debug @= add.s  # fanout — wire created automatically
```

## Deduplication

Identical modules (same structure, same IR) are deduplicated into a single emitted module with multiple instances. Modules with the same name but different internal logic emit as separate modules with numeric suffixes:

```python
class Gate(Module):
    def __init__(self, mode_and=True):
        super().__init__()
        self.mode_and = mode_and

    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.z = IO(Output(UInt(8)), name="z")
        if self.mode_and:
            self.z @= self.a & self.b
        else:
            self.z @= self.a | self.b

class Top(Module):
    def elaborate(self):
        self.and_inst = instance(Gate(mode_and=True))
        self.or_inst = instance(Gate(mode_and=False))
```

Emits two modules: `Gate` (and) and `Gate_1` (or).

## Array Instances

Use `count=` to instantiate N copies of a module as a Verilog array instance. This is useful for vendor cells (e.g., TSMC muxes) where you want synthesis to use a specific cell:

```python
from plane import *

class TSMCMux(BlackBox):
    def elaborate(self):
        self.a = IO(Input(UInt(1)), name="a")
        self.b = IO(Input(UInt(1)), name="b")
        self.s = IO(Input(Bool()), name="s")
        self.y = IO(Output(UInt(1)), name="y")

class Top(Module):
    def elaborate(self):
        self.sig_a = IO(Input(UInt(4)), name="sig_a")
        self.sig_b = IO(Input(UInt(4)), name="sig_b")
        self.sel = IO(Input(Bool()), name="sel")
        self.out = IO(Output(UInt(4)), name="out")

        mux = instance(TSMCMux(), name="u_mux", count=4)
        mux.a @= self.sig_a
        mux.b @= self.sig_b
        mux.s @= self.sel
        self.out @= mux.y
```

Emits:

```verilog
module Top (
  input  logic [3:0] sig_a,
  input  logic [3:0] sig_b,
  input  logic       sel,
  output logic [3:0] out
);

  TSMCMux u_mux[3:0] (
    .a (sig_a),
    .b (sig_b),
    .s (sel),
    .y (out)
  );

endmodule
```

The Verilog tool handles width slicing/broadcasting automatically:
- 4-bit signal connected to 1-bit port → sliced across 4 instances
- 1-bit signal connected to 1-bit port → broadcast to all instances

> **⚠️ Width checks are disabled for array instances.** plane does not validate that connection widths match port widths × count. You must ensure the widths are correct — the downstream Verilog tool will catch mismatches.

### Parameterized Count

`count` can be a `Parameter` for parameterized array sizes:

```python
class Top(Module):
    def elaborate(self):
        self.W = Parameter("W", 4)
        self.sig_a = IO(Input(UInt(4)), name="sig_a")
        # ...
        mux = instance(TSMCMux(), name="u_mux", count=self.W)
```

Emits `TSMCMux u_mux[W-1:0]` with `parameter int W = 4`.

### Output Fanout

Array instance outputs cannot drive multiple sinks directly (the intermediate wire would have incorrect width). Use an explicit wire:

```python
mux = instance(TSMCMux(), name="u_mux", count=4)
# ...
self.mux_y = Wire(UInt(4), name="mux_y")
self.mux_y @= mux.y
self.out @= self.mux_y
self.debug @= self.mux_y
```

## Gotchas

- **`instance()` returns a module reference** — Access ports as `inst.port_name`, not `inst["port_name"]`.
- **Dedup is structural** — Modules with the same name but different logic are not merged.
- **Unconnected ports are allowed** — plane does not require all child ports to be connected.

## Next

Read the [Parameters](09_parameters.md) section to learn about module parameters and parameterized types.
