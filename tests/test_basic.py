from tests.conftest import compile_verilog
import pytest
from plane import *


class TestBasicModule:
    """Test basic module creation and elaboration."""

    def test_simple_input_output(self):
        class Simple(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out1 @= self.in1

        expected = """module Simple (
  input  logic [7:0] in1,
  output logic [7:0] out1
);

  assign out1 = in1;

endmodule"""

        sv = emitVerilog(Simple())
        assert sv == expected
        compile_verilog(sv)

    def test_module_with_wire(self):
        class WireModule(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.w = Wire(Bits(8), name="w")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.w @= self.in1
                self.out1 @= self.w

        expected = """module WireModule (
  input  logic [7:0] in1,
  output logic [7:0] out1
);

  logic [7:0] w;

  assign w    = in1;
  assign out1 = w;

endmodule"""

        sv = emitVerilog(WireModule())
        assert sv == expected
        compile_verilog(sv)

    def test_output_only(self):
        class OutOnly(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= Literal(0, 8)

        expected = """module OutOnly (
  output logic [7:0] out
);

  assign out = 8'd0;

endmodule"""

        sv = emitVerilog(OutOnly())
        assert sv == expected
        compile_verilog(sv)

    def test_bit_width_1_no_brackets(self):
        class Bit1(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(1)), name="in1")
                self.out1 = IO(Output(Bits(1)), name="out1")
                self.out1 @= self.in1

        expected = """module Bit1 (
  input  logic in1,
  output logic out1
);

  assign out1 = in1;

endmodule"""

        sv = emitVerilog(Bit1())
        assert sv == expected
        compile_verilog(sv)

    def test_empty_module(self):
        class Empty(Module):
            def elaborate(self):
                pass

        expected = """module Empty (
);

endmodule"""

        sv = emitVerilog(Empty())
        assert sv == expected
        compile_verilog(sv)

    def test_multiple_ports_diff_widths(self):
        class MultiPort(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(1)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.c = IO(Input(Bits(32)), name="c")
                self.o = IO(Output(Bits(8)), name="o")
                self.o @= self.b

        expected = """module MultiPort (
  input  logic        a,
  input  logic [7:0]  b,
  input  logic [31:0] c,
  output logic [7:0]  o
);

  assign o = b;

endmodule"""

        sv = emitVerilog(MultiPort())
        assert sv == expected
        compile_verilog(sv)

    def test_inout_port(self):
        class InoutMod(Module):
            def elaborate(self):
                self.dio = IO(Inout(Bits(8)), name="dio")

        expected = """module InoutMod (
  inout  wire  [7:0] dio
);

endmodule"""

        sv = emitVerilog(InoutMod())
        assert sv == expected
        compile_verilog(sv)

    def test_node_module_tracking(self):
        class Tracking(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.w = Wire(Bits(8), name="w")

        m = Tracking()
        Builder.push(m)
        m.elaborate()
        Builder.pop()

        assert m.in1._module is m
        assert m.out1._module is m
        assert m.w._module is m

    def test_node_outside_context_error(self):
        from plane.base import Node

        with pytest.raises(
            RuntimeError, match="Node created outside of Module context"
        ):
            Node()

    def test_emit_to_file(self, tmp_path):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a

        outfile = tmp_path / "test.sv"
        result = emitVerilog(M(), filename=str(outfile))
        assert outfile.exists()
        assert outfile.read_text() == result
        compile_verilog(filename=str(outfile))


class TestAssignFunction:
    def test_assign_outside_conditional(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                assign(self.out, self.a)

        sv = emitVerilog(M())
        assert "assign out = a;" in sv

    def test_assign_no_module_returns_sink(self):
        result = assign(None, None)
        assert result is None

    def test_assign_inside_conditional(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                with AlwaysComb():
                    with When(self.a[0]):
                        assign(self.out, self.b)

        sv = emitVerilog(M())
        assert "if (a[0])" in sv
        assert "out = b;" in sv


class TestModuleUtilities:
    def test_parameter_add(self):
        p = Parameter("WIDTH", 8)
        assert p + 2 == 10
        assert 2 + p == 10

    def test_get_unique_instance_name_conflict(self):
        class M(Module):
            def elaborate(self):
                pass

        m = M()
        m._instance_names = ["foo"]
        name = m._get_unique_instance_name("foo")
        assert name == "foo_1"

    def test_elaborate_not_implemented(self):
        m = Module()
        with pytest.raises(NotImplementedError):
            m.elaborate()

    def test_pop_context_empty(self):
        class M(Module):
            def elaborate(self):
                pass

        m = M()
        assert m._pop_context() is None

    def test_get_switch_chain_none(self):
        class M(Module):
            def elaborate(self):
                pass

        m = M()
        assert m._get_switch_chain() is None
