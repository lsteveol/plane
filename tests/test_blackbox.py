from tests.conftest import compile_verilog
import pytest
from plane import *

MY_BLACKBOX_STUB = """
module MyBlackBox (
  input  logic clk,
  input  logic [7:0] data_in,
  output logic [7:0] data_out
);
endmodule
"""

BUNDLE_BLACKBOX_STUB = """
module BundleBlackBox (
  input  logic [7:0] s_data,
  input  logic s_valid
);
endmodule
"""

PARAM_BLACKBOX_STUB = """
module ParamBlackBox (
  input  logic clk,
  input  logic data_in,
  output logic data_out
);
  parameter WIDTH = 8;
endmodule
"""


class MyBlackBox(BlackBox):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.data_in = IO(Input(Bits(8)), name="data_in")
        self.data_out = IO(Output(Bits(8)), name="data_out")


class TestBlackBoxBasic:
    def test_blackbox_instance_only(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(8)), name="data_in")
                self.bb = instance(MyBlackBox())
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in

        expected = """module Top (
  input  logic       clk,
  input  logic [7:0] data_in
);

  MyBlackBox myblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + MY_BLACKBOX_STUB)

    def test_blackbox_port_connections(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(Input(Bits(8)), name="data_in")
                self.bb = instance(MyBlackBox())
                self.bb.clk @= self.clk
                self.bb.data_in @= self.io

        expected = """module Top (
  input  logic       clk,
  input  logic [7:0] data_in
);

  MyBlackBox myblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + MY_BLACKBOX_STUB)

    def test_blackbox_output_usage(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(8)), name="data_in")
                self.io = IO(Output(Bits(8)), name="data_out")
                self.bb = instance(MyBlackBox())
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in
                self.io @= self.bb.data_out

        expected = """module Top (
  input  logic       clk,
  input  logic [7:0] data_in,
  output logic [7:0] data_out
);

  MyBlackBox myblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (data_out)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + MY_BLACKBOX_STUB)

    def test_multiple_blackbox_instances(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(8)), name="data_in")
                self.bb1 = instance(MyBlackBox())
                self.bb2 = instance(MyBlackBox())
                self.bb1.clk @= self.clk
                self.bb1.data_in @= self.data_in
                self.bb2.clk @= self.clk
                self.bb2.data_in @= self.data_in

        expected = """module Top (
  input  logic       clk,
  input  logic [7:0] data_in
);

  MyBlackBox myblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

  MyBlackBox myblackbox_1 (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + MY_BLACKBOX_STUB)

    def test_blackbox_with_bundle(self):
        class MyBundle(Bundle):
            data = Input(Bits(8))
            valid = Output(Bool())

        class BundleBlackBox(BlackBox):
            def elaborate(self):
                self.io = IO(MyBundle(), name="s")

        class Top(Module):
            def elaborate(self):
                self.bb = instance(BundleBlackBox())
                self.bb.io.data @= Literal(0, 8)

        expected = """module Top (
);

  BundleBlackBox bundleblackbox (
    .s_data  (8'd0),
    .s_valid (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + BUNDLE_BLACKBOX_STUB)


class ParamBlackBox(BlackBox):
    def elaborate(self):
        self.WIDTH = Parameter("WIDTH", 8)
        self.clk = IO(Input(Clock()), name="clk")
        self.data_in = IO(Input(Bits(self.WIDTH)), name="data_in")
        self.data_out = IO(Output(Bits(self.WIDTH)), name="data_out")


class TestBlackBoxParameters:
    def test_blackbox_parameter_default(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(8)), name="data_in")
                self.bb = instance(ParamBlackBox())
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in

        expected = """module Top (
  input  logic       clk,
  input  logic [7:0] data_in
);

  ParamBlackBox paramblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + PARAM_BLACKBOX_STUB)

    def test_blackbox_parameter_override_int(self):
        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(16)), name="data_in")
                self.bb = instance(ParamBlackBox(), params=(("WIDTH", 16),))
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in

        expected = """module Top (
  input  logic        clk,
  input  logic [15:0] data_in
);

  ParamBlackBox #(.WIDTH(16)) paramblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + PARAM_BLACKBOX_STUB)

    def test_blackbox_parameter_passthrough(self):
        class Top(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 32)
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(self.WIDTH)), name="data_in")
                self.bb = instance(ParamBlackBox(), params=(("WIDTH", self.WIDTH),))
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in

        expected = """module Top #(
  parameter int WIDTH = 32
) (
  input  logic             clk,
  input  logic [WIDTH-1:0] data_in
);

  ParamBlackBox #(.WIDTH(WIDTH)) paramblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (/* unconnected */)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + PARAM_BLACKBOX_STUB)

    def test_blackbox_parameter_with_connections(self):
        class Top(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 32)
                self.clk = IO(Input(Clock()), name="clk")
                self.data_in = IO(Input(Bits(self.WIDTH)), name="data_in")
                self.data_out = IO(Output(Bits(self.WIDTH)), name="data_out")
                self.bb = instance(ParamBlackBox(), params=(("WIDTH", self.WIDTH),))
                self.bb.clk @= self.clk
                self.bb.data_in @= self.data_in
                self.data_out @= self.bb.data_out

        expected = """module Top #(
  parameter int WIDTH = 32
) (
  input  logic             clk,
  input  logic [WIDTH-1:0] data_in,
  output logic [WIDTH-1:0] data_out
);

  ParamBlackBox #(.WIDTH(WIDTH)) paramblackbox (
    .clk      (clk),
    .data_in  (data_in),
    .data_out (data_out)
  );

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv + PARAM_BLACKBOX_STUB)
