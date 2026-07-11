import pytest
from plane import *
from plane.emit import emitVerilog
from tests.conftest import compile_verilog


class TestSliceWrite:
    def test_slice_write_lower_bits(self):
        class M(Module):
            def elaborate(self):
                self.mysig = Wire(Bits(8), name="mysig")
                assign(self.mysig[3:0], Literal(0, 4))

        expected = """module M (
);

  logic [7:0] mysig;

  assign mysig[3:0] = 4'd0;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_slice_write_upper_bits(self):
        class M(Module):
            def elaborate(self):
                self.mysig = Wire(Bits(8), name="mysig")
                self.upper = IO(Input(Bits(4)), name="upper")
                assign(self.mysig[7:4], self.upper)

        expected = """module M (
  input  logic [3:0] upper
);

  logic [7:0] mysig;

  assign mysig[7:4] = upper;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_multiple_non_overlapping_writes(self):
        class M(Module):
            def elaborate(self):
                self.mysig = Wire(Bits(8), name="mysig")
                self.upper = IO(Input(Bits(4)), name="upper")
                self.lower = IO(Input(Bits(4)), name="lower")
                assign(self.mysig[7:4], self.upper)
                assign(self.mysig[3:0], self.lower)

        expected = """module M (
  input  logic [3:0] upper,
  input  logic [3:0] lower
);

  logic [7:0] mysig;

  assign mysig[7:4] = upper;
  assign mysig[3:0] = lower;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_index_write(self):
        class M(Module):
            def elaborate(self):
                self.mysig = Wire(Bits(8), name="mysig")
                assign(self.mysig[0], Literal(1, 1))

        expected = """module M (
);

  logic [7:0] mysig;

  assign mysig[0] = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestAssignRegular:
    def test_assign_on_output_port(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(8)), name="out")
                assign(self.out, self.a)

        expected = """module M (
  input  logic [7:0] a,
  output logic [7:0] out
);

  assign out = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_assign_on_wire(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.w = Wire(Bits(8), name="w")
                assign(self.w, self.a)

        expected = """module M (
  input  logic [7:0] a
);

  logic [7:0] w;

  assign w = a;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestSliceRead:
    def test_slice_read(self):
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

    def test_slice_in_expression(self):
        class M(Module):
            def elaborate(self):
                self.a = IO(Input(Bits(8)), name="a")
                self.out = IO(Output(Bits(4)), name="out")
                self.out @= self.a[7:4] + 1

        expected = """module M (
  input  logic [7:0] a,
  output logic [3:0] out
);

  assign out = (a[7:4] + 4'd1);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestConditionalSlice:
    def test_slice_in_always_comb(self):
        class M(Module):
            def elaborate(self):
                self.mysig = Wire(Bits(8), name="mysig")
                self.sel = IO(Input(Bits(1)), name="sel")
                self.val = IO(Input(Bits(4)), name="val")
                with AlwaysComb():
                    with When(self.sel):
                        assign(self.mysig[3:0], self.val)
                    with Otherwise():
                        assign(self.mysig[3:0], Literal(0, 4))

        expected = """module M (
  input  logic       sel,
  input  logic [3:0] val
);

  logic [7:0] mysig;

  always_comb begin
    if (sel) begin
      mysig[3:0] = val;
    end
    else begin
      mysig[3:0] = 4'd0;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_slice_conditional_all_bits_covered(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                self.sel = IO(Input(Bits(1)), name="sel")
                self.a = IO(Input(Bits(4)), name="a")
                self.b = IO(Input(Bits(4)), name="b")
                with AlwaysComb():
                    assign(self.out[7:4], self.a)
                    with When(self.sel):
                        assign(self.out[3:0], self.b)

        expected = """module M (
  output logic [7:0] out,
  input  logic       sel,
  input  logic [3:0] a,
  input  logic [3:0] b
);

  always_comb begin
    out[7:4] = a;
    if (sel) begin
      out[3:0] = b;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestUndrivenValidation:
    def test_uncovered_bits_error(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                assign(self.out[3:0], Literal(0, 4))

        with pytest.raises(RuntimeError, match="uncovered bits: \\[4, 5, 6, 7\\]"):
            emitVerilog(M())

    def test_all_bits_covered_by_slices(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                assign(self.out[7:4], Literal(0, 4))
                assign(self.out[3:0], Literal(0, 4))

        expected = """module M (
  output logic [7:0] out
);

  assign out[7:4] = 4'd0;
  assign out[3:0] = 4'd0;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_mixed_slice_and_index_all_covered(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                assign(self.out[7:2], Literal(0, 6))
                assign(self.out[1], Literal(0, 1))
                assign(self.out[0], Literal(1, 1))

        expected = """module M (
  output logic [7:0] out
);

  assign out[7:2] = 6'd0;
  assign out[1]   = 1'd0;
  assign out[0]   = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_uncovered_conditional_bits_error(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                self.sel = IO(Input(Bits(1)), name="sel")
                self.a = IO(Input(Bits(4)), name="a")
                with AlwaysComb():
                    assign(self.out[3:0], self.a)

        with pytest.raises(RuntimeError, match="uncovered bits: \\[4, 5, 6, 7\\]"):
            emitVerilog(M())

    def test_full_assignment_still_works(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= Literal(42, 8)

        expected = """module M (
  output logic [7:0] out
);

  assign out = 8'd42;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_undriven_no_partial_error(self):
        class M(Module):
            def elaborate(self):
                self.out = IO(Output(Bits(8)), name="out")

        with pytest.raises(RuntimeError, match="is undriven"):
            emitVerilog(M())
