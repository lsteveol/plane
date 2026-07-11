import pytest

from plane import AsyncLowReset, Bool, Clock, IO, Input, Literal, Module, UInt, Wire, emitVerilog
from plane.lib.amba.apb import APB3Bundle, APB4Bundle, apb3_adapter, apb4_adapter
from plane.lib.csr import (
    RCField,
    RCWField,
    Register,
    RegisterBlock,
    ROField,
    RWField,
    W1CField,
    W1SField,
    WOField,
)


def test_all_field_types_build():
    class Top(Module):
        def elaborate(self):
            self.clk = IO(Input(Clock()), name="clk")
            self.rst = IO(Input(AsyncLowReset()), name="rst")
            self.addr = IO(Input(UInt(8)), name="addr")
            self.we = IO(Input(Bool()), name="we")
            self.re = IO(Input(Bool()), name="re")
            self.wdata = IO(Input(UInt(32)), name="wdata")
            self.be = IO(Input(UInt(4)), name="be")
            
            self.ro_in = Wire(UInt(1), name="ro_in")
            self.rc_in = Wire(UInt(1), name="rc_in")
            self.rcw_in = Wire(UInt(1), name="rcw_in")
            
            block = RegisterBlock(
                name="all_fields",
                registers=[
                    Register(
                        name="mixed",
                        offset=0,
                        fields=[
                            RWField(name="rw_f", width=1, offset=0),
                            ROField(name="ro_f", width=1, offset=1, connection=self.ro_in),
                            WOField(name="wo_f", width=1, offset=2),
                            W1CField(name="w1c_f", width=1, offset=3),
                            W1SField(name="w1s_f", width=1, offset=4),
                            RCField(name="rc_f", width=1, offset=5, connection=self.rc_in),
                            RCWField(name="rcw_f", width=1, offset=6, connection=self.rcw_in),
                        ],
                    ),
                ],
            )
            
            self.csr = block.build()
            self.csr.io_clk @= self.clk
            self.csr.io_rst @= self.rst
            self.csr.io_addr @= self.addr
            self.csr.io_write_en @= self.we
            self.csr.io_read_en @= self.re
            self.csr.io_write_data @= self.wdata
            self.csr.io_byte_en @= self.be
            
            self.ro_in @= Literal(0, 1)
            self.rc_in @= Literal(0, 1)
            self.rcw_in @= Literal(0, 1)

    sv = emitVerilog(Top())
    for name in ["rw_f", "ro_f", "wo_f", "w1c_f", "w1s_f", "rc_f", "rcw_f"]:
        assert name in sv
    assert "mixed_addr_match" in sv
    assert "mixed_we" in sv
    assert "mixed_read_en" in sv


def test_empty_block_build_returns_none():
    block = RegisterBlock(name="empty")
    result = block.build()
    assert result is None


def test_field_access_properties():
    assert RWField(name="x", width=1).access == "RW"
    assert ROField(name="x", width=1).access == "RO"
    assert WOField(name="x", width=1).access == "WO"
    assert W1CField(name="x", width=1).access == "W1C"
    assert W1SField(name="x", width=1).access == "W1S"
    assert RCField(name="x", width=1).access == "RC"
    assert RCWField(name="x", width=1).access == "RCW"


@pytest.mark.parametrize("bundle_cls,adapter_fn", [
    (APB3Bundle, apb3_adapter),
    (APB4Bundle, apb4_adapter),
])
def test_apb_adapter_build(bundle_cls, adapter_fn):
    class Top(Module):
        def elaborate(self):
            self.apb = IO(bundle_cls(addr_width=8, data_width=32), name="apb")
            self.status_done = Wire(Bool(), name="status_done")
            
            block = RegisterBlock(
                name="test_csr",
                registers=[
                    Register(
                        name="ctrl",
                        offset=0,
                        fields=[RWField(name="enable", width=1, offset=0, reset=0)],
                    ),
                    Register(
                        name="status",
                        offset=4,
                        fields=[ROField(name="done", width=1, offset=0, connection=self.status_done)],
                    ),
                ],
                width=32,
                address_space=256,
            )
            
            self.csr = block.build(adapter_fn=adapter_fn)
            self.apb @= self.csr.apb
            self.status_done @= Literal(0, 1)

    sv = emitVerilog(Top())
    
    # Common APB signals
    for signal in ["apb_pclk", "apb_prstn", "apb_paddr", "apb_psel", 
                   "apb_penable", "apb_pwrite", "apb_pwdata", "apb_prdata", "apb_pready"]:
        assert signal in sv
    
    # Adapter-specific signals
    if adapter_fn == apb3_adapter:
        assert "saved_addr" in sv
        assert "saved_write" in sv
    else:  # apb4_adapter
        assert "apb_pstrb" in sv
        assert "apb_pprot" in sv


