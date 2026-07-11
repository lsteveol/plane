import os

from plane import Bool, Clock, IO, Input, Module, UInt, emitVerilog
from plane.lib.amba.apb import APB3Bundle, apb3_adapter
from plane.lib.csr import (
    RWField,
    Register,
    RegisterBlock,
)
from tests.conftest import simulate_verilog


class APBCSRDut(Module):
    def elaborate(self):
        self.apb = IO(APB3Bundle(addr_width=8, data_width=32), name="apb")
        block = RegisterBlock(
            name="apb_csr_dut",
            registers=[
                Register(
                    name="ctrl",
                    offset=0x00,
                    fields=[
                        RWField(name="enable", width=1, offset=0, reset=0),
                        RWField(name="mode", width=3, offset=4, reset=5),
                    ],
                ),
                Register(
                    name="data",
                    offset=0x04,
                    fields=[
                        RWField(name="lo", width=8, offset=0, reset=0),
                        RWField(name="hi", width=8, offset=8, reset=0),
                    ],
                ),
            ],
            width=32,
            address_space=256,
        )
        self.csr = block.build(adapter_fn=apb3_adapter)
        self.apb @= self.csr.apb


def test_apb_bfm():
    dut_sv = emitVerilog(APBCSRDut())
    tb_file = os.path.join(os.path.dirname(__file__), "apb_tb.sv")
    stdout = simulate_verilog(dut_sv, tb_file)
    assert "PASS" in stdout
