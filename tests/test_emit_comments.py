from tests.conftest import compile_verilog
import pytest
from plane import *


class TestAlwaysFFComments:
    def test_single_reg_comment(self):
        class M(Module):
            group_always_ff = False
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.r = Reg(Bits(8), name="r")
                self.r.comment = "This is register r"
                self.r @= self.a
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  output logic [7:0] out
);

  // This is register r
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out <= 8'd0; // optimized from r
    end else begin
      out <= a; // optimized from r
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_comment_constructor_parameter(self):
        class M(Module):
            group_always_ff = False
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.r = Reg(Bits(8), name="r", comment="Pipeline register")
                self.r @= self.a
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  output logic [7:0] out
);

  // Pipeline register
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out <= 8'd0; // optimized from r
    end else begin
      out <= a; // optimized from r
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_grouped_multiple_comments(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.r1 = Reg(Bits(8), name="r1")
                self.r1.comment = "First register"
                self.r1 @= self.a
                self.out1 @= self.r1
                self.r2 = Reg(Bits(8), name="r2")
                self.r2.comment = "Second register"
                self.r2 @= self.b
                self.out2 @= self.r2

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out1,
  output logic [7:0] out2
);

  // First register
  // Second register
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out1 <= 8'd0; // optimized from r1
      out2 <= 8'd0; // optimized from r2
    end else begin
      out1 <= a; // optimized from r1
      out2 <= b; // optimized from r2
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_grouped_partial_comments(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.r1 = Reg(Bits(8), name="r1")
                self.r1.comment = "Only this one has a comment"
                self.r1 @= self.a
                self.out1 @= self.r1
                self.r2 = Reg(Bits(8), name="r2")
                self.r2 @= self.b
                self.out2 @= self.r2

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out1,
  output logic [7:0] out2
);

  // Only this one has a comment
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out1 <= 8'd0; // optimized from r1
      out2 <= 8'd0; // optimized from r2
    end else begin
      out1 <= a; // optimized from r1
      out2 <= b; // optimized from r2
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAlwaysCombComments:
    def test_always_comb_comment(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                with AlwaysComb(comment="Compute output"):
                    self.out @= self.a | self.b

        expected = """module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  // Compute output
  always_comb begin
    out = (a | b);
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestConditionalComments:
    def test_when_elseif_otherwise_comments(self):
        class M(Module):
            def elaborate(self):
                self.cond1 = IO(Input(Bits(1)), name="cond1")
                self.cond2 = IO(Input(Bits(1)), name="cond2")
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.c = IO(Input(Bits(8)), name="c")
                self.out = IO(Output(Bits(8)), name="out")
                with AlwaysComb():
                    with When(self.cond1, comment="First condition"):
                        self.out @= self.a
                    with ElseWhen(self.cond2, comment="Second condition"):
                        self.out @= self.b
                    with Otherwise(comment="Default case"):
                        self.out @= self.c

        expected = """module M (
  input  logic       cond1,
  input  logic       cond2,
  input  logic [7:0] a,
  input  logic [7:0] b,
  input  logic [7:0] c,
  output logic [7:0] out
);

  always_comb begin
    // First condition
    if (cond1) begin
      out = a;
    end
    // Second condition
    else if (cond2) begin
      out = b;
    end
    // Default case
    else begin
      out = c;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestSwitchComments:
    def test_switch_case_default_comments(self):
        from plane import utils
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class State(PlaneEnum):
                IDLE = 0
                BUSY = 1
                DONE = 2

            class M(Module):
                def elaborate(self):
                    self.state = IO(Input(State), name="state")
                    self.nstate = IO(Output(State), name="nstate")
                    with AlwaysComb(comment="FSM next-state logic"):
                        with Switch(self.state, comment="State machine"):
                            with Case(State.IDLE, comment="This is the IDLE state"):
                                self.nstate @= State.BUSY
                            with Case(State.BUSY, comment="In BUSY state"):
                                self.nstate @= State.DONE
                            with Case(State.DONE):
                                self.nstate @= State.IDLE
                            with Default(comment="Safety default"):
                                self.nstate @= State.IDLE

            expected = """module M (
  input  logic [1:0] state,
  output logic [1:0] nstate
);

  localparam State_IDLE = 2'd0, State_BUSY = 2'd1, State_DONE = 2'd2;

  // FSM next-state logic
  always_comb begin
    // State machine
    case (state)
      // This is the IDLE state
      State_IDLE: begin
        nstate = State_BUSY;
      end
      // In BUSY state
      State_BUSY: begin
        nstate = State_DONE;
      end
      State_DONE: begin
        nstate = State_IDLE;
      end
      // Safety default
      default: begin
        nstate = State_IDLE;
      end
    endcase
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode

    def test_nested_when_in_switch(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(UInt(2)), name="sel")
                self.cond = IO(Input(Bits(1)), name="cond")
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                with AlwaysComb():
                    with Switch(self.sel):
                        with Case(0, comment="Case 0"):
                            with When(self.cond, comment="Nested when"):
                                self.out @= self.a
                            with Otherwise():
                                self.out @= self.b
                        with Default():
                            self.out @= 0

        expected = """module M (
  input  logic [1:0] sel,
  input  logic       cond,
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  always_comb begin
    case (sel)
      // Case 0
      2'd0: begin
        // Nested when
        if (cond) begin
          out = a;
        end
        else begin
          out = b;
        end
      end
      default: begin
        out = 8'd0;
      end
    endcase
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestInstanceComments:
    def test_instance_comment(self):
        class Child(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a

        class Top(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                child = instance(Child(), name="child_inst")
                child.comment = "This is the child instance"
                child._graph.nodes[0] @= self.a
                self.out @= child._graph.nodes[1]

        expected = """module Top (
  input  logic [7:0] a,
  output logic [7:0] out
);

  // This is the child instance
  Child child_inst (
    .a   (a),
    .out (out)
  );

endmodule

module Child (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)


class TestWireComments:
    def test_wire_comment_constructor_parameter(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.w = Wire(Bits(8), name="w", comment="Intermediate sum")
                self.w @= self.a + self.b
                self.out @= self.w * 2

        expected = """module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  logic [7:0] w;

  // Intermediate sum
  assign w   = (a + b);
  assign out = (w * 8'd2);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_wire_comment_assignment(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.w = Wire(Bits(8), name="w")
                self.w.comment = "Intermediate computation"
                self.w @= self.a + self.b
                self.out @= self.w

        expected = """module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  logic [7:0] w;

  // Intermediate computation
  assign w   = (a + b);
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestPortComments:
    def test_port_comment_constructor_parameter(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk", comment="System clock")
                self.rst = IO(Input(AsyncLowReset()), name="rst", comment="Active-low reset")
                self.a = IO(Input(Bits(8)), name="a", comment="Data input")
                self.out = IO(Output(Bits(8)), name="out", comment="Data output")
                self.out @= self.a

        expected = """module M (
  // System clock
  input  logic       clk,
  // Active-low reset
  input  logic       rst,
  // Data input
  input  logic [7:0] a,
  // Data output
  output logic [7:0] out
);

  // Data output
  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_port_comment_assignment(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.a.comment = "Input data"
                self.out = IO(Output(Bits(8)), name="out")
                self.out.comment = "Output data"
                self.out @= self.a

        expected = """module M (
  // Input data
  input  logic [7:0] a,
  // Output data
  output logic [7:0] out
);

  // Output data
  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestMultiLineComments:
    def test_multiline_comment(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.r = Reg(Bits(8), name="r")
                self.r.comment = "Multi-line comment\nLine 2\nLine 3"
                self.r @= self.a
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  output logic [7:0] out
);

  // Multi-line comment
  // Line 2
  // Line 3
  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out <= 8'd0; // optimized from r
    end else begin
      out <= a; // optimized from r
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBackwardCompat:
    def test_no_comment(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.r = Reg(Bits(8), name="r")
                self.r @= self.a
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] a,
  output logic [7:0] out
);

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      out <= 8'd0; // optimized from r
    end else begin
      out <= a; // optimized from r
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)
