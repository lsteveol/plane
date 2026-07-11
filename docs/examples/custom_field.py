"""
Custom Field Type Example: Write-1-to-Toggle

This example demonstrates how to create a custom field type by subclassing
an existing field (RWField) and overriding only the create_logic() method.

The RWToggleField implements write-1-to-toggle behavior:
- Writing 1 to a bit toggles it
- Writing 0 leaves it unchanged
- Reading returns the current value

By subclassing RWField and keeping access="RW", we maintain compatibility with:
- Connection handling (connection= parameter works)
- UVM RAL generation (treated as RW)
- YAML serialization/deserialization
- HTML documentation generation

Run this file to see the generated Verilog:
    uv run python docs/examples/custom_field.py
"""

from plane import *
from plane import utils
from plane.lib.amba.apb import APB3Bundle, apb3_adapter
from plane.lib.csr import RegisterBlock, Register, RWField, ROField

utils.group_always_ff = False


class RWToggleField(RWField):
    """Write-1-to-toggle field.
    
    Writing 1 to a bit toggles it, writing 0 leaves it unchanged.
    Reading returns the current register value.
    
    Inherits from RWField, so:
    - access property returns "RW" (inherited)
    - create_port() creates a backing register + output port (inherited)
    - create_logic() is overridden to implement toggle behavior
    
    Since access is "RW", this field works with:
    - connection= parameter (output field, drives connection)
    - UVM RAL generation (treated as RW)
    - YAML serialization/deserialization
    - HTML documentation generation
    
    If you need a different UVM access type, override the uvm_access property:
    
        @property
        def uvm_access(self) -> str:
            return "W1T"  # Custom UVM access type (requires UVM extension)
    """
    
    def create_logic(self, write_en, write_data, byte_en_mask, bit_lo, read_en=None):
        # Override to implement toggle: next = reg ^ (wdata & mask) when write_en
        from plane import Mux, UInt, Wire
        
        next_val = Wire(UInt(self.width), name=f"{self.name}_next", comment="Write-1-to-toggle: XOR with masked write data")
        
        # Extract the relevant bits from write_data and byte_en_mask
        wdata_slice = write_data[bit_lo + self.width - 1 : bit_lo]
        byte_en_slice = byte_en_mask[bit_lo + self.width - 1 : bit_lo]
        
        # Toggle logic: XOR current value with masked write data
        toggle_val = self._reg ^ (wdata_slice & byte_en_slice)
        
        next_val @= Mux(write_en, toggle_val, self._reg)
        
        self._reg @= next_val
        return self._reg


class Top(Module):
    def elaborate(self):
        self.clk = IO(Input(Clock()), name="clk")
        self.rst = IO(Input(AsyncLowReset()), name="rst")
        
        # External connections for field ports
        self.toggle_out = Wire(UInt(4), name="toggle_out")
        self.standard_out = Wire(UInt(4), name="standard_out")
        self.status_in = Wire(UInt(8), name="status_in")
        
        # Top-level APB bundle
        self.apb = IO(APB3Bundle(addr_width=8, data_width=32), name="apb")
        
        block = RegisterBlock(
            name="custom_field_demo",
            module_name="CustomFieldCSR",
            instance_name="csr_inst",
            registers=[
                Register(
                    name="ctrl",
                    offset=0,
                    fields=[
                        # Standard RW field: writing sets the value directly
                        RWField(name="standard", width=4, offset=0, reset=0, connection=self.standard_out),
                        # Custom toggle field: writing 1 toggles, writing 0 keeps
                        RWToggleField(name="toggle", width=4, offset=4, reset=0, connection=self.toggle_out),
                        # Read-only field: input from external logic
                        ROField(name="status", width=8, offset=16, connection=self.status_in),
                    ],
                ),
            ],
            width=32,
            address_space=256,
        )
        
        self.csr = block.build(adapter_fn=apb3_adapter)
        
        # Connect CSR's apb to Top's apb
        self.apb @= self.csr.apb
        
        # Drive RO input with a constant for this example
        self.status_in @= Literal(0xAB, 8)


print(emitVerilog(Top()))