def test_width_inferred_from_connection():
    class Top(Module):
        def elaborate(self):
            self.out_wire = Wire(UInt(8), name="out_wire")
            self.in_wire = Wire(UInt(16), name="in_wire")
            self.slice_wire = Wire(UInt(32), name="slice_wire")

            self.rw_field = RWField(name="rw_f", offset=0, connection=self.out_wire)
            self.ro_field = ROField(name="ro_f", offset=0, connection=self.in_wire)
            self.slice_field = RWField(name="slice_f", offset=8, connection=self.slice_wire[11:8])

            assert self.rw_field.width == 8
            assert self.ro_field.width == 16
            assert self.slice_field.width == 4

    Top()


def test_width_inferred_from_connection_rc_rcw():
    class Top(Module):
        def elaborate(self):
            self.rc_wire = Wire(UInt(5), name="rc_wire")
            self.rcw_wire = Wire(UInt(3), name="rcw_wire")

            self.rc_field = RCField(name="rc_f", offset=0, connection=self.rc_wire)
            self.rcw_field = RCWField(name="rcw_f", offset=0, connection=self.rcw_wire)

            assert self.rc_field.width == 5
            assert self.rcw_field.width == 3

    Top()


def test_width_required_when_no_connection():
    with pytest.raises(ValueError, match="width is required"):
        RWField(name="x")


def test_width_connection_mismatch():
    class Top(Module):
        def elaborate(self):
            self.wire = Wire(UInt(8), name="wire")
            with pytest.raises(ValueError, match="does not match"):
                RWField(name="x", width=4, offset=0, connection=self.wire)

    Top()


def test_width_inferred_build():
    class Top(Module):
        def elaborate(self):
            self.clk = IO(Input(Clock()), name="clk")
            self.rst = IO(Input(AsyncLowReset()), name="rst")
            self.addr = IO(Input(UInt(8)), name="addr")
            self.we = IO(Input(Bool()), name="we")
            self.re = IO(Input(Bool()), name="re")
            self.wdata = IO(Input(UInt(32)), name="wdata")
            self.be = IO(Input(UInt(4)), name="be")
            self.out = Wire(UInt(8), name="out")
            self.inp = Wire(UInt(16), name="inp")

            block = RegisterBlock(
                name="inferred",
                registers=[
                    Register(
                        name="ctrl",
                        offset=0,
                        fields=[
                            RWField(name="rw_f", offset=0, connection=self.out),
                            ROField(name="ro_f", offset=8, connection=self.inp),
                        ],
                    ),
                ],
                width=32,
            )

            self.csr = block.build()
            self.csr.io_clk @= self.clk
            self.csr.io_rst @= self.rst
            self.csr.io_addr @= self.addr
            self.csr.io_write_en @= self.we
            self.csr.io_read_en @= self.re
            self.csr.io_write_data @= self.wdata
            self.csr.io_byte_en @= self.be
            self.inp @= Literal(0, 16)

    sv = emitVerilog(Top())
    assert "rw_f" in sv
    assert "ro_f" in sv


def test_width_parameter_connection_rejected():
    class Top(Module):
        def elaborate(self):
            from plane.base import Parameter

            self.param = Parameter("WIDTH", 8)
            self.wire = Wire(UInt(self.param), name="wire")

            with pytest.raises(ValueError, match="parameterized width"):
                RWField(name="x", offset=0, connection=self.wire)

    Top()
