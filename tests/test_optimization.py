"""Tests for register optimization and auto-naming features."""

from plane import *
from tests.conftest import compile_verilog


class TestSingleOutputPortOptimization:
    def test_single_output_port(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out = IO(Output(UInt(8)), name="out")
                self.r = Reg(UInt(8), name="r")
                self.r @= self.in1
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out
);

  always_ff @(posedge clk) begin
    out <= in1; // optimized from r
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestMultipleOutputPortsOptimization:
    def test_multiple_output_ports(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out2 = IO(Output(UInt(8)), name="out2")
                self.out3 = IO(Output(UInt(8)), name="out3")
                self.r = Reg(UInt(8), name="r")
                self.r @= self.in1
                self.out1 @= self.r
                self.out2 @= self.r
                self.out3 @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out1,
  output logic [7:0] out2,
  output logic [7:0] out3
);

  assign out2 = out1; // optimized from r
  assign out3 = out1; // optimized from r

  always_ff @(posedge clk) begin
    out1 <= in1; // optimized from r
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestMixedLoadsOptimization:
    def test_mixed_loads(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out2 = IO(Output(UInt(8)), name="out2")
                self.w = Wire(UInt(8), name="w")
                self.r = Reg(UInt(8), name="r")
                self.r @= self.in1
                self.out1 @= self.r
                self.out2 @= self.r
                self.w @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out1,
  output logic [7:0] out2
);

  logic [7:0] w;

  assign out2 = out1; // optimized from r
  assign w    = out1; // optimized from r

  always_ff @(posedge clk) begin
    out1 <= in1; // optimized from r
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestNoOutputPortNoOptimization:
    def test_no_output_port(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out = IO(Output(UInt(8)), name="out")
                self.w = Wire(UInt(8), name="w")
                self.r = Reg(UInt(8), name="r")
                self.r @= self.in1
                self.w @= self.r
                self.out @= self.w

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out
);

  logic [7:0] w;
  logic [7:0] r;

  assign w   = r;
  assign out = w;

  always_ff @(posedge clk) begin
    r <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestOptimizationDisabled:
    def test_optimization_disabled(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out = IO(Output(UInt(8)), name="out")
                self.r = Reg(UInt(8), name="r", optimize=False)
                self.r @= self.in1
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out
);

  logic [7:0] r;

  assign out = r;

  always_ff @(posedge clk) begin
    r <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAutoNamingReg:
    def test_auto_naming_reg(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.r1 = Reg(UInt(8))
                self.r2 = Reg(UInt(8))
                self.r3 = Reg(UInt(8))
                self.r1 @= self.in1
                self.r2 @= self.in1
                self.r3 @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1
);

  logic [7:0] auto_reg_0;
  logic [7:0] auto_reg_1;
  logic [7:0] auto_reg_2;

  always_ff @(posedge clk) begin
    auto_reg_0 <= in1;
    auto_reg_1 <= in1;
    auto_reg_2 <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAutoNamingRegNext:
    def test_auto_naming_regnext(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.r1 = RegNext(self.in1)
                self.r2 = RegNext(self.in1)

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1
);

  logic [7:0] auto_reg_0;
  logic [7:0] auto_reg_1;

  always_ff @(posedge clk) begin
    auto_reg_0 <= in1;
    auto_reg_1 <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAutoNamingWithExplicitNames:
    def test_mixed_names(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.r1 = Reg(UInt(8), name="my_reg")
                self.r2 = Reg(UInt(8))
                self.r3 = Reg(UInt(8), name="another_reg")
                self.r4 = Reg(UInt(8))
                self.r1 @= self.in1
                self.r2 @= self.in1
                self.r3 @= self.in1
                self.r4 @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1
);

  logic [7:0] my_reg;
  logic [7:0] auto_reg_0;
  logic [7:0] another_reg;
  logic [7:0] auto_reg_1;

  always_ff @(posedge clk) begin
    my_reg      <= in1;
    auto_reg_0  <= in1;
    another_reg <= in1;
    auto_reg_1  <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAutoNamingConflictResolution:
    def test_conflict_resolution(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.auto_reg_0 = Wire(UInt(8), name="auto_reg_0")
                self.r = Reg(UInt(8))
                self.r @= self.in1
                self.auto_reg_0 @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1
);

  logic [7:0] auto_reg_0;
  logic [7:0] auto_reg_1;

  assign auto_reg_0 = auto_reg_1;

  always_ff @(posedge clk) begin
    auto_reg_1 <= in1;
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAutoNamingWithOptimization:
    def test_auto_naming_with_optimization(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out = IO(Output(UInt(8)), name="out")
                self.r = Reg(UInt(8))
                self.r @= self.in1
                self.out @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out
);

  always_ff @(posedge clk) begin
    out <= in1; // optimized from auto_reg_0
  end

endmodule"""

        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)
