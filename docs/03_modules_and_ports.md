# Modules & Ports

Every plane circuit is a `Module` subclass. The `elaborate` method is where you declare ports, wires, registers, and connections.

## Basic Module

```python
from plane import *

class Adder(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.s = IO(Output(UInt(8)), name="s")
        self.s @= self.a + self.b
```

Call `emitVerilog(Adder())` to generate Verilog:

```verilog
module Adder (
  input logic [7:0] a,
  input logic [7:0] b,
  output logic [7:0] s
);

  assign s = (a + b);

endmodule
```

## Ports

Ports are declared with `IO(direction, name=...)`. The `name` is required.

| Direction | Description |
|-----------|-------------|
| `Input(T)` | Input port of type `T` |
| `Output(T)` | Output port of type `T` |
| `Inout(T)` | Bidirectional port of type `T` |

```python
self.clk = IO(Input(Clock()), name="clk")
self.data = IO(Input(UInt(8)), name="data")
self.valid = IO(Output(Bool()), name="valid")
self.bus = IO(Inout(UInt(8)), name="bus")
```

## Naming

### Module Names

By default the emitted module name is the class name. Override with `desired_name`:

```python
class MyCounter(Module):
    def __init__(self):
        super().__init__(desired_name="FastCounter")

    def elaborate(self):
        ...
```

Emits `module FastCounter (...)`.

### Wire and Register Names

Wires and registers are auto-named with a counter if no `name` is given:

```python
self.w = Wire(UInt(8))   # -> wire_0
self.r = Reg(UInt(8))    # -> reg_0
```

Provide a name for readability:

```python
self.sum_wire = Wire(UInt(8), name="sum_wire")
self.counter = Reg(UInt(8), name="counter")
```

### Module Name Transformations

plane supports two global transformations for module names (useful for design uniquification and naming convention compliance):

**Snake case conversion** — Convert CamelCase module names to snake_case:

```python
from plane import utils

utils.convert_module_names_to_snake_case = True

class MyApbFanout(Module):
    def elaborate(self):
        ...

# Emits: module my_apb_fanout (...)
```

**Module prefix** — Add a prefix to all module names:

```python
utils.module_prefix = "my_prefix"

class Counter(Module):
    def elaborate(self):
        ...

# Emits: module my_prefix_Counter (...)
```

**Ordering** — Transformations are applied in order: snake_case → dedup suffix → prefix:

```python
utils.convert_module_names_to_snake_case = True
utils.module_prefix = "my_prefix"

class MyApbFanout(Module):
    def elaborate(self):
        ...

# Emits: module my_prefix_my_apb_fanout (...)
```

**BlackBox exemption** — BlackBox modules are excluded from both transformations (they refer to external definitions):

```python
class TSMCMux(BlackBox):
    def elaborate(self):
        ...

# With both transformations enabled, still emits: TSMCMux tsmcmux (...)
```

## Wires

`Wire(T)` creates a combinational signal:

```python
class Adder(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.s = IO(Output(UInt(8)), name="s")
        self.sum_wire = Wire(UInt(8), name="sum_wire")
        self.sum_wire @= self.a + self.b
        self.s @= self.sum_wire
```

## Registers

`Reg(T)` creates a clocked register. Requires an implicit clock (from a `Clock` port) or explicit `clk=`:

```python
class Counter(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.out = IO(Output(UInt(8)), name="out")
        self.counter = Reg(UInt(8), init=0, name="counter")
        self.counter @= self.counter + Literal(1, 8)
        self.out @= self.counter
```

`RegNext(next, ...)` is a convenience that takes the next value in the constructor:

```python
self.r = RegNext(self.a + self.b, name="r")
```

## Connection Operator

`@=` connects a source to a sink. It is not Python assignment:

```python
self.out @= self.w  # hardware connection
self.w = Wire(...)   # Python attribute assignment
```

plane validates that all output ports are driven before emission.

## Gotchas

- **Port names are required** — `IO()` will raise if `name` is missing.
- **`@=` vs `=`** — `self.x = y` is Python assignment. `self.x @= y` is a hardware connection.
- **Output ports must be driven** — plane will error if an output port has no driver.

## Next

Read the [Combinational Logic](04_combinational_logic.md) section to learn about operators, muxes, concatenation, and slicing.
