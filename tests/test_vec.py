from tests.conftest import compile_verilog
import pytest
from plane import *


class TestVecWire:
    def test_vec_wire_expansion(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 4), name="v")
                self.v[0] @= Literal(1, 8)

        expected = """module Foo (
);

  logic [7:0] v_0;
  logic [7:0] v_1;
  logic [7:0] v_2;
  logic [7:0] v_3;

  assign v_0 = 8'd1;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_wire_indexed_assignment(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 2), name="v")
                self.v[0] @= Literal(42, 8)
                self.v[1] @= Literal(99, 8)

        expected = """module Foo (
);

  logic [7:0] v_0;
  logic [7:0] v_1;

  assign v_0 = 8'd42;
  assign v_1 = 8'd99;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_bulk_assign_zero(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 3), name="v")
                self.v @= 0

        expected = """module Foo (
);

  logic [7:0] v_0;
  logic [7:0] v_1;
  logic [7:0] v_2;

  assign v_0 = 8'd0;
  assign v_1 = 8'd0;
  assign v_2 = 8'd0;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_bulk_assign_literal(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 2), name="v")
                self.v @= Literal(5, 8)

        expected = """module Foo (
);

  logic [7:0] v_0;
  logic [7:0] v_1;

  assign v_0 = 8'd5;
  assign v_1 = 8'd5;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_to_vec_assignment(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 2), name="v")
                self.w = Wire(Vec(Bits(8), 2), name="w")
                self.v[0] @= Literal(1, 8)
                self.w @= self.v

        expected = """module Foo (
);

  logic [7:0] v_0;
  logic [7:0] v_1;
  logic [7:0] w_0;
  logic [7:0] w_1;

  assign v_0 = 8'd1;
  assign w_0 = v_0;
  assign w_1 = v_1;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_depth_mismatch_error(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 2), name="v")
                self.w = Wire(Vec(Bits(8), 3), name="w")
                self.w @= self.v

        with pytest.raises(TypeError, match="depth mismatch"):
            emitVerilog(Foo())


class TestVecPorts:
    def test_vec_input(self):
        class Foo(Module):
            def elaborate(self):
                self.v = IO(Input(Vec(Bits(8), 3)), name="v")
                self.o = IO(Output(Bits(8)), name="o")
                self.o @= self.v[1]

        expected = """module Foo (
  input  logic [7:0] v_0,
  input  logic [7:0] v_1,
  input  logic [7:0] v_2,
  output logic [7:0] o
);

  assign o = v_1;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_output(self):
        class Foo(Module):
            def elaborate(self):
                self.v = IO(Input(Bits(8)), name="v")
                self.o = IO(Output(Vec(Bits(8), 2)), name="o")
                self.o[0] @= self.v
                self.o[1] @= Literal(42, 8)

        expected = """module Foo (
  input  logic [7:0] v,
  output logic [7:0] o_0,
  output logic [7:0] o_1
);

  assign o_0 = v;
  assign o_1 = 8'd42;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_passthrough(self):
        class Foo(Module):
            def elaborate(self):
                self.i = IO(Input(Vec(Bits(8), 2)), name="i")
                self.o = IO(Output(Vec(Bits(8), 2)), name="o")
                self.o @= self.i

        expected = """module Foo (
  input  logic [7:0] i_0,
  input  logic [7:0] i_1,
  output logic [7:0] o_0,
  output logic [7:0] o_1
);

  assign o_0 = i_0;
  assign o_1 = i_1;

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)


class TestVecDynamicIndex:
    def test_dynamic_index_mux_tree(self):
        class Foo(Module):
            def elaborate(self):
                self.idx = IO(Input(Bits(2)), name="idx")
                self.v = IO(Input(Vec(Bits(8), 4)), name="v")
                self.o = IO(Output(Bits(8)), name="o")
                self.o @= self.v[self.idx]

        expected = """module Foo (
  input  logic [1:0] idx,
  input  logic [7:0] v_0,
  input  logic [7:0] v_1,
  input  logic [7:0] v_2,
  input  logic [7:0] v_3,
  output logic [7:0] o
);

  assign o = ((idx == 2'd0) ? v_0 : ((idx == 2'd1) ? v_1 : ((idx == 2'd2) ? v_2 : v_3)));

endmodule"""
        sv = emitVerilog(Foo())
        assert sv == expected
        compile_verilog(sv)


class TestVecErrors:
    def test_invalid_assignment_target(self):
        class Foo(Module):
            def elaborate(self):
                self.v = Wire(Vec(Bits(8), 2), name="v")
                self.o = IO(Output(Bits(8)), name="o")
                self.v @= self.o

        with pytest.raises(TypeError, match="Cannot assign"):
            emitVerilog(Foo())
