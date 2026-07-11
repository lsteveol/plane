# FSM Example

This example puts together enums, `AlwaysComb`, `Switch`/`Case`, registers, and the default assignment pattern to build a simple state machine.

## Traffic Light Controller

```python
from plane import *

class Light(PlaneEnum):
    RED = 0
    YELLOW = 1
    GREEN = 2

class TrafficLight(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        self.ped = IO(Input(Bool()), name="ped")
        self.light = IO(Output(Light), name="light")

        # Disable optimization to show state register explicitly in Verilog
        self.state = Reg(Light, init=Light.RED, name="state", optimize=False)
        self.state_next = Wire(Light, name="state_next")

        with AlwaysComb():
            self.state_next @= Light.RED
            with Switch(self.state):
                with Case(Light.RED):
                    self.state_next @= Light.GREEN
                with Case(Light.GREEN):
                    with When(self.ped):
                        self.state_next @= Light.YELLOW
                    with Otherwise():
                        self.state_next @= Light.GREEN
                with Case(Light.YELLOW):
                    self.state_next @= Light.RED

        self.state @= self.state_next
        self.light @= self.state
```

Emits (package mode):

```verilog
package TrafficLight_pkg;
  typedef enum logic [1:0] { RED, YELLOW, GREEN } Light_t;
endpackage

module TrafficLight (
  input  logic       clk,
  input  logic       rst,
  input  logic       ped,
  output logic [1:0] light
);

  import TrafficLight_pkg::*;

  Light_t state_next;
  Light_t state;

  assign light = state;

  always_comb begin
    state_next = Light_t::RED;
    case (state)
      Light_t::RED: begin
        state_next = Light_t::GREEN;
      end
      Light_t::GREEN: begin
        if (ped) begin
          state_next = Light_t::YELLOW;
        end
        else begin
          state_next = Light_t::GREEN;
        end
      end
      Light_t::YELLOW: begin
        state_next = Light_t::RED;
      end
    endcase
  end

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      state <= Light_t::RED;
    end else begin
      state <= state_next;
    end
  end

endmodule
```

## Pattern

The standard FSM pattern in plane:

1. Define states with a `PlaneEnum` subclass
2. Create a state register: `Reg(MyEnum, init=MyEnum.INIT, name="state")`
3. Create a next-state wire: `Wire(MyEnum, name="state_next")`
4. In `AlwaysComb`, set default next state, then use `Switch`/`Case` for transitions
5. Assign `self.state @= self.state_next` outside `AlwaysComb` for the sequential update

## Gotchas

- **Use `Switch`/`Case` for state machines** — `When`/`ElseWhen` works but `Switch`/`Case` is cleaner for FSMs.
- **Default assignment prevents latches** — Always assign a default next state before the `Switch`.
- **Enum reset values are named** — `Reg(Light, init=Light.RED, ...)` emits `state <= Light_t::RED;` in package mode.

## Next

Read the [Comments](14_comments.md) section to learn about adding `//` comments to generated Verilog.
