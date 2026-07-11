# Attributes

`Attribute` lets you attach custom annotations to hardware nodes. They are emitted before the node declaration as raw SystemVerilog text.

## Custom Attributes

Subclass `Attribute` and override `content()`:

```python
from plane import *

class DontTouchAttr(Attribute):
    def content(self):
        return '(* dont_touch = "true" *)'

class M(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.r = Reg(UInt(8), name="r")
        DontTouchAttr(self.r)
        self.r @= self.r + Literal(1, 8)
```

Emits:

```verilog
module M (
  input logic clk
);

  (* dont_touch = "true" *)
  logic [7:0] r;

  always_ff @(posedge clk) begin
    r <= (r + 8'd1);
  end

endmodule
```

## How It Works

- `Attribute(node)` auto-registers with the node on construction
- `content()` returns the string emitted before the node's declaration
- The content is emitted verbatim — you control the exact string


## Gotchas

- **Attributes are emitted verbatim** — plane does not validate the string. Make sure it's valid SystemVerilog.
- **Attributes are per-node** — Each attribute instance attaches to one node. Create multiple instances for multiple attributes on the same node.

## Next

Read the [Width Checking](12_width_checking.md) section to learn about width mismatch detection.
