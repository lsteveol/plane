# Combinational Logic

plane provides operators, muxes, concatenation, slicing, and reduction operations for combinational logic.

## Operators

All standard arithmetic and bitwise operators work on hardware nodes:

```python
from plane import *

class Ops(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.b = IO(Input(UInt(8)), name="b")
        self.add = IO(Output(UInt(8)), name="add")
        self.and_ = IO(Output(UInt(8)), name="and")
        self.eq = IO(Output(Bool()), name="eq")

        self.add @= self.a + self.b
        self.and_ @= self.a & self.b
        self.eq @= self.a == self.b
```

| Operator | Result | Description |
|----------|--------|-------------|
| `a + b` | `max(Wa, Wb)` | Add |
| `a - b` | `max(Wa, Wb)` | Subtract |
| `a * b` | `max(Wa, Wb)` | Multiply |
| `a / b` | `max(Wa, Wb)` | Divide |
| `a % b` | `max(Wa, Wb)` | Modulo |
| `a & b` | `max(Wa, Wb)` | Bitwise AND |
| `a \| b` | `max(Wa, Wb)` | Bitwise OR |
| `a ^ b` | `max(Wa, Wb)` | Bitwise XOR |
| `a << b` | `max(Wa, Wb)` | Shift left |
| `a >> b` | `max(Wa, Wb)` | Shift right |
| `~a` | `Wa` | Bitwise NOT |
| `-a` | `Wa` | Negate |
| `a == b` | 1 | Equal |
| `a != b` | 1 | Not equal |
| `a < b` | 1 | Less than |
| `a <= b` | 1 | Less or equal |
| `a > b` | 1 | Greater than |
| `a >= b` | 1 | Greater or equal |

Int operands are auto-wrapped in `Literal`:

```python
self.out @= self.a + 1  # 1 becomes Literal(1, width_of_a)
```

## Mux

`Mux(sel, then_, else_)` creates a conditional expression:

```python
self.out @= Mux(self.sel, self.a, self.b)
```

Emits `(sel ? a : b)`. Width is `max(width(then_), width(else_))`.

## Concatenation

`Cat(*parts)` concatenates values, MSB first:

```python
self.out @= Cat(self.a, self.b)  # {a, b}
```

Emits `{a, b}`. Width is the sum of all part widths.

## Slicing

Slice notation `[hi:lo]` extracts a range. Single index `[i]` extracts bit `i`:

```python
self.slice_out @= self.a[7:4]  # 4 bits
self.bit_out @= self.a[0]      # 1 bit
```

Emits `a[7:4]` and `a[0]` respectively.

## Bit Assignment

Assign to a slice or bit using `assign()`:

```python
assign(self.a[7:4], self.b)
```

## Reductions

Reduction operators collapse a vector to 1 bit:

```python
self.all_ones @= AndR(self.a)  # &a
self.any_one @= OrR(self.a)    # |a
self.parity @= XorR(self.a)    # ^a
```

Emits:

```verilog
assign all_ones = &a;
assign any_one = |a;
assign parity = ^a;
```

## Extension

Zero-extend and sign-extend to a wider width:

```python
self.zext @= zext(self.a, 8)  # {4'd0, a} for 4-bit a
self.sext @= sext(self.s, 8)  # {4{s[3]}, s} for 4-bit s
```

Emits:

```verilog
assign zext = {4'd0, a};
assign sext = {4{s[3]}, s};
```

## Gotchas

- **Comparisons return nodes** — `a == b` produces a 1-bit hardware signal, not a Python boolean. Use it in `When()` conditions, not Python `if` statements.
- **Width is max, not sum** — `a + b` where both are 8-bit produces an 8-bit result. Truncation happens silently. Use wider types if you need to avoid overflow.
- **`Cat` is MSB-first** — `Cat(a, b)` emits `{a, b}`, so `a` is the most significant part.

## Next

Read the [Sequential Logic](05_sequential_logic.md) section to learn about registers, clock/reset resolution, and reset strategies.
