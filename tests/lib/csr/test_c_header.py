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


def _make_test_block():
    return RegisterBlock(
        name="test_blk",
        width=32,
        registers=[
            Register(
                name="ctrl",
                offset=0,
                fields=[
                    RWField(name="enable", width=1, offset=0, reset=0),
                    RWField(name="mode", width=3, offset=4, reset=5),
                    ROField(name="status", width=4, offset=8, reset=0),
                    W1CField(name="irq", width=1, offset=12, reset=0),
                    W1SField(name="flag", width=1, offset=16, reset=0),
                    WOField(name="count", width=8, offset=20, reset=0),
                    RCField(name="rcval", width=1, offset=28, reset=0),
                    RCWField(name="rwc", width=2, offset=30, reset=0),
                ],
            ),
            Register(
                name="data",
                offset=4,
                fields=[
                    RWField(name="byte0", width=4, offset=0, reset=0),
                    RWField(name="byte1", width=6, offset=8, reset=0),
                    RWField(name="hword", width=12, offset=16, reset=0),
                ],
            ),
        ],
    )


def _has_define_line(header: str, define_name: str, value: str) -> bool:
    """Check if header contains a line with both define_name and value."""
    for line in header.split('\n'):
        if define_name in line and value in line:
            return True
    return False


def test_block_header():
    block = _make_test_block()
    h = block.to_c_header()
    
    # Check guard
    assert "#ifndef TEST_BLK_H" in h
    assert "#define TEST_BLK_H" in h
    assert "#endif /* TEST_BLK_H */" in h
    
    # Check register address and reset values (name and value on same line)
    assert _has_define_line(h, "TEST_BLK_CTRL_ADDR", "0x0000")
    assert _has_define_line(h, "TEST_BLK_CTRL_RESET", "0x00000050")  # mode=5 at offset 4
    assert _has_define_line(h, "TEST_BLK_DATA_ADDR", "0x0004")
    assert _has_define_line(h, "TEST_BLK_DATA_RESET", "0x00000000")
    
    # Check field defines exist with correct values
    assert _has_define_line(h, "TEST_BLK_CTRL_ENABLE_OFFSET", "0")
    assert _has_define_line(h, "TEST_BLK_CTRL_ENABLE_WIDTH", "1")
    assert _has_define_line(h, "TEST_BLK_CTRL_ENABLE_MASK", "0x1")
    assert _has_define_line(h, "TEST_BLK_CTRL_ENABLE_BYTE_OFFSET", "0")
    
    assert _has_define_line(h, "TEST_BLK_CTRL_MODE_OFFSET", "4")
    assert _has_define_line(h, "TEST_BLK_CTRL_MODE_WIDTH", "3")
    assert _has_define_line(h, "TEST_BLK_CTRL_MODE_MASK", "0x7")
    
    assert _has_define_line(h, "TEST_BLK_DATA_BYTE0_OFFSET", "0")
    assert _has_define_line(h, "TEST_BLK_DATA_BYTE1_OFFSET", "8")
    assert _has_define_line(h, "TEST_BLK_DATA_HWORD_OFFSET", "16")
    assert _has_define_line(h, "TEST_BLK_DATA_HWORD_MASK", "0xFFF")
    
    # Check macros block
    assert "#ifndef PLANE_FIELD_MACROS" in h
    assert "#define REG_READ" in h
    assert "#define REG_WRITE" in h
    assert "#define GET_FIELD" in h
    assert "#define UPDATE_FIELD" in h
    assert "#define FIELD8_WRITE" in h
    assert "#define FIELD16_WRITE" in h


