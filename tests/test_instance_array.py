"""Tests for array instance feature (count parameter on instance())."""
import pytest
from plane import *


class TSMCMux(BlackBox):
    """Example vendor cell: 2:1 mux."""

    def elaborate(self):
        self.a = IO(Input(UInt(1)), name="a")
        self.b = IO(Input(UInt(1)), name="b")
        self.s = IO(Input(Bool()), name="s")
        self.y = IO(Output(UInt(1)), name="y")


class TestInstanceArrayBasic:
    """Basic array instance emission."""

    def test_instance_array_basic(self):
        """4-bit signals sliced across four 1-bit instances."""

        class Top(Module):
            def elaborate(self):
                self.sig_a = IO(Input(UInt(4)), name="sig_a")
                self.sig_b = IO(Input(UInt(4)), name="sig_b")
                self.sel = IO(Input(Bool()), name="sel")
                self.out = IO(Output(UInt(4)), name="out")

                mux = instance(TSMCMux(), name="u_mux", count=4)
                mux.a @= self.sig_a
                mux.b @= self.sig_b
                mux.s @= self.sel
                self.out @= mux.y

        sv = emitVerilog(Top())
        expected = (
            "module Top (\n"
            "  input  logic [3:0] sig_a,\n"
            "  input  logic [3:0] sig_b,\n"
            "  input  logic       sel,\n"
            "  output logic [3:0] out\n"
            ");\n\n"
            "  TSMCMux u_mux[3:0] (\n"
            "    .a (sig_a),\n"
            "    .b (sig_b),\n"
            "    .s (sel),\n"
            "    .y (out)\n"
            "  );\n\n"
            "endmodule"
        )
        assert sv == expected

    def test_instance_array_output_fanout_rejected(self):
        """Second load on array output raises ConnectionError."""

        def elaborate_failing():
            class Top(Module):
                def elaborate(self):
                    self.sig_a = IO(Input(UInt(4)), name="sig_a")
                    self.sig_b = IO(Input(UInt(4)), name="sig_b")
                    self.sel = IO(Input(Bool()), name="sel")
                    self.out = IO(Output(UInt(4)), name="out")
                    self.debug = IO(Output(UInt(4)), name="debug")

                    mux = instance(TSMCMux(), name="u_mux", count=4)
                    mux.a @= self.sig_a
                    mux.b @= self.sig_b
                    mux.s @= self.sel
                    self.out @= mux.y
                    self.debug @= mux.y  # should fail

            emitVerilog(Top())

        with pytest.raises(ConnectionError, match="Array instance output"):
            elaborate_failing()

    def test_instance_array_explicit_wire_works(self):
        """User creates explicit wire, fans out from it."""

        class Top(Module):
            def elaborate(self):
                self.sig_a = IO(Input(UInt(4)), name="sig_a")
                self.sig_b = IO(Input(UInt(4)), name="sig_b")
                self.sel = IO(Input(Bool()), name="sel")
                self.out = IO(Output(UInt(4)), name="out")
                self.debug = IO(Output(UInt(4)), name="debug")

                mux = instance(TSMCMux(), name="u_mux", count=4)
                mux.a @= self.sig_a
                mux.b @= self.sig_b
                mux.s @= self.sel

                # Explicit wire for fanout
                self.mux_y = Wire(UInt(4), name="mux_y")
                self.mux_y @= mux.y
                self.out @= self.mux_y
                self.debug @= self.mux_y

        sv = emitVerilog(Top())
        expected = (
            "module Top (\n"
            "  input  logic [3:0] sig_a,\n"
            "  input  logic [3:0] sig_b,\n"
            "  input  logic       sel,\n"
            "  output logic [3:0] out,\n"
            "  output logic [3:0] debug\n"
            ");\n\n"
            "  logic [3:0] mux_y;\n\n"
            "  assign out   = mux_y;\n"
            "  assign debug = mux_y;\n\n"
            "  TSMCMux u_mux[3:0] (\n"
            "    .a (sig_a),\n"
            "    .b (sig_b),\n"
            "    .s (sel),\n"
            "    .y (mux_y)\n"
            "  );\n\n"
            "endmodule"
        )
        assert sv == expected

    def test_instance_array_parameterized(self):
        """count=Parameter emits parameterized range."""

        class Top(Module):
            def elaborate(self):
                self.W = Parameter("W", 4)
                self.sig_a = IO(Input(UInt(4)), name="sig_a")
                self.sig_b = IO(Input(UInt(4)), name="sig_b")
                self.sel = IO(Input(Bool()), name="sel")
                self.out = IO(Output(UInt(4)), name="out")

                mux = instance(TSMCMux(), name="u_mux", count=self.W)
                mux.a @= self.sig_a
                mux.b @= self.sig_b
                mux.s @= self.sel
                self.out @= mux.y

        sv = emitVerilog(Top())
        expected = (
            "module Top #(\n"
            "  parameter int W = 4\n"
            ") (\n"
            "  input  logic [3:0] sig_a,\n"
            "  input  logic [3:0] sig_b,\n"
            "  input  logic       sel,\n"
            "  output logic [3:0] out\n"
            ");\n\n"
            "  TSMCMux u_mux[W-1:0] (\n"
            "    .a (sig_a),\n"
            "    .b (sig_b),\n"
            "    .s (sel),\n"
            "    .y (out)\n"
            "  );\n\n"
            "endmodule"
        )
        assert sv == expected

    def test_instance_array_count_1_no_range(self):
        """count=1 emits normal instance (no range)."""

        class Top(Module):
            def elaborate(self):
                self.sig_a = IO(Input(UInt(1)), name="sig_a")
                self.sig_b = IO(Input(UInt(1)), name="sig_b")
                self.sel = IO(Input(Bool()), name="sel")
                self.out = IO(Output(UInt(1)), name="out")

                mux = instance(TSMCMux(), name="u_mux", count=1)
                mux.a @= self.sig_a
                mux.b @= self.sig_b
                mux.s @= self.sel
                self.out @= mux.y

        sv = emitVerilog(Top())
        expected = (
            "module Top (\n"
            "  input  logic sig_a,\n"
            "  input  logic sig_b,\n"
            "  input  logic sel,\n"
            "  output logic out\n"
            ");\n\n"
            "  TSMCMux u_mux (\n"
            "    .a (sig_a),\n"
            "    .b (sig_b),\n"
            "    .s (sel),\n"
            "    .y (out)\n"
            "  );\n\n"
            "endmodule"
        )
        assert sv == expected

    def test_instance_array_count_zero_rejected(self):
        """count=0 raises ValueError with instance info."""
        with pytest.raises(ValueError, match="count must be >= 1 for instance 'u_mux'"):

            class Top(Module):
                def elaborate(self):
                    instance(TSMCMux(), name="u_mux", count=0)

            emitVerilog(Top())

    def test_instance_array_count_negative_rejected(self):
        """count=-1 raises ValueError with instance info."""
        with pytest.raises(ValueError, match="count must be >= 1 for instance 'u_mux'"):

            class Top(Module):
                def elaborate(self):
                    instance(TSMCMux(), name="u_mux", count=-1)

            emitVerilog(Top())

    def test_instance_array_count_invalid_type_rejected(self):
        """count='4' (string) raises TypeError with instance info."""
        with pytest.raises(TypeError, match="count must be int or Parameter for instance 'u_mux'"):

            class Top(Module):
                def elaborate(self):
                    instance(TSMCMux(), name="u_mux", count="4")

            emitVerilog(Top())
