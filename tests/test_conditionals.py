from tests.conftest import compile_verilog
import pytest
from plane import *


class TestWhen:
    """Test When/ElseWhen/Otherwise Verilog emission."""

    def test_when_only(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.x = IO(Output(Bits(1)), name="x")

                with AlwaysComb():
                    with When(self.a):
                        self.x @= Literal(1)

        expected = """module M (
  input  logic a,
  output logic x
);

  always_comb begin
    if (a) begin
      x = 1'd1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_when_otherwise(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.x = IO(Output(Bits(1)), name="x")

                with AlwaysComb():
                    with When(self.a):
                        self.x @= Literal(1)
                    with Otherwise():
                        self.x @= Literal(0)

        expected = """module M (
  input  logic a,
  output logic x
);

  always_comb begin
    if (a) begin
      x = 1'd1;
    end
    else begin
      x = 1'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_when_elsewhen_otherwise(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.b = IO(Input(Bits(1)), name="b")
                self.x = IO(Output(Bits(1)), name="x")

                with AlwaysComb():
                    with When(self.a):
                        self.x @= Literal(1)
                    with ElseWhen(self.b):
                        self.x @= Literal(2)
                    with Otherwise():
                        self.x @= Literal(0)

        expected = """module M (
  input  logic a,
  input  logic b,
  output logic x
);

  always_comb begin
    if (a) begin
      x = 1'd1;
    end
    else if (b) begin
      x = 1'd2;
    end
    else begin
      x = 1'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestSwitch:
    """Test Switch/Case/Default Verilog emission."""

    def test_switch_case_default(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")

                with AlwaysComb():
                    with Switch(self.sel):
                        with Case(0):
                            self.out @= Literal(0, 8)
                        with Case(1):
                            self.out @= Literal(1, 8)
                        with Default():
                            self.out @= Literal(255, 8)

        expected = """module M (
  input  logic [1:0] sel,
  output logic [7:0] out
);

  always_comb begin
    case (sel)
      2'd0: begin
        out = 8'd0;
      end
      2'd1: begin
        out = 8'd1;
      end
      default: begin
        out = 8'd255;
      end
    endcase
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_multiple_cases(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")

                with AlwaysComb():
                    with Switch(self.sel):
                        with Case(0):
                            self.out @= Literal(0, 8)
                        with Case(1):
                            self.out @= Literal(1, 8)
                        with Case(2):
                            self.out @= Literal(2, 8)
                        with Default():
                            self.out @= Literal(255, 8)

        expected = """module M (
  input  logic [1:0] sel,
  output logic [7:0] out
);

  always_comb begin
    case (sel)
      2'd0: begin
        out = 8'd0;
      end
      2'd1: begin
        out = 8'd1;
      end
      2'd2: begin
        out = 8'd2;
      end
      default: begin
        out = 8'd255;
      end
    endcase
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestNesting:
    """Test nested conditionals Verilog emission."""

    def test_when_nested_switch(self):
        class M(Module):
            def elaborate(self):
                self.cond = IO(Input(Bits(1)), name="cond")
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")

                with AlwaysComb():
                    with When(self.cond):
                        with Switch(self.sel):
                            with Case(0):
                                self.out @= Literal(10, 8)
                            with Case(1):
                                self.out @= Literal(11, 8)
                    with Otherwise():
                        self.out @= Literal(0, 8)

        expected = """module M (
  input  logic       cond,
  input  logic [1:0] sel,
  output logic [7:0] out
);

  always_comb begin
    if (cond) begin
      case (sel)
        2'd0: begin
          out = 8'd10;
        end
        2'd1: begin
          out = 8'd11;
        end
      endcase
    end
    else begin
      out = 8'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


    def test_switch_nested_when(self):
        class M(Module):
            def elaborate(self):
                self.cond = IO(Input(Bits(1)), name="cond")
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")

                with AlwaysComb():
                    with Switch(self.sel):
                        with Case(0):
                            with When(self.cond):
                                self.out @= Literal(10, 8)
                        with Default():
                            self.out @= Literal(0, 8)

        expected = """module M (
  input  logic       cond,
  input  logic [1:0] sel,
  output logic [7:0] out
);

  always_comb begin
    case (sel)
      2'd0: begin
        if (cond) begin
          out = 8'd10;
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


    def test_deep_nesting(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.b = IO(Input(Bits(1)), name="b")
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")

                with AlwaysComb():
                    with When(self.a):
                        with Switch(self.sel):
                            with Case(0):
                                with When(self.b):
                                    self.out @= Literal(1, 8)
                            with Case(1):
                                self.out @= Literal(2, 8)
                    with Otherwise():
                        self.out @= Literal(0, 8)

        expected = """module M (
  input  logic       a,
  input  logic       b,
  input  logic [1:0] sel,
  output logic [7:0] out
);

  always_comb begin
    if (a) begin
      case (sel)
        2'd0: begin
          if (b) begin
            out = 8'd1;
          end
        end
        2'd1: begin
          out = 8'd2;
        end
      endcase
    end
    else begin
      out = 8'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestMultipleAlwaysComb:
    def test_multiple_alwayscomb_blocks(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.b = IO(Input(Bits(1)), name="b")
                self.x = IO(Output(Bits(1)), name="x")
                self.y = IO(Output(Bits(1)), name="y")

                with AlwaysComb():
                    with When(self.a):
                        self.x @= Literal(1)
                    with Otherwise():
                        self.x @= Literal(0)

                with AlwaysComb():
                    with When(self.b):
                        self.y @= Literal(1)
                    with Otherwise():
                        self.y @= Literal(0)

        expected = """module M (
  input  logic a,
  input  logic b,
  output logic x,
  output logic y
);

  always_comb begin
    if (a) begin
      x = 1'd1;
    end
    else begin
      x = 1'd0;
    end
  end

  always_comb begin
    if (b) begin
      y = 1'd1;
    end
    else begin
      y = 1'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestErrorCases:
    def test_elsewhen_without_when(self):
        class M(Module):
            def elaborate(self):
                self.b = IO(Input(Bits(1)), name="b")
                with ElseWhen(self.b):
                    pass

        m = M()
        Builder.push(m)
        with pytest.raises(RuntimeError, match="ElseWhen must follow"):
            m.elaborate()
        Builder.pop()

    def test_otherwise_without_when(self):
        class M(Module):
            def elaborate(self):
                with Otherwise():
                    pass

        m = M()
        Builder.push(m)
        with pytest.raises(RuntimeError, match="Otherwise must follow"):
            m.elaborate()
        Builder.pop()

    def test_case_without_switch(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(Bits(2)), name="sel")
                with Case(0):
                    pass

        m = M()
        Builder.push(m)
        with pytest.raises(RuntimeError, match="Case must be inside Switch"):
            m.elaborate()
        Builder.pop()


class TestClockReset:
    def test_clockreset_override(self):
        class M(Module):
            def elaborate(self):
                self.clk1 = IO(Input(Clock()), name="clk1")
                self.clk2 = IO(Input(Clock()), name="clk2")
                self.rst = IO(Input(Reset()), name="rst")
                self.a = IO(Input(Bits(8)), name="a")

                self.r1 = Reg(Bits(8), name="r1")
                self.r1 @= self.a

                with ClockReset(clk=self.clk2):
                    self.r2 = Reg(Bits(8), name="r2")
                    self.r2 @= self.a

                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out1 @= self.r1
                self.out2 @= self.r2

        expected = """module M (
  input  logic       clk1,
  input  logic       clk2,
  input  logic       rst,
  input  logic [7:0] a,
  output logic [7:0] out1,
  output logic [7:0] out2
);

  always_ff @(posedge clk1 or negedge rst) begin
    if (!rst) begin
      out1 <= 8'd0; // optimized from r1
    end else begin
      out1 <= a; // optimized from r1
    end
  end

  always_ff @(posedge clk2 or negedge rst) begin
    if (!rst) begin
      out2 <= 8'd0; // optimized from r2
    end else begin
      out2 <= a; // optimized from r2
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)
