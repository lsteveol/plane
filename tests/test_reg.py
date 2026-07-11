from tests.conftest import compile_verilog
import pytest
from plane import *


class TestRegBasic:
    def test_reg_no_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.r = Reg(Bits(8), name="r")
                self.r @= self.in1
                self.out1 @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out1
);

  always_ff @(posedge clk) begin
    out1 <= in1; // optimized from r
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_with_init(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=42, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      r <= 8'd42;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_bool(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(Bool(), name="r")
                self.r @= Literal(1)

        expected = """module M (
  input  logic clk
);

  logic r;

  always_ff @(posedge clk) begin
    r <= 1'd1;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_regnext_basic(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.out1 = IO(Output(Bits(8)), name="out1")
                self.r = RegNext(self.in1, name="r")
                self.out1 @= self.r

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  output logic [7:0] out1
);

  always_ff @(posedge clk) begin
    out1 <= in1; // optimized from r
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_regnext_with_init(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = RegNext(self.in1, init=100, name="r")

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      r <= 8'd100;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestRegReset:
    def test_reg_async_low_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_async_high_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncHighReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_sync_low_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(SyncLowReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk) begin
    if (!rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_sync_high_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(SyncHighReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk) begin
    if (rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_async_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk or negedge rst) begin
    if (!rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)

    def test_reg_sync_reset(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(SyncReset()), name="rst")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.r = Reg(Bits(8), init=0, name="r")
                self.r @= self.in1

        expected = """module M (
  input  logic       clk,
  input  logic       rst,
  input  logic [7:0] in1
);

  logic [7:0] r;

  always_ff @(posedge clk) begin
    if (!rst) begin
      r <= 8'd0;
    end else begin
      r <= in1;
    end
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestRegGrouping:
    def test_multiple_regs_same_clk(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(Bits(8)), name="in1")
                self.in2 = IO(Input(Bits(8)), name="in2")
                self.r1 = Reg(Bits(8), name="r1")
                self.r2 = Reg(Bits(8), name="r2")
                self.r1 @= self.in1
                self.r2 @= self.in2

        expected = """module M (
  input  logic       clk,
  input  logic [7:0] in1,
  input  logic [7:0] in2
);

  logic [7:0] r1;
  logic [7:0] r2;

  always_ff @(posedge clk) begin
    r1 <= in1;
    r2 <= in2;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected
        compile_verilog(sv)


class TestRegErrors:
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

    def test_reg_invalid_type_error(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(None, name="r")
                self.r @= Literal(0)

        m = M()
        Builder.push(m)
        with pytest.raises(TypeError, match="has no type"):
            m.elaborate()
        Builder.pop()


class TestResetHelpers:
    def test_is_sync(self):
        from plane.types import Reset, ResetPolarity, ResetType

        r = Reset(ResetType.Sync, ResetPolarity.ActiveLow)
        assert r.is_sync() is True
        assert r.is_async() is False

    def test_is_active_high(self):
        from plane.types import Reset, ResetPolarity, ResetType

        r = Reset(ResetType.Async, ResetPolarity.ActiveHigh)
        assert r.is_active_high() is True
        assert r.is_active_low() is False


class TestRegEdgeCases:
    def test_reg_with_enum_init(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUN = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.r = Reg(MyState, init=MyState.RUN, name="r")
                self.r @= MyState.IDLE

        sv = emitVerilog(M())
        assert "MyState_t::RUN" in sv

    def test_reg_emit_init_value_literal(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.r = Reg(Bits(8), init=42, name="r")
                self.r @= self.r

        sv = emitVerilog(M())
        assert "8'd42" in sv

    def test_reg_emit_init_value_default(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.r = Reg(Bits(8), name="r")
                self.r @= self.r

        sv = emitVerilog(M())
        assert "8'd0" in sv

    def test_reg_int_to_literal(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(Bits(8), name="r")
                self.r @= 5

        sv = emitVerilog(M())
        assert "r <= 8'd5;" in sv


class TestGroupAlwaysFF:
    def test_grouped_always_ff(self):
        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r1 = Reg(Bits(8), name="r1")
                self.r1 @= 1
                self.r2 = Reg(Bits(8), name="r2")
                self.r2 @= 2

        expected = """module M (
  input  logic clk
);

  logic [7:0] r1;
  logic [7:0] r2;

  always_ff @(posedge clk) begin
    r1 <= 8'd1;
    r2 <= 8'd2;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_ungrouped_always_ff(self):
        class M(Module):
            group_always_ff = False

            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r1 = Reg(Bits(8), name="r1")
                self.r1 @= 1
                self.r2 = Reg(Bits(8), name="r2")
                self.r2 @= 2

        expected = """module M (
  input  logic clk
);

  logic [7:0] r1;
  logic [7:0] r2;

  always_ff @(posedge clk) begin
    r1 <= 8'd1;
  end

  always_ff @(posedge clk) begin
    r2 <= 8'd2;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_ungrouped_global_config(self):
        from plane import utils

        old = utils.group_always_ff
        utils.group_always_ff = False
        try:
            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.r1 = Reg(Bits(8), name="r1")
                    self.r1 @= 1
                    self.r2 = Reg(Bits(8), name="r2")
                    self.r2 @= 2

            expected = """module M (
  input  logic clk
);

  logic [7:0] r1;
  logic [7:0] r2;

  always_ff @(posedge clk) begin
    r1 <= 8'd1;
  end

  always_ff @(posedge clk) begin
    r2 <= 8'd2;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
        finally:
            utils.group_always_ff = old

    def test_module_attr_overrides_global(self):
        from plane import utils

        old = utils.group_always_ff
        utils.group_always_ff = False
        try:
            class M(Module):
                group_always_ff = True

                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.r1 = Reg(Bits(8), name="r1")
                    self.r1 @= 1
                    self.r2 = Reg(Bits(8), name="r2")
                    self.r2 @= 2

            expected = """module M (
  input  logic clk
);

  logic [7:0] r1;
  logic [7:0] r2;

  always_ff @(posedge clk) begin
    r1 <= 8'd1;
    r2 <= 8'd2;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
        finally:
            utils.group_always_ff = old
