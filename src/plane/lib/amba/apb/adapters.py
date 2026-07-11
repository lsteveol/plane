from .bundles import APB3Bundle, APB4Bundle


def apb3_adapter(csr, reset_type=None):
    """APB3 adapter - no byte strobes, all bytes enabled.

    Called inside _CSR.elaborate(). Declares APB ports and maps them
    to internal bus_* signals.

    APB Protocol:
        SETUP phase (psel=1, penable=0): Latch address and direction
        ACCESS phase (psel=1, penable=1): Transfer data

    Args:
        csr: The CSR module instance
        reset_type: Reset type (default AsyncLowReset)
    """
    from plane import IO, Bool, UInt, Wire, Reg, Mux, Literal

    addr_width = csr._addr_width
    data_width = csr._data_width

    csr.apb = IO(APB3Bundle(addr_width, data_width, reset_type), name="apb")

    saved_addr = Reg(UInt(addr_width), name="saved_addr")
    saved_write = Reg(Bool(), name="saved_write")

    setup_phase = csr.apb.psel & ~csr.apb.penable
    saved_addr @= Mux(setup_phase, csr.apb.paddr, saved_addr)
    saved_write @= Mux(setup_phase, csr.apb.pwrite, saved_write)

    csr.bus_addr @= saved_addr
    csr.bus_write_en @= saved_write & csr.apb.psel & csr.apb.penable
    csr.bus_read_en @= ~saved_write & csr.apb.psel & csr.apb.penable
    csr.bus_write_data @= csr.apb.pwdata
    csr.bus_byte_en @= Literal((1 << (data_width // 8)) - 1, data_width // 8)
    csr.apb.prdata @= csr.bus_rdata
    csr.apb.pready @= Literal(1)


def apb4_adapter(csr, reset_type=None):
    """APB4 adapter - uses pstrb for byte enables.

    Called inside _CSR.elaborate(). Declares APB ports and maps them
    to internal bus_* signals. pprot is exposed but not used internally.

    Args:
        csr: The CSR module instance
        reset_type: Reset type (default AsyncLowReset)
    """
    from plane import IO, Bool, UInt, Wire, Reg, Mux, Literal

    addr_width = csr._addr_width
    data_width = csr._data_width

    csr.apb = IO(APB4Bundle(addr_width, data_width, reset_type), name="apb")

    saved_addr = Reg(UInt(addr_width), name="saved_addr")
    saved_write = Reg(Bool(), name="saved_write")

    setup_phase = csr.apb.psel & ~csr.apb.penable
    saved_addr @= Mux(setup_phase, csr.apb.paddr, saved_addr)
    saved_write @= Mux(setup_phase, csr.apb.pwrite, saved_write)

    csr.bus_addr @= saved_addr
    csr.bus_write_en @= saved_write & csr.apb.psel & csr.apb.penable
    csr.bus_read_en @= ~saved_write & csr.apb.psel & csr.apb.penable
    csr.bus_write_data @= csr.apb.pwdata
    csr.bus_byte_en @= csr.apb.pstrb
    csr.apb.prdata @= csr.bus_rdata
    csr.apb.pready @= Literal(1)
