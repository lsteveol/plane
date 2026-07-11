import pytest
from plane import *
from tests.conftest import compile_verilog


class TestPortValidation:
    def test_invalid_port_digit_start(self):
        with pytest.raises(ValueError, match="must start with letter or underscore"):

            class M(Module):
                def elaborate(self):
                    self.in1 = IO(Input(Bits(8)), name="1bad")

            emitVerilog(M())

    def test_invalid_port_special_char(self):
        with pytest.raises(ValueError, match="must start with letter or underscore"):

            class M(Module):
                def elaborate(self):
                    self.in1 = IO(Input(Bits(8)), name="bad-name")

            emitVerilog(M())

    def test_port_keyword_rejected(self):
        for keyword in ["module", "wire", "logic", "always", "begin", "end"]:
            with pytest.raises(ValueError, match="cannot use SystemVerilog keyword"):

                class M(Module):
                    def elaborate(self):
                        self.p = IO(Input(Bits(8)), name=keyword)

                emitVerilog(M())

    def test_empty_port_name_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):

            class M(Module):
                def elaborate(self):
                    self.p = IO(Input(Bits(8)), name="")

            emitVerilog(M())


class TestConnectionErrors:
    def test_assign_to_input_port_error(self):
        with pytest.raises(ConnectionError, match="Cannot assign to input port"):
            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.inp = IO(Input(UInt(8)), name="inp")
                    self.r = Reg(UInt(8))
                    self.r @= self.inp
                    self.inp @= self.r  # Wrong direction!

            emitVerilog(M())

    def test_reassign_error(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a
                self.out @= self.b

        m = M()
        Builder.push(m)
        with pytest.raises(ConnectionError, match="Reassigning"):
            m.elaborate()
        Builder.pop()


class TestRegValidation:
    def test_reg_no_next_error(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(Bits(8), name="r")

        m = M()
        Builder.push(m)
        m.elaborate()
        Builder.pop()
        with pytest.raises(RuntimeError, match="no next value assigned"):
            m._validate()

    def test_undriven_output_error(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        with pytest.raises(RuntimeError, match="is undriven"):
            emitVerilog(M())

    def test_reg_no_clock_error(self):
        class M(Module):
            def elaborate(self):
                self.r = Reg(Bits(8), name="r")
                self.r @= Literal(0)

        m = M()
        Builder.push(m)
        with pytest.raises(RuntimeError, match="no clock defined"):
            m.elaborate()
        Builder.pop()


class TestErrorPaths:
    def test_node_name_collision(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                Wire(Bits(8), name="w")
                Wire(Bits(8), name="w")

        with pytest.raises(ValueError, match="already used"):
            emitVerilog(M())

    def test_when_outside_always_comb(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bool()), name="a")
                self.out = IO(Output(Bool()), name="out")
                with When(self.a):
                    self.out @= 1

        with pytest.raises(RuntimeError, match="inside AlwaysComb"):
            emitVerilog(M())

    def test_switch_outside_always_comb(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(Bits(2)), name="sel")
                self.out = IO(Output(Bits(8)), name="out")
                with Switch(self.sel):
                    with Case(0):
                        self.out @= 1

        with pytest.raises(RuntimeError, match="inside AlwaysComb"):
            emitVerilog(M())

    def test_default_outside_switch(self):
        class M(Module):
            def elaborate(self):
                with AlwaysComb():
                    with Default():
                        pass

        with pytest.raises(RuntimeError, match="must be inside Switch"):
            emitVerilog(M())


class TestPortIOEdgeCases:
    def test_port_name_from_typ(self):
        from plane.nodes import InputPort

        clk = Clock()
        p = InputPort(clk)
        assert p.name == "clk"

    def test_port_no_name_no_typ_name(self):
        from plane.nodes import InputPort

        with pytest.raises(ValueError, match="must have a name"):
            InputPort(Bits(8))

    def test_port_no_name_output(self):
        from plane.nodes import OutputPort

        with pytest.raises(ValueError, match="must have a name"):
            OutputPort(Bits(8))

    def test_io_port_no_name(self):
        with pytest.raises(ValueError, match="must have a name"):
            IO(Input(Bits(8)))

    def test_io_bundle_no_name(self):
        class MyBundle(Bundle):
            data = Input(Bits(8))

        with pytest.raises(ValueError, match="must have a name"):
            IO(Input(MyBundle()))


class TestRegInAlwaysComb:
    def test_reg_inside_always_comb_error(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.counter = Reg(Bits(8), clk=self.clk)
                with AlwaysComb():
                    self.counter @= Literal(42, 8)

        with pytest.raises(RuntimeError, match="assigned inside AlwaysComb context"):
            emitVerilog(M())

    def test_reg_inside_when_inside_always_comb_error(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.en = IO(Input(Bool()), name="en")
                self.counter = Reg(Bits(8), clk=self.clk)
                with AlwaysComb():
                    with When(self.en):
                        self.counter @= Literal(42, 8)

        with pytest.raises(RuntimeError, match="assigned inside AlwaysComb context"):
            emitVerilog(M())

    def test_reg_inside_switch_inside_always_comb_error(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.sel = IO(Input(Bits(2)), name="sel")
                self.counter = Reg(Bits(8), clk=self.clk)
                with AlwaysComb():
                    with Switch(self.sel):
                        with Case(0):
                            self.counter @= Literal(1, 8)

        with pytest.raises(RuntimeError, match="assigned inside AlwaysComb context"):
            emitVerilog(M())

    def test_reg_outside_always_comb_ok(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.en = IO(Input(Bool()), name="en")
                self.counter = Reg(Bits(8), clk=self.clk)
                next_val = Wire(Bits(8), name="next_val")
                with AlwaysComb():
                    with When(self.en):
                        next_val @= Literal(42, 8)
                    with Otherwise():
                        next_val @= Literal(0, 8)
                self.counter @= next_val

        sv = emitVerilog(M())
        assert "always_comb" in sv
        assert "always_ff" in sv
        compile_verilog(sv)


class TestWireAutoNaming:
    def test_wire_auto_name_basic(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                w = Wire(Bits(8))
                w @= Literal(42, 8)

        expected = """module M (
  input  logic clk
);

  logic [7:0] auto_wire_0;

  assign auto_wire_0 = 8'd42;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_wire_auto_name_unique(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                w1 = Wire(Bits(8))
                w2 = Wire(Bits(8))
                w3 = Wire(Bits(8))
                w1 @= Literal(1, 8)
                w2 @= Literal(2, 8)
                w3 @= Literal(3, 8)

        expected = """module M (
  input  logic clk
);

  logic [7:0] auto_wire_0;
  logic [7:0] auto_wire_1;
  logic [7:0] auto_wire_2;

  assign auto_wire_0 = 8'd1;
  assign auto_wire_1 = 8'd2;
  assign auto_wire_2 = 8'd3;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_wire_auto_name_no_conflict(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                Wire(Bits(8), name="auto_wire_0")
                w = Wire(Bits(8))
                w @= Literal(42, 8)

        expected = """module M (
  input  logic clk
);

  logic [7:0] auto_wire_0;
  logic [7:0] auto_wire_1;

  assign auto_wire_1 = 8'd42;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)
