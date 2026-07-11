from tests.conftest import compile_verilog
import pytest
from plane import *


class TestInstanceNaming:
    def test_default_instance_name(self):
        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub())
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= sub.out

        expected = """module Top (
  output logic [7:0] out
);

  Sub sub (
    .out (out)
  );

endmodule

module Sub (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)

    def test_explicit_instance_name(self):
        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub(), name="mysub")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= sub.out

        expected = """module Top (
  output logic [7:0] out
);

  Sub mysub (
    .out (out)
  );

endmodule

module Sub (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)

    def test_auto_disambiguation(self):
        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                s1 = instance(Sub())
                s2 = instance(Sub())
                s3 = instance(Sub())
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out3 = IO(Output(Bits(8)), name="out3")
                self.out1 @= s1.out
                self.out2 @= s2.out
                self.out3 @= s3.out

        expected = """module Top (
  output logic [7:0] out1,
  output logic [7:0] out2,
  output logic [7:0] out3
);

  Sub sub (
    .out (out1)
  );

  Sub sub_1 (
    .out (out2)
  );

  Sub sub_2 (
    .out (out3)
  );

endmodule

module Sub (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)


class TestNestedInstances:
    def test_three_levels_deep(self):
        class Leaf(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Mid(Module):
            def elaborate(self):
                self.leaf = instance(Leaf())
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.leaf.out

        class Top(Module):
            def elaborate(self):
                self.mid = instance(Mid())
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.mid.out

        expected = """module Top (
  output logic [7:0] out
);

  Mid mid (
    .out (out)
  );

endmodule

module Mid (
  output logic [7:0] out
);

  Leaf leaf (
    .out (out)
  );

endmodule

module Leaf (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)


class TestDeduplication:
    def test_diamond_dependency(self):
        class D(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class B(Module):
            def elaborate(self):
                self.d = instance(D())
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.d.out

        class C(Module):
            def elaborate(self):
                self.d = instance(D())
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.d.out

        class A(Module):
            def elaborate(self):
                self.b = instance(B())
                self.c = instance(C())
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out1 @= self.b.out
                self.out2 @= self.c.out

        expected = """module A (
  output logic [7:0] out1,
  output logic [7:0] out2
);

  B b (
    .out (out1)
  );

  C c (
    .out (out2)
  );

endmodule

module B (
  output logic [7:0] out
);

  D d (
    .out (out)
  );

endmodule

module D (
  output logic [7:0] out
);

endmodule

module C (
  output logic [7:0] out
);

  D d (
    .out (out)
  );

endmodule"""
        sv = emitVerilog(A())
        assert sv == expected
        compile_verilog(sv)


class TestWireCollision:
    def test_fanout_wire_name_collision(self):
        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub())
                self._sub_out = Wire(Bits(8), name="_sub_out")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out1 @= sub.out
                self.out2 @= sub.out

        expected = """module Top (
  output logic [7:0] out1,
  output logic [7:0] out2
);

  logic [7:0] _sub_out;
  logic [7:0] _sub_out_1;

  assign out1 = _sub_out_1;
  assign out2 = _sub_out_1;

  Sub sub (
    .out (_sub_out_1)
  );

endmodule

module Sub (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)


class TestSuggestName:
    def test_suggest_name(self):
        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub().suggest_name("MySub"))
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= sub.out

        expected = """module Top (
  output logic [7:0] out
);

  MySub mysub (
    .out (out)
  );

endmodule

module MySub (
  output logic [7:0] out
);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)


class TestDedupRename:
    def test_same_class_different_logic_not_deduped(self):
        """Same class with different internal logic emits two modules."""
        class GateModule(Module):
            def __init__(self, mode_and=True):
                super().__init__()
                self.mode_and = mode_and

            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.z = IO(Output(Bits(8)), name="z")
                if self.mode_and:
                    self.z @= self.a & self.b
                else:
                    self.z @= self.a | self.b

        class Top(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.and_out = IO(Output(Bits(8)), name="and_out")
                self.or_out = IO(Output(Bits(8)), name="or_out")

                and_inst = instance(GateModule(mode_and=True))
                and_inst.a @= self.a
                and_inst.b @= self.b
                self.and_out @= and_inst.z

                or_inst = instance(GateModule(mode_and=False))
                or_inst.a @= self.a
                or_inst.b @= self.b
                self.or_out @= or_inst.z

        expected = """module Top (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] and_out,
  output logic [7:0] or_out
);

  GateModule gatemodule (
    .a (a),
    .b (b),
    .z (and_out)
  );

  GateModule_1 gatemodule_1 (
    .a (a),
    .b (b),
    .z (or_out)
  );

endmodule

module GateModule (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] z
);

  assign z = (a & b);

endmodule

module GateModule_1 (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] z
);

  assign z = (a | b);

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)
