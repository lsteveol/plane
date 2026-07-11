from tests.conftest import compile_verilog
import pytest
from plane import *


class TestFanout:
    """Test intermediate wire generation for fanout from child output ports."""

    def test_single_fanout_no_wire(self):
        """Single fanout should connect directly, no intermediate wire."""

        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub())
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out1 @= sub.out

        top_expected = """module Top (
  output logic [7:0] out1
);

  Sub sub (
    .out (out1)
  );

endmodule"""

        sub_expected = """module Sub (
  output logic [7:0] out
);

endmodule"""

        sv = emitVerilog(Top())
        assert top_expected in sv
        assert sub_expected in sv
        assert "_fanout" not in sv
        compile_verilog(sv)

    def test_double_fanout_creates_wire(self):
        """Double fanout should create intermediate wire."""

        class Sub(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub())
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out1 @= sub.out
                self.out2 @= sub.out

        top_expected = """module Top (
  output logic [7:0] out1,
  output logic [7:0] out2
);

  logic [7:0] _sub_out;

  assign out1 = _sub_out;
  assign out2 = _sub_out;

  Sub sub (
    .out (_sub_out)
  );

endmodule"""

        sub_expected = """module Sub (
  output logic [7:0] out
);

endmodule"""

        sv = emitVerilog(Top())
        assert top_expected in sv
        assert sub_expected in sv
        compile_verilog(sv)

    def test_multiple_fanout_sources(self):
        """Multiple fanout sources should each get their own wire."""

        class Sub1(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Sub2(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Top(Module):
            def elaborate(self):
                s1 = instance(Sub1())
                s2 = instance(Sub2())
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out3 = IO(Output(Bits(8)), name="out3")
                self.out4 = IO(Output(Bits(8)), name="out4")
                self.out1 @= s1.out
                self.out2 @= s1.out
                self.out3 @= s2.out
                self.out4 @= s2.out

        top_expected = """module Top (
  output logic [7:0] out1,
  output logic [7:0] out2,
  output logic [7:0] out3,
  output logic [7:0] out4
);

  logic [7:0] _sub1_out;
  logic [7:0] _sub2_out;

  assign out1 = _sub1_out;
  assign out2 = _sub1_out;
  assign out3 = _sub2_out;
  assign out4 = _sub2_out;

  Sub1 sub1 (
    .out (_sub1_out)
  );

  Sub2 sub2 (
    .out (_sub2_out)
  );

endmodule"""

        sv = emitVerilog(Top())
        assert top_expected in sv
        compile_verilog(sv)

    def test_fanout_to_child_inputs(self):
        """Fanout to child instance inputs creates intermediate wire."""

        class Source(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        class Consumer(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.in2 = IO(Input(Bits(8)), name="in2")

        class Top(Module):
            def elaborate(self):
                src = instance(Source())
                c1 = instance(Consumer())
                c1.in1 @= src.out
                c1.in2 @= src.out

        top_expected = """module Top (
);

  logic [7:0] _source_out;

  Source source (
    .out (_source_out)
  );

  Consumer consumer (
    .in1 (_source_out),
    .in2 (_source_out)
  );

endmodule"""

        sv = emitVerilog(Top())
        assert top_expected in sv
        compile_verilog(sv)

    def test_current_module_ports_no_extra_wire(self):
        """Current module's own ports should not create intermediate wires."""

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.out2 = IO(Output(Bits(8)), name="out2")
                self.out1 @= self.in1
                self.out2 @= self.in1

        expected = """module Top (
  input  logic [7:0] in1,
  output logic [7:0] out1,
  output logic [7:0] out2
);

  assign out1 = in1;
  assign out2 = in1;

endmodule"""

        sv = emitVerilog(Top())
        assert sv == expected
        assert "_fanout" not in sv
        compile_verilog(sv)


class TestFanoutExistingWire:
    def test_fanout_intermediate_wire_reuse(self):
        class Child(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= 42

        class Parent(Module):
            def elaborate(self):
                self.a = IO(Output(Bits(1)), name="a")
                self.b = IO(Output(Bits(1)), name="b")
                self.ch = instance(Child(), name="ch")
                self.a @= self.ch.out
                self.b @= self.ch.out

        expected = """module Parent (
  output logic a,
  output logic b
);

  logic [7:0] _ch_out;

  assign a = _ch_out;
  assign b = _ch_out;

  Child ch (
    .out (_ch_out)
  );

endmodule

module Child (
  output logic [7:0] out
);

  assign out = 8'd42;

endmodule"""

        sv = emitVerilog(Parent())
        assert sv == expected
        compile_verilog(sv)
