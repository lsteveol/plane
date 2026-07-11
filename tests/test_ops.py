from tests.conftest import compile_verilog
import warnings

import pytest
from plane import *


class TestArithmeticOps:
    @pytest.mark.parametrize(
        "op,verilog_op",
        [
            (lambda a, b: a + b, "+"),
            (lambda a, b: a - b, "-"),
            (lambda a, b: a * b, "*"),
            (lambda a, b: a << b, "<<"),
            (lambda a, b: a >> b, ">>"),
        ],
    )
    def test_arithmetic(self, op, verilog_op):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= op(self.a, self.b)

        expected = f"""module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  assign out = (a {verilog_op} b);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestLogicOps:
    @pytest.mark.parametrize(
        "op,verilog_op",
        [
            (lambda a, b: a & b, "&"),
            (lambda a, b: a | b, "|"),
            (lambda a, b: a ^ b, "^"),
        ],
    )
    def test_logic(self, op, verilog_op):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= op(self.a, self.b)

        expected = f"""module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  assign out = (a {verilog_op} b);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestComparisonOps:
    @pytest.mark.parametrize(
        "op,verilog_op",
        [
            (lambda a, b: a == b, "=="),
            (lambda a, b: a != b, "!="),
            (lambda a, b: a < b, "<"),
            (lambda a, b: a <= b, "<="),
            (lambda a, b: a > b, ">"),
            (lambda a, b: a >= b, ">="),
        ],
    )
    def test_comparison(self, op, verilog_op):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(1)), name="out")
                self.out @= op(self.a, self.b)

        expected = f"""module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic       out
);

  assign out = (a {verilog_op} b);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestUnaryOp:
    def test_invert(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= ~self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = ~a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestSlice:
    def test_slice(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(4)), name="out")
                self.out @= self.a[7:4]

        expected = """module M (
  input  logic [7:0] a,
  output logic [3:0] out
);

  assign out = a[7:4];

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestIndex:
    def test_index(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(1)), name="out")
                self.out @= self.a[3]

        expected = """module M (
  input  logic [7:0] a,
  output logic       out
);

  assign out = a[3];

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestMux:
    def test_mux(self):
        class M(Module):
            def elaborate(self):
                self.sel = IO(Input(Bits(1)), name="sel")
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= Mux(self.sel, self.a, self.b)

        expected = """module M (
  input  logic       sel,
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  assign out = (sel ? a : b);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestCat:
    def test_cat(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(4)), name="a")
                self.b = IO(Input(Bits(4)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= Cat(self.a, self.b)

        expected = """module M (
  input  logic [3:0] a,
  input  logic [3:0] b,
  output logic [7:0] out
);

  assign out = {a, b};

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestExtend:
    def test_zero_extend(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(4)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= zext(self.a, 8)

        expected = """module M (
  input  logic [3:0] a,
  output logic [7:0] out
);

  assign out = {4'd0, a};

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_sign_extend(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(4)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= sext(self.a, 8)

        expected = """module M (
  input  logic [3:0] a,
  output logic [7:0] out
);

  assign out = {4{a[3]}, a};

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        # skip iverilog: {N{expr}} repeat concatenation not supported


class TestNestedOps:
    def test_nested_expression(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.c = IO(Input(Bits(8)), name="c")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= (self.a + self.b) * self.c

        expected = """module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  input  logic [7:0] c,
  output logic [7:0] out
);

  assign out = ((a + b) * c);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestDivModOps:
    @pytest.mark.parametrize(
        "op,verilog_op",
        [
            (lambda a, b: a / b, "/"),
            (lambda a, b: a // b, "/"),
            (lambda a, b: a % b, "%"),
        ],
    )
    def test_div_mod(self, op, verilog_op):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.b = IO(Input(Bits(8)), name="b")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= op(self.a, self.b)

        expected = f"""module M (
  input  logic [7:0] a,
  input  logic [7:0] b,
  output logic [7:0] out
);

  assign out = (a {verilog_op} b);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestReverseOps:
    def test_rmul(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= 3 * self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = (8'd3 * a);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_radd(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= 1 + self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = (8'd1 + a);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_rsub(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= 255 - self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = (8'd255 - a);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestNegOp:
    def test_neg(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= -self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = -a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestReductionOps:
    @pytest.mark.parametrize(
        "op,verilog_op",
        [
            (AndR, "&"),
            (OrR, "|"),
            (XorR, "^"),
        ],
    )
    def test_reduction(self, op, verilog_op):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(1)), name="out")
                self.out @= op(self.a)

        expected = f"""module M (
  input  logic [7:0] a,
  output logic       out
);

  assign out = {verilog_op}a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestUIntType:
    def test_uint_port(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(UInt(8)), name="a")
                self.out = IO(Output(UInt(8)), name="out")
                self.out @= self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestSIntType:
    def test_sint_port(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(SInt(8)), name="a")
                self.out = IO(Output(SInt(8)), name="out")
                self.out @= self.a

        expected = """module M (
  input  logic signed [7:0] a,
  output logic signed [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_sint_wire(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(SInt(8)), name="a")
                self.w = Wire(SInt(8), name="w")
                self.out = IO(Output(SInt(8)), name="out")
                self.w @= self.a
                self.out @= self.w

        expected = """module M (
  input  logic signed [7:0] a,
  output logic signed [7:0] out
);

  logic signed [7:0] w;

  assign w   = a;
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_sint_reg(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.a = IO(Input(SInt(8)), name="a")
                self.r = Reg(SInt(8), name="r")
                self.out = IO(Output(SInt(8)), name="out")
                self.r @= self.a
                self.out @= self.r

        expected = """module M (
  input  logic              clk,
  input  logic signed [7:0] a,
  output logic signed [7:0] out
);

  always_ff @(posedge clk) begin
    out <= a; // optimized from r
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestCastOps:
    def test_asSInt(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= asSInt(self.a)

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = $signed(a);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_asUInt(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(SInt(8)), name="a")
                self.out = IO(Output(UInt(8)), name="out")
                self.out @= asUInt(self.a)

        expected = """module M (
  input  logic signed [7:0] a,
  output logic        [7:0] out
);

  assign out = $unsigned(a);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestNegativeLiteral:
    def test_negative_literal_unsigned(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a + -1

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = (a + 8'd255);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_negative_literal_wide(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(32)), name="a")
                self.out = IO(Output(Bits(32)), name="out")
                self.out @= self.a + -1

        expected = """module M (
  input  logic [31:0] a,
  output logic [31:0] out
);

  assign out = (a + 32'd4294967295);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBitsBackwardCompat:
    def test_bits_still_works(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestParameter:
    def test_single_parameter(self):
        class M(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 8)
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                self.out @= self.a

        expected = """module M #(
  parameter int WIDTH = 8
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_parameter_wire(self):
        class M(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 8)
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.w = Wire(Bits(self.WIDTH), name="w")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                self.w @= self.a
                self.out @= self.w

        expected = """module M #(
  parameter int WIDTH = 8
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  logic [WIDTH-1:0] w;

  assign w   = a;
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_parameter_override_int(self):
        class Sub(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 8)
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                self.out @= self.a

        class Top(Module):
            def elaborate(self):
                sub = instance(Sub(), params=(("WIDTH", 16),))
                self.a = IO(Input(Bits(16)), name="a")
                self.out = IO(Output(Bits(16)), name="out")
                sub.a @= self.a
                self.out @= sub.out

        expected = """module Top (
  input  logic [15:0] a,
  output logic [15:0] out
);

  Sub #(.WIDTH(16)) sub (
    .a   (a),
    .out (out)
  );

endmodule

module Sub #(
  parameter int WIDTH = 8
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)

    def test_parameter_override_parameter(self):
        class Sub(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 8)
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                self.out @= self.a

        class Top(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 16)
                sub = instance(Sub(), params=(("WIDTH", self.WIDTH),))
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                sub.a @= self.a
                self.out @= sub.out

        expected = """module Top #(
  parameter int WIDTH = 16
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  Sub #(.WIDTH(WIDTH)) sub (
    .a   (a),
    .out (out)
  );

endmodule

module Sub #(
  parameter int WIDTH = 8
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(Top())
        assert sv == expected
        compile_verilog(sv)

    def test_multiple_parameters(self):
        class M(Module):
            def elaborate(self):
                self.WIDTH = Parameter("WIDTH", 8)
                self.DEPTH = Parameter("DEPTH", 4)
                self.a = IO(Input(Bits(self.WIDTH)), name="a")
                self.out = IO(Output(Bits(self.WIDTH)), name="out")
                self.out @= self.a

        expected = """module M #(
  parameter int DEPTH = 4,
  parameter int WIDTH = 8
) (
  input  logic [WIDTH-1:0] a,
  output logic [WIDTH-1:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAttribute:
    def test_wire_attribute(self):
        class DontTouchAttr(Attribute):
            def content(self) -> str:
                return '(* dont_touch = "true" *)'

        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.w = Wire(Bits(8), name="w")
                DontTouchAttr(self.w)
                self.out = IO(Output(Bits(8)), name="out")
                self.w @= self.a
                self.out @= self.w

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  (* dont_touch = "true" *)
  logic [7:0] w;

  assign w   = a;
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_port_attribute(self):
        class XPropAttr(Attribute):
            def content(self) -> str:
                return '(* x_propagate = "true" *)'

        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                XPropAttr(self.a)
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.a

        expected = """module M (
  (* x_propagate = "true" *)
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_comment_attribute(self):
        class CommentAttr(Attribute):
            def content(self) -> str:
                return "// internal wire"

        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.w = Wire(Bits(8), name="w")
                CommentAttr(self.w)
                self.out = IO(Output(Bits(8)), name="out")
                self.w @= self.a
                self.out @= self.w

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  // internal wire
  logic [7:0] w;

  assign w   = a;
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestWidthMismatch:
    def test_width_mismatch_warn(self):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            class M(Module):
                def elaborate(self):
                    self.a = IO(Input(Bits(8)), name="a")
                    self.out = IO(Output(Bits(4)), name="out")
                    self.out @= self.a

            emitVerilog(M())
            assert len(w) == 1
            assert "Width mismatch" in str(w[0].message)

    def test_width_mismatch_error(self):
        import plane.utils as utils
        old_mode = utils.width_mismatch_mode
        try:
            utils.width_mismatch_mode = "error"

            class M(Module):
                def elaborate(self):
                    self.a = IO(Input(Bits(8)), name="a")
                    self.out = IO(Output(Bits(4)), name="out")
                    self.out @= self.a

            with pytest.raises(utils.WidthMismatchError, match="Width mismatch"):
                emitVerilog(M())
        finally:
            utils.width_mismatch_mode = old_mode

    def test_width_mismatch_silent(self):
        import warnings
        import plane.utils as utils

        old_mode = utils.width_mismatch_mode
        try:
            utils.width_mismatch_mode = "silent"

            class M(Module):
                def elaborate(self):
                    self.a = IO(Input(Bits(8)), name="a")
                    self.out = IO(Output(Bits(4)), name="out")
                    self.out @= self.a

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                emitVerilog(M())
                assert len(w) == 0
        finally:
            utils.width_mismatch_mode = old_mode


class TestParameterArithmetic:
    def test_parameter_add(self):
        p = Parameter("WIDTH", 8)
        assert p + 4 == 12
        assert 4 + p == 12

    def test_parameter_sub(self):
        p = Parameter("WIDTH", 8)
        assert p - 2 == 6
        assert 10 - p == 2

    def test_parameter_mul(self):
        p = Parameter("WIDTH", 8)
        assert p * 3 == 24
        assert 3 * p == 24

    def test_parameter_div(self):
        p = Parameter("WIDTH", 8)
        assert p // 2 == 4
        assert 16 // p == 2

    def test_parameter_mod(self):
        p = Parameter("WIDTH", 10)
        assert p % 3 == 1

    def test_parameter_shift(self):
        p = Parameter("WIDTH", 4)
        assert p << 1 == 8
        assert p >> 1 == 2


class TestEnumValidation:
    def test_reg_with_invalid_enum(self):
        class NotAnEnum:
            values = ("A", "B")

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(NotAnEnum, name="state")
                self.r @= Literal(0)

        with pytest.raises(TypeError, match="Expected Bits, Bool, Enum"):
            emitVerilog(M())


class TestAttributeEmission:
    def test_attribute_emitted_before_wire(self):
        class DontTouch(Attribute):
            def content(self):
                return '(* dont_touch = "true" *)'

        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                self.w = Wire(Bits(8), name="w")
                DontTouch(self.w)
                self.w @= self.a
                self.out @= self.w

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  (* dont_touch = "true" *)
  logic [7:0] w;

  assign w   = a;
  assign out = w;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected


class TestUtilsFallbacks:
    def test_width_mismatch_error(self):
        from plane.utils import WidthMismatchError

        assert issubclass(WidthMismatchError, Exception)

    def test_get_width_unknown_type(self):
        from plane.utils import get_width

        class CustomType:
            pass

        w = get_width(CustomType())
        assert w == 1

    def test_get_width_int(self):
        from plane.utils import get_width

        assert get_width(int) == 1
