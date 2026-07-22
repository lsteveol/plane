import pytest

from plane.lib.csr import (
    RCField,
    RCWField,
    Register,
    RegisterBlock,
    RegisterSystem,
    ROField,
    RWField,
    SystemChild,
    W1CField,
    W1SField,
    WOField,
)


def _make_block():
    return RegisterBlock(
        name="timer",
        registers=[
            Register(
                name="ctrl",
                offset=0,
                fields=[
                    RWField(name="enable", width=1, offset=0, reset=0),
                    RWField(name="mode", width=3, offset=4, reset=5),
                ],
            ),
            Register(
                name="status",
                offset=4,
                fields=[ROField(name="done", width=1, offset=0, reset=0)],
            ),
        ],
    )


def test_single_block():
    block = _make_block()
    sv = block.to_uvm_ral()
    expected = """class timer_ctrl extends uvm_reg;
  rand uvm_reg_field enable;
  rand uvm_reg_field mode;

  function new(string name = "timer_ctrl");
    super.new(name, 32, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    enable = uvm_reg_field::type_id::create("enable");
    enable.configure(this, 1, 0, "RW", 0, 1'h0, 1, 1, 0);
    mode = uvm_reg_field::type_id::create("mode");
    mode.configure(this, 3, 4, "RW", 0, 3'h5, 1, 1, 0);
  endfunction

  `uvm_object_utils(timer_ctrl)
endclass

class timer_status extends uvm_reg;
  rand uvm_reg_field done;

  function new(string name = "timer_status");
    super.new(name, 32, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    done = uvm_reg_field::type_id::create("done");
    done.configure(this, 1, 0, "RO", 1, 1'h0, 1, 1, 0);
  endfunction

  `uvm_object_utils(timer_status)
endclass

class timer extends uvm_reg_block;
  rand timer_ctrl ctrl;
  rand timer_status status;

  function new(string name = "timer");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map("default_map", 0, 4, UVM_LITTLE_ENDIAN, 0);
    ctrl = timer_ctrl::type_id::create("ctrl");
    ctrl.configure(this, null, "");
    ctrl.build();
    default_map.add_reg(ctrl, 'h0);
    status = timer_status::type_id::create("status");
    status.configure(this, null, "");
    status.build();
    default_map.add_reg(status, 'h4);
  endfunction

  `uvm_object_utils(timer)
endclass
"""
    assert sv == expected


def test_system_multi_instance():
    timer_block = _make_block()
    system = RegisterSystem(
        name="soc",
        children=[
            SystemChild(kind="block", file="timer.yaml", obj=timer_block, name="timer0", offset=0x1000, address_space=0x100),
            SystemChild(kind="block", file="timer.yaml", obj=timer_block, name="timer1", offset=0x2000, address_space=0x100),
        ],
    )
    sv = system.to_uvm_ral()
    assert 'timer0 = timer::type_id::create("timer0");' in sv
    assert 'timer1 = timer::type_id::create("timer1");' in sv
    assert "default_map.add_submap(timer0.default_map, 'h1000);" in sv
    assert "default_map.add_submap(timer1.default_map, 'h2000);" in sv
    assert sv.count("class timer extends uvm_reg_block;") == 1


def test_nested_system():
    spi = RegisterBlock(name="spi", registers=[Register(name="ctrl", offset=0, fields=[RWField(name="en", width=1)])])
    i2c = RegisterBlock(name="i2c", registers=[Register(name="ctrl", offset=0, fields=[RWField(name="en", width=1)])])
    peripherals = RegisterSystem(
        name="peripherals",
        children=[
            SystemChild(kind="block", file="spi.yaml", obj=spi, name="spi0", offset=0, address_space=0x100),
            SystemChild(kind="block", file="i2c.yaml", obj=i2c, name="i2c0", offset=0x100, address_space=0x100),
        ],
    )
    soc = RegisterSystem(
        name="soc",
        children=[SystemChild(kind="system", file="peripherals.yaml", obj=peripherals, name="peripherals", offset=0, address_space=0x1000)],
    )
    sv = soc.to_uvm_ral()
    assert "class spi extends uvm_reg_block;" in sv
    assert "class i2c extends uvm_reg_block;" in sv
    assert "class peripherals extends uvm_reg_block;" in sv
    assert "class soc extends uvm_reg_block;" in sv
    assert "rand peripherals peripherals;" in sv


def test_all_access_types():
    block = RegisterBlock(
        name="access_test",
        registers=[
            Register(
                name="regs",
                offset=0,
                fields=[
                    RWField(name="rw_f", width=1, offset=0),
                    ROField(name="ro_f", width=1, offset=1),
                    WOField(name="wo_f", width=1, offset=2),
                    W1CField(name="w1c_f", width=1, offset=3),
                    W1SField(name="w1s_f", width=1, offset=4),
                    RCField(name="rc_f", width=1, offset=5),
                    RCWField(name="rcw_f", width=1, offset=6),
                ],
            ),
        ],
    )
    sv = block.to_uvm_ral()
    assert '"RW", 0' in sv
    assert '"RO", 1' in sv
    assert '"WO", 0' in sv
    assert '"W1C", 1' in sv
    assert '"W1S", 1' in sv
    assert '"RC", 1' in sv
    assert '"WRC", 1' in sv


def test_empty_block():
    block = RegisterBlock(name="empty")
    sv = block.to_uvm_ral()
    expected = """class empty extends uvm_reg_block;


  function new(string name = "empty");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map("default_map", 0, 4, UVM_LITTLE_ENDIAN, 0);

  endfunction

  `uvm_object_utils(empty)
endclass
"""
    assert sv == expected


def test_yaml_roundtrip(tmp_path):
    block = _make_block()
    yaml_path = tmp_path / "timer.yaml"
    block.to_yaml(yaml_path)
    loaded = RegisterBlock.from_yaml(yaml_path)
    assert block.to_uvm_ral() == loaded.to_uvm_ral()


def test_custom_uvm_access():
    """Test that custom fields can override uvm_access to control UVM representation."""
    from plane.lib.csr import Field
    
    class CustomField(Field):
        """Custom field with non-standard access but standard UVM access."""
        
        @property
        def access(self) -> str:
            return "CUSTOM"
        
        @property
        def uvm_access(self) -> str:
            return "RW"
    
    block = RegisterBlock(
        name="custom_test",
        registers=[
            Register(
                name="ctrl",
                offset=0,
                fields=[CustomField(name="custom", width=4, offset=0, reset=0)],
            ),
        ],
    )
    
    sv = block.to_uvm_ral()
    
    # Verify that UVM uses the uvm_access value ("RW"), not the hardware access value ("CUSTOM")
    assert '"RW", 0' in sv
    assert '"CUSTOM"' not in sv
    assert 'custom.configure(this, 4, 0, "RW", 0, 4\'h0, 1, 1, 0);' in sv
