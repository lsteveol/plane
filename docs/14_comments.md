# Comments

plane lets you attach `//` comments to hardware nodes and contexts. Comments are emitted in the generated Verilog at the relevant emission point for each node type.

## Setting Comments

Comments can be set two ways:

**Constructor parameter:**

```python
self.r = Reg(UInt(8), name="r", comment="Pipeline register")
```

**Assignment:**

```python
self.r = Reg(UInt(8), name="r")
self.r.comment = "Pipeline register"
```

Both produce the same output. The constructor parameter is more concise; assignment is useful when the comment depends on runtime logic.

## Where Comments Appear

| Node | Emission point | Example |
|------|---------------|---------|
| `Reg` | Before the `always_ff` block | `// Pipeline register` above `always_ff` |
| `Wire` | Before the `assign` statement | `// Intermediate sum` above `assign w = ...` |
| `IO` (port) | Before the port declaration | `// System clock` above `input logic clk` |
| `Module` | Before the instance | `// Timer block` above `Timer timer_inst (` |
| `AlwaysComb` | Before the `always_comb` block | `// Combinational logic` above `always_comb begin` |
| `When` / `ElseWhen` / `Otherwise` | Before the `if` / `else if` / `else` line | `// First condition` above `if (cond) begin` |
| `Switch` | Before the `case` line | `// State machine` above `case (state)` |
| `Case` / `Default` | Before the case item | `// IDLE state` above `IDLE: begin` |

## Registers

```python
class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        self.a = IO(Input(UInt(8)), name="a")
        self.out = IO(Output(UInt(8)), name="out")

        self.r = Reg(UInt(8), name="r", comment="Pipeline register")
        self.r @= self.a
        self.out @= self.r
```

Emits:

```verilog
  // Pipeline register
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out <= 8'd0;
    end else begin
      out <= a;
    end
  end
```

When registers are grouped (the default), all comments are collected and emitted before the shared `always_ff` block:

```python
self.r1 = Reg(UInt(8), name="r1", comment="First register")
self.r1 @= self.a
self.r2 = Reg(UInt(8), name="r2", comment="Second register")
self.r2 @= self.b
```

Emits:

```verilog
  // First register
  // Second register
  always_ff @(posedge clk or negedge rst) begin
    ...
  end
```

## Wires

Comments on wires appear before the `assign` statement where the wire is the sink:

```python
self.w = Wire(UInt(8), name="w", comment="Intermediate sum")
self.w @= self.a + self.b
self.out @= self.w * 2
```

Emits:

```verilog
  // Intermediate sum
  assign w   = (a + b);
  assign out = (w * 8'd2);
```

## Ports

Comments on ports appear before the port declaration in the module header:

```python
self.clk = IO(Input(Clock()), name="clk", comment="System clock")
self.rst = IO(Input(AsyncLowReset()), name="rst", comment="Active-low reset")
self.a = IO(Input(UInt(8)), name="a", comment="Data input")
self.out = IO(Output(UInt(8)), name="out", comment="Data output")
```

Emits:

```verilog
module M (
  // System clock
  input  logic       clk,
  // Active-low reset
  input  logic       rst,
  // Data input
  input  logic [7:0] a,
  // Data output
  output logic [7:0] out
);
```

## Instances

Set `comment` on a child module to emit a comment before the instance:

```python
class Top(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        timer = instance(Timer(), name="timer_inst")
        timer.comment = "Timer peripheral"
        timer.clk @= self.clk
```

Emits:

```verilog
  // Timer peripheral
  Timer timer_inst (
    .clk (clk)
  );
```

## Conditionals

Comments on `AlwaysComb`, `When`, `ElseWhen`, `Otherwise`, `Switch`, `Case`, and `Default` are emitted before their respective lines:

```python
with AlwaysComb(comment="FSM next-state logic"):
    with Switch(self.state, comment="State machine"):
        with Case(State.IDLE, comment="IDLE state"):
            self.nstate @= State.BUSY
        with Case(State.BUSY, comment="BUSY state"):
            self.nstate @= State.DONE
        with Default(comment="Safety default"):
            self.nstate @= State.IDLE
```

Emits:

```verilog
  // FSM next-state logic
  always_comb begin
    // State machine
    case (state)
      // IDLE state
      State_IDLE: begin
        nstate = State_BUSY;
      end
      // BUSY state
      State_BUSY: begin
        nstate = State_DONE;
      end
      // Safety default
      default: begin
        nstate = State_IDLE;
      end
    endcase
  end
```

Comments work at any nesting level:

```python
with Switch(self.sel):
    with Case(0, comment="Case 0"):
        with When(self.cond, comment="Nested condition"):
            self.out @= self.a
```

Emits:

```verilog
    case (sel)
      // Case 0
      2'd0: begin
        // Nested condition
        if (cond) begin
          out = a;
        end
      end
    endcase
```

## Multi-Line Comments

Use `\n` or triple-quoted strings for multi-line comments. Each line is prefixed with `//`:

```python
self.r = Reg(UInt(8), name="r", comment="Pipeline register\nStage 2 of 3")
```

Emits:

```verilog
  // Pipeline register
  // Stage 2 of 3
  always_ff @(posedge clk) begin
    ...
  end
```

## Gotchas

- **Comments are plain text** — plane does not validate comment content. Ensure it's meaningful.
- **Wire comments appear at the assign, not the declaration** — A wire's `comment` is emitted before the `assign` where it's the sink, not before the `logic [...] w;` declaration.
- **Reg comments appear before always_ff, not the declaration** — Same pattern: the comment goes before the `always_ff` block, not the `logic [...] r;` declaration.
- **Grouped always_ff collects all comments** — When registers share an `always_ff` block, all their comments are emitted together before the block.

## Next

Read the [CSR Generation](15_csr.md) section to learn about defining control and status registers and generating hardware, UVM RAL models, and documentation.