def test_no_block_prefix():
    block = _make_test_block()
    h = block.to_c_header(prefix_block_name=False)
    
    # Check that register/field defines don't have block prefix
    assert "#define TEST_BLK_CTRL_" not in h
    assert "#define TEST_BLK_DATA_" not in h
    
    # Check register defines without prefix
    assert _has_define_line(h, "CTRL_ADDR", "0x0000")
    assert _has_define_line(h, "CTRL_RESET", "0x00000050")
    assert _has_define_line(h, "DATA_ADDR", "0x0004")
    
    # Check field defines without prefix
    assert _has_define_line(h, "CTRL_ENABLE_OFFSET", "0")
    assert _has_define_line(h, "DATA_BYTE0_OFFSET", "0")
    assert _has_define_line(h, "DATA_HWORD_OFFSET", "16")


def test_empty_block():
    block = RegisterBlock(name="empty")
    h = block.to_c_header()
    expected = """#ifndef EMPTY_H
#define EMPTY_H

/*
 * empty
 */

#ifndef PLANE_FIELD_MACROS
#define PLANE_FIELD_MACROS

/* Register access (32-bit) */
#define REG_READ(base, offset)        (*((volatile uint32_t *)((uintptr_t)(base) + (offset))))
#define REG_WRITE(base, offset, val) (*((volatile uint32_t *)((uintptr_t)(base) + (offset))) = (uint32_t)(val))

/* Field access (32-bit RMW) */
#define GET_FIELD(reg, field)          (((uint32_t)(reg) >> field##_OFFSET) & field##_MASK)
#define UPDATE_FIELD(reg, field, val) (((uint32_t)(reg) & ~((uint32_t)field##_MASK << field##_OFFSET)) | (((val) & field##_MASK) << field##_OFFSET))

/* Field write (8-bit direct — no RMW, user must ensure field is sole byte occupant or accept corruption */
#define FIELD8_WRITE(base, offset, field, val) \\
    (*((volatile uint8_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \\
        (uint8_t)((val) & field##_MASK))

/* Field write (16-bit direct — no RMW, user must ensure field is sole halfword occupant or accept corruption */
#define FIELD16_WRITE(base, offset, field, val) \\
    (*((volatile uint16_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \\
        (uint16_t)((val) & field##_MASK))

#endif

#endif /* EMPTY_H */
"""
    assert h == expected


def test_system_header(tmp_path):
    spi = RegisterBlock(
        name="spi",
        registers=[Register(name="ctrl", offset=0, fields=[RWField(name="en", width=1)])],
    )
    i2c = RegisterBlock(
        name="i2c",
        registers=[Register(name="ctrl", offset=0, fields=[RWField(name="en", width=1)])],
    )
    peripherals = RegisterSystem(
        name="peripherals",
        children=[
            SystemChild(kind="block", file="spi.yaml", obj=spi, name="spi0", offset=0, address_space=0x100),
            SystemChild(kind="block", file="i2c.yaml", obj=i2c, name="i2c0", offset=0x100, address_space=0x100),
        ],
    )
    soc = RegisterSystem(
        name="soc",
        children=[
            SystemChild(
                kind="system",
                file="peripherals.yaml",
                obj=peripherals,
                name="peripherals",
                offset=0,
                address_space=0x1000,
            ),
        ],
    )

    soc.to_c_header(tmp_path)

    expected_files = {"spi.h", "i2c.h", "peripherals.h", "soc.h"}
    actual_files = {f.name for f in tmp_path.iterdir() if f.is_file()}
    assert actual_files == expected_files

    soc_h = (tmp_path / "soc.h").read_text()
    assert '#include "peripherals.h"' in soc_h
    assert _has_define_line(soc_h, "SOC_PERIPHERALS_OFFSET", "0x0000")

    peripherals_h = (tmp_path / "peripherals.h").read_text()
    assert '#include "spi.h"' in peripherals_h
    assert '#include "i2c.h"' in peripherals_h
    assert _has_define_line(peripherals_h, "PERIPHERALS_SPI0_OFFSET", "0x0000")
    assert _has_define_line(peripherals_h, "PERIPHERALS_I2C0_OFFSET", "0x0100")
