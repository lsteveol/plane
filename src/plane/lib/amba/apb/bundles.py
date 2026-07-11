from plane.types import Bundle, Input, Output, AsyncLowReset, SyncLowReset
from plane.types import UInt, Bool, Clock


def _get_reset_name(reset_type) -> str:
    """Derive reset port name from type."""
    if isinstance(reset_type, (AsyncLowReset, SyncLowReset)):
        return "prstn"
    return "prst"


class APB3Bundle(Bundle):
    """APB3 slave interface bundle.

    Defined from the slave's perspective:
    - Inputs: pclk, preset/prstn, psel, penable, paddr, pwrite, pwdata
    - Outputs: prdata, pready

    Args:
        addr_width: Address bus width (default 32)
        data_width: Data bus width (default 32)
        reset_type: Reset type (default AsyncLowReset)
    """

    def __init__(
        self,
        addr_width: int = 32,
        data_width: int = 32,
        reset_type=None,
    ):
        reset_type = reset_type or AsyncLowReset()
        reset_name = _get_reset_name(reset_type)

        self.pclk = Input(Clock())
        setattr(self, reset_name, Input(reset_type))
        self.paddr = Input(UInt(addr_width))
        self.psel = Input(Bool())
        self.penable = Input(Bool())
        self.pwrite = Input(Bool())
        self.pwdata = Input(UInt(data_width))
        self.prdata = Output(UInt(data_width))
        self.pready = Output(Bool())


class APB4Bundle(APB3Bundle):
    """APB4 slave interface bundle with byte strobes and protection.

    Adds pstrb (byte strobes) and pprot (protection type) to APB3.
    """

    def __init__(
        self,
        addr_width: int = 32,
        data_width: int = 32,
        reset_type=None,
    ):
        super().__init__(addr_width, data_width, reset_type)
        self.pstrb = Input(UInt(data_width // 8))
        self.pprot = Input(UInt(3))
