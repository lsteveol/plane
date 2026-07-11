# Control Flow

plane provides `AlwaysComb`, `When`/`ElseWhen`/`Otherwise`, and `Switch`/`Case`/`Default` for conditional combinational logic.

## Flat Assignments

Without `AlwaysComb`, connections emit as flat `assign` statements:

```python
from plane import *

class FlatAdder(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.out = IO(Output(UInt(8)), name="out")
        self.out @= self.a + self.b
```

Emits:

```verilog
assign out = (a + b);
```

## AlwaysComb

Wrap conditional logic in `AlwaysComb()` to emit an `always_comb` block:

```python
with AlwaysComb():
    with When(self.sel):
        self.w @= self.a
    with Otherwise():
        self.w @= self.b
```

`AlwaysComb` is a context manager. All `@=` connections inside it are collected and emitted as part of a single `always_comb` block.

## Default Assignment Pattern

Assign a default value **before** any `When` to set the fallback. This avoids latch inference:

```python
with AlwaysComb():
    self.w @= Literal(0, 8)  # default
    with When(self.en):
        self.w @= Literal(1, 8)
```

Emits:

```verilog
always_comb begin
  w = 8'd0;
  if (en) begin
    w = 8'd1;
  end
end
```

This is the standard pattern for FSM next-state logic and any conditional where not every branch is covered.

## When / ElseWhen / Otherwise

Build if-else chains with `When`, `ElseWhen`, and `Otherwise`:

```python
from plane import *

class WhenExample(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.sel = IO(Input(Bool()), name="sel")
        self.out = IO(Output(UInt(8)), name="out")
        self.w = Wire(UInt(8), name="w")
        with AlwaysComb():
            with When(self.sel):
                self.w @= self.a + self.b
            with ElseWhen(self.a > self.b):
                self.w @= self.a - self.b
            with Otherwise():
                self.w @= Literal(0, 8)
        self.out @= self.w
```

Emits:

```verilog
always_comb begin
  if (sel) begin
    w = (a + b);
  end
  else if (a > b) begin
    w = (a - b);
  end
  else begin
    w = 8'd0;
  end
end
```

Rules:
- `When` must be the first in a chain (or nested inside another context)
- `ElseWhen` must follow `When` or another `ElseWhen`
- `Otherwise` must follow `When` or `ElseWhen` — it terminates the chain
- `Otherwise` is optional

## Switch / Case / Default

Build case statements with `Switch`, `Case`, and `Default`:

```python
from plane import *

class SwitchExample(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.sel = IO(Input(UInt(2)), name="sel")
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.c = IO(Input(UInt(8)), name="c")
        self.d = IO(Input(UInt(8)), name="d")
        self.out = IO(Output(UInt(8)), name="out")
        self.w = Wire(UInt(8), name="w")
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
        self.out @= self.w
```

Emits:

```verilog
always_comb begin
  case (sel)
    2'd0: begin
      w = a;
    end
    2'd1: begin
      w = b;
    end
    2'd2: begin
      w = c;
    end
    default: begin
      w = d;
    end
  endcase
end
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

Emits (package mode):

```verilog
case (op)
  MyOp_t::ADD: begin
    w = (a + b);
  end
  MyOp_t::SUB: begin
    w = (a - b);
  end
  default: begin
    w = a;
  end
endcase
```

Emits:

```verilog
always_comb begin
  case (sel)
    0: begin
      w = a;
    end
    1: begin
      w = b;
    end
    2: begin
      w = c;
    end
    default: begin
      w = d;
    end
  endcase
end
```

## Nesting

`When`/`ElseWhen`/`Otherwise` and `Switch` can be nested:

```python
with AlwaysComb():
    with When(self.en):
        with When(self.sel):
            self.w @= self.a + self.b
        with Otherwise():
            self.w @= self.a - self.b
    with Otherwise():
        self.w @= Literal(0, 8)
```

Emits:

```verilog
always_comb begin
  if (en) begin
    if (sel) begin
      w = (a + b);
    end
    else begin
      w = (a - b);
    end
  end
  else begin
    w = 8'd0;
  end
end
```

## Counter Pattern

The standard pattern for a conditional counter uses `AlwaysComb` with a next-value wire:

```python
class Counter(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.en = IO(Input(Bool()), name="en")
        self.out = IO(Output(UInt(8)), name="out")
        self.counter = Reg(UInt(8), init=0, name="counter")
        self.counter_next = Wire(UInt(8), name="counter_next")
        with AlwaysComb():
            self.counter_next @= Literal(0, 8)
            with When(self.en):
                self.counter_next @= self.counter + Literal(1, 8)
        self.counter @= self.counter_next
        self.out @= self.counter
```

Emits:

```verilog
always_comb begin
  counter_next = 8'd0;
  if (en) begin
    counter_next = (counter + 8'd1);
  end
end

always_ff @(posedge clk) begin
  counter <= counter_next;
end
```

## Gotchas

- **`When` conditions are hardware nodes** — `self.a > self.b` produces a 1-bit comparison node, not a Python boolean.
- **`AlwaysComb` is required for conditionals** — `When`/`Switch` must be inside `AlwaysComb()`.
- **`Otherwise` is optional** — If omitted, unassigned wires keep their previous value (latch inference in Verilog). Use the default assignment pattern to avoid latches.
- **`Reg @=` inside `AlwaysComb`** — Assigning to a reg inside `AlwaysComb` sets `reg.next`. The reg still emits as `always_ff`. Use a wire for the next value (as shown in the counter pattern) for clean separation.

## Next

Read the [Bundles & Vecs](07_bundles_and_vecs.md) section to learn about structured interfaces and arrays.
