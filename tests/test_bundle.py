from tests.conftest import compile_verilog
import pytest
from plane import *
from plane.nodes import _get_bundle_fields


class MyBundle(Bundle):
    data = Input(Bits(8))
    valid = Output(Bool())


class MyParamBundle(Bundle):
    def __init__(self, width):
        self.data = Input(Bits(width))
        self.valid = Output(Bool())


class NestedBundle(Bundle):
    inner = Input(Bits(4))


class ComplexBundle(Bundle):
    data = Input(Bits(8))
    nested = NestedBundle


class TestBundleBasic:
    def test_bundle_io_expansion(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(MyBundle(), name="s")
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [7:0] s_data,
  output logic       s_valid
);

  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_bundle_field_access(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(MyBundle(), name="s")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.io.data
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [7:0] s_data,
  output logic       s_valid,
  output logic [7:0] out
);

  assign out     = s_data;
  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_bundle_flipped(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(Flipped(MyBundle()), name="s")
                self.io.data @= Literal(0, 8)

        expected = """module M (
  output logic [7:0] s_data,
  input  logic       s_valid
);

  assign s_data = 8'd0;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_bundle_double_flipped(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(Flipped(Flipped(MyBundle())), name="s")
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [7:0] s_data,
  output logic       s_valid
);

  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleNested:
    def test_nested_bundle_expansion(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(ComplexBundle(), name="s")

        expected = """module M (
  input  logic [7:0] s_data,
  input  logic [3:0] s_nested_inner
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_nested_bundle_flipped(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(Flipped(ComplexBundle()), name="s")
                self.io.data @= Literal(0, 8)
                self.io.nested.inner @= Literal(0, 4)

        expected = """module M (
  output logic [7:0] s_data,
  output logic [3:0] s_nested_inner
);

  assign s_data         = 8'd0;
  assign s_nested_inner = 4'd0;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleWire:
    def test_bundle_wire_expansion(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(MyBundle(), name="s")
                self.w = Wire(MyBundle(), name="w")
                self.w.data @= self.io.data
                self.io.valid @= self.w.valid

        expected = """module M (
  input  logic [7:0] s_data,
  output logic       s_valid
);

  logic [7:0] w_data;
  logic w_valid;

  assign w_data  = s_data;
  assign s_valid = w_valid;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleReg:
    def test_bundle_reg_expansion(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(MyBundle(), name="s")
                self.r = Reg(MyBundle(), name="r")
                self.r.data @= self.io.data
                self.r.valid @= Literal(1)
                self.io.valid @= self.r.valid

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] s_data,
  output logic       s_valid
);

  logic [7:0] r_data;

  always_ff @(posedge clk) begin
    r_data  <= s_data;
    s_valid <= 1'd1; // optimized from r_valid
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_bundle_post_init(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(Reset()), name="rst")
                self.io = IO(MyBundle(), name="s")
                self.r = Reg(MyBundle(), name="r")
                self.r.data.init = Literal(42, 8)
                self.r.valid.init = Literal(1)
                self.r.data @= self.io.data
                self.r.valid @= Literal(1)
                self.io.valid @= self.r.valid

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] s_data,
  output logic       s_valid
);

  logic [7:0] r_data;

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      r_data  <= 8'd42;
      s_valid <= 1'd1; // optimized from r_valid
    end else begin
      r_data  <= s_data;
      s_valid <= 1'd1; // optimized from r_valid
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleVec:
    def test_bundle_with_vec_field(self):
        class VecBundle(Bundle):
            vec = Input(Vec(Bits(8), 2))

        class M(Module):
            def elaborate(self):
                self.io = IO(VecBundle(), name="s")

        expected = """module M (
  input  logic [7:0] s_vec_0,
  input  logic [7:0] s_vec_1
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_of_bundles(self):
        class ElemBundle(Bundle):
            data = Input(Bits(8))

        class M(Module):
            def elaborate(self):
                self.io = IO(Vec(ElemBundle, 2), name="s")
                self.out = IO(Output(Bits(8)), name="out")
                self.out @= self.io[0].data

        expected = """module M (
  input  logic [7:0] s_0_data,
  input  logic [7:0] s_1_data,
  output logic [7:0] out
);

  assign out = s_0_data;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_flipped_vec_of_bundles(self):
        class ElemBundle(Bundle):
            data = Input(Bits(8))

        class M(Module):
            def elaborate(self):
                self.io = IO(Flipped(Vec(ElemBundle, 2)), name="s")
                self.io[0].data @= Literal(0, 8)
                self.io[1].data @= Literal(0, 8)

        expected = """module M (
  output logic [7:0] s_0_data,
  output logic [7:0] s_1_data
);

  assign s_0_data = 8'd0;
  assign s_1_data = 8'd0;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleInout:
    def test_inout_bundle_field(self):
        class InoutBundle(Bundle):
            data = Inout(Bits(8))
            en = Input(Bool())

        class M(Module):
            def elaborate(self):
                self.io = IO(InoutBundle(), name="s")

        expected = """module M (
  inout  wire  [7:0] s_data,
  input  logic       s_en
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_flipped_inout_stays_inout(self):
        class MixedBundle(Bundle):
            data = Inout(Bits(8))
            inp = Input(Bool())
            outp = Output(Bool())

        class M(Module):
            def elaborate(self):
                self.io = IO(Flipped(MixedBundle()), name="s")
                self.io.data @= Literal(0, 8)
                self.io.inp @= Literal(1)

        expected = """module M (
  inout  wire  [7:0] s_data,
  output logic       s_inp,
  input  logic       s_outp
);

  assign s_data = 8'd0;
  assign s_inp  = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleParam:
    def test_param_bundle_io(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(MyParamBundle(width=16), name="s")
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [15:0] s_data,
  output logic        s_valid
);

  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_param_bundle_mixed_fields(self):
        class MixedBundle(Bundle):
            fixed = Input(Bits(8))

            def __init__(self, width):
                self.param = Input(Bits(width))

        class M(Module):
            def elaborate(self):
                self.io = IO(MixedBundle(width=4), name="s")

        expected = """module M (
  input  logic [7:0] s_fixed,
  input  logic [3:0] s_param
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_param_bundle_wire(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(MyParamBundle(width=16), name="s")
                self.w = Wire(MyParamBundle(width=16), name="w")
                self.w.data @= self.io.data
                self.io.valid @= self.w.valid

        expected = """module M (
  input  logic [15:0] s_data,
  output logic        s_valid
);

  logic [15:0] w_data;
  logic w_valid;

  assign w_data  = s_data;
  assign s_valid = w_valid;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_param_bundle_reg(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(MyParamBundle(width=16), name="s")
                self.r = Reg(MyParamBundle(width=16), name="r")
                self.r.data @= self.io.data
                self.r.valid @= Literal(1)
                self.io.valid @= self.r.valid

        expected = """module M (
  input  logic        clk,
  input  logic [15:0] s_data,
  output logic        s_valid
);

  logic [15:0] r_data;

  always_ff @(posedge clk) begin
    r_data  <= s_data;
    s_valid <= 1'd1; // optimized from r_valid
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleCloning:
    def test_two_io_instances_same_bundle(self):
        class M(Module):
            def elaborate(self):
                self.io1 = IO(MyBundle(), name="s1")
                self.io2 = IO(MyBundle(), name="s2")
                self.io1.valid @= Literal(1)
                self.io2.valid @= Literal(1)

        expected = """module M (
  input  logic [7:0] s1_data,
  output logic       s1_valid,
  input  logic [7:0] s2_data,
  output logic       s2_valid
);

  assign s1_valid = 1'd1;
  assign s2_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_two_wire_instances_same_bundle(self):
        class InBundle(Bundle):
            data = Input(Bits(8))

        class M(Module):
            def elaborate(self):
                self.io = IO(InBundle(), name="s")
                self.w1 = Wire(InBundle(), name="w1")
                self.w2 = Wire(InBundle(), name="w2")
                self.w1 @= self.io
                self.w2 @= self.io

        expected = """module M (
  input  logic [7:0] s_data
);

  logic [7:0] w1_data;
  logic [7:0] w2_data;

  assign w1_data = s_data;
  assign w2_data = s_data;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_two_reg_instances_same_bundle(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(MyBundle(), name="s")
                self.r1 = Reg(MyBundle(), name="r1")
                self.r2 = Reg(MyBundle(), name="r2")
                self.r1 @= self.io
                self.r2 @= self.r1
                self.io.valid @= self.r2.valid

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] s_data,
  output logic       s_valid
);

  logic [7:0] r1_data;
  logic r1_valid;
  logic [7:0] r2_data;

  always_ff @(posedge clk) begin
    r1_data  <= s_data;
    r1_valid <= s_valid;
    r2_data  <= r1_data;
    s_valid  <= r1_valid; // optimized from r2_valid
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleEdgeCases:
    def test_empty_bundle(self):
        class EmptyBundle(Bundle):
            pass

        class M(Module):
            def elaborate(self):
                self.io = IO(EmptyBundle(), name="s")

        expected = """module M (
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_deeply_nested_bundle(self):
        class L3(Bundle):
            x = Input(Bits(4))

        class L2(Bundle):
            l3 = L3

        class L1(Bundle):
            l2 = L2

        class M(Module):
            def elaborate(self):
                self.io = IO(L1(), name="s")

        expected = """module M (
  input  logic [3:0] s_l2_l3_x
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_vec_of_vec_in_bundle(self):
        class VecVecBundle(Bundle):
            mat = Input(Vec(Vec(Bits(8), 2), 3))

        class M(Module):
            def elaborate(self):
                self.io = IO(VecVecBundle(), name="s")

        expected = """module M (
  input  logic [7:0] s_mat_0_0,
  input  logic [7:0] s_mat_0_1,
  input  logic [7:0] s_mat_1_0,
  input  logic [7:0] s_mat_1_1,
  input  logic [7:0] s_mat_2_0,
  input  logic [7:0] s_mat_2_1
);

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleMatmul:
    def test_bundle_to_bundle_assignment(self):
        class InBundle(Bundle):
            data = Input(Bits(8))
            valid = Input(Bool())

        class M(Module):
            def elaborate(self):
                self.io = IO(InBundle(), name="s")
                self.w = Wire(InBundle(), name="w")
                self.w @= self.io

        expected = """module M (
  input  logic [7:0] s_data,
  input  logic       s_valid
);

  logic [7:0] w_data;
  logic w_valid;

  assign w_data  = s_data;
  assign w_valid = s_valid;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_nested_bundle_matmul(self):
        class M(Module):
            def elaborate(self):
                self.io = IO(ComplexBundle(), name="s")
                self.w = Wire(ComplexBundle(), name="w")
                self.w @= self.io

        expected = """module M (
  input  logic [7:0] s_data,
  input  logic [3:0] s_nested_inner
);

  logic [7:0] w_data;
  logic [3:0] w_nested_inner;

  assign w_data         = s_data;
  assign w_nested_inner = s_nested_inner;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleRegVec:
    def test_reg_bundle_with_vec_field(self):
        class VecBundle(Bundle):
            vec = Input(Vec(Bits(8), 2))

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(VecBundle(), name="s")
                self.r = Reg(VecBundle(), name="r")
                self.r.vec[0] @= self.io.vec[0]
                self.r.vec[1] @= self.io.vec[1]

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] s_vec_0,
  input  logic [7:0] s_vec_1
);

  logic [7:0] r_vec_0;
  logic [7:0] r_vec_1;

  always_ff @(posedge clk) begin
    r_vec_0 <= s_vec_0;
    r_vec_1 <= s_vec_1;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_nested_bundle_with_vec(self):
        class InnerBundle(Bundle):
            vec = Input(Vec(Bits(4), 2))

        class OuterBundle(Bundle):
            data = Input(Bits(8))
            inner = InnerBundle
            result = Output(Bits(8))

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.io = IO(OuterBundle(), name="s")
                self.r = Reg(OuterBundle(), name="r")
                self.r.data @= self.io.data
                self.r.inner.vec[0] @= self.io.inner.vec[0]
                self.r.inner.vec[1] @= self.io.inner.vec[1]
                self.r.result @= self.io.data + 1
                self.io.result @= self.r.result

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] s_data,
  input  logic [3:0] s_inner_vec_0,
  input  logic [3:0] s_inner_vec_1,
  output logic [7:0] s_result
);

  logic [7:0] r_data;
  logic [3:0] r_inner_vec_0;
  logic [3:0] r_inner_vec_1;

  always_ff @(posedge clk) begin
    r_data        <= s_data;
    r_inner_vec_0 <= s_inner_vec_0;
    r_inner_vec_1 <= s_inner_vec_1;
    s_result      <= (s_data + 8'd1); // optimized from r_result
  end

endmodule"""
        assert emitVerilog(M()) == expected


class TestBundleValidation:
    def test_bundle_no_name_error(self):
        with pytest.raises(ValueError, match="must have a name"):

            class M(Module):
                def elaborate(self):
                    self.io = IO(MyBundle())

            emitVerilog(M())

    def test_bundle_invalid_prefix(self):
        with pytest.raises(ValueError, match="must start with letter"):

            class M(Module):
                def elaborate(self):
                    self.io = IO(MyBundle(), name="1bad")

            emitVerilog(M())

    def test_direction_wrapped_bundle_error(self):
        class BadBundle(Bundle):
            nested = Output(NestedBundle())

        with pytest.raises(TypeError, match="Cannot wrap Bundle"):

            class M(Module):
                def elaborate(self):
                    self.io = IO(BadBundle(), name="s")

            emitVerilog(M())


class TestRecordBundle:
    def test_record_bundle_basic(self):
        class RecordBundle(Bundle):
            def __init__(self, signals):
                for name, direction, typ in signals:
                    if isinstance(typ, type) and issubclass(typ, Bundle):
                        setattr(self, name, typ())
                    else:
                        setattr(self, name, direction(typ))

        signals = [
            ("data", Input, Bits(8)),
            ("valid", Output, Bool()),
            ("ready", Input, Bool()),
        ]

        class M(Module):
            def elaborate(self):
                self.io = IO(RecordBundle(signals), name="s")
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [7:0] s_data,
  output logic       s_valid,
  input  logic       s_ready
);

  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


    def test_record_bundle_nested(self):
        class RecordBundle(Bundle):
            def __init__(self, signals):
                for name, direction, typ in signals:
                    if isinstance(typ, type) and issubclass(typ, Bundle):
                        setattr(self, name, typ())
                    else:
                        setattr(self, name, direction(typ))

        class InnerBundle(Bundle):
            addr = Input(Bits(16))
            data = Input(Bits(8))

        signals = [
            ("ctrl", Input, InnerBundle),
            ("valid", Output, Bool()),
        ]

        class M(Module):
            def elaborate(self):
                self.io = IO(RecordBundle(signals), name="s")
                self.io.valid @= Literal(1)

        expected = """module M (
  input  logic [15:0] s_ctrl_addr,
  input  logic [7:0]  s_ctrl_data,
  output logic        s_valid
);

  assign s_valid = 1'd1;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestBundleEdgeCases:
    def test_bundle_proxy_getattr_missing(self):
        from plane.nodes import BundleProxy

        bp = BundleProxy({"a": 1})
        with pytest.raises(AttributeError, match="has no field"):
            bp.b

    def test_bundle_proxy_getattr_private(self):
        from plane.nodes import BundleProxy

        bp = BundleProxy({})
        with pytest.raises(AttributeError):
            bp._private

    def test_bundle_proxy_matmul_wrong_type(self):
        from plane.nodes import BundleProxy

        bp = BundleProxy({"a": 1})
        with pytest.raises(TypeError, match="Cannot assign"):
            bp @= 42

    def test_bundle_instance_non_direction_field(self):
        class MyBundle(Bundle):
            data = Input(Bits(8))
            extra = 42

        fields = _get_bundle_fields(MyBundle())
        names = [f[0] for f in fields]
        assert "data" in names
        assert "extra" not in names

    def test_bundle_class_non_direction_field(self):
        class MyBundle(Bundle):
            data = Input(Bits(8))
            extra = 42

        fields = _get_bundle_fields(MyBundle)
        names = [f[0] for f in fields]
        assert "data" in names
        assert "extra" not in names

    def test_bundle_instance_bundle_field(self):
        class Inner(Bundle):
            a = Input(Bits(8))

        class MyBundle(Bundle):
            inner = Inner()

        fields = _get_bundle_fields(MyBundle())
        names = [f[0] for f in fields]
        assert "inner" in names

    def test_bundle_direction_wrapping_error(self):
        class Inner(Bundle):
            a = Input(Bits(8))

        class MyBundle(Bundle):
            inner = Input(Inner())

        with pytest.raises(TypeError, match="Cannot wrap Bundle"):

            class M(Module):
                def elaborate(self):
                    self.io = IO(MyBundle(), name="s")

            emitVerilog(M())

    def test_bundle_direction_wrapping_error_instance(self):
        class Inner(Bundle):
            a = Input(Bits(8))

        class MyBundle(Bundle):
            pass

        with pytest.raises(TypeError, match="Cannot wrap Bundle"):

            class M(Module):
                def elaborate(self):
                    obj = MyBundle()
                    obj.inner = Input(Inner())
                    self.io = IO(obj, name="s")

            emitVerilog(M())
