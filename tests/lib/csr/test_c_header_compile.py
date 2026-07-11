import shutil
import subprocess

import pytest

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

GCC = shutil.which("gcc")
requires_gcc = pytest.mark.skipif(not GCC, reason="gcc not available")


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


C_DRIVER = """
#include "test_blk.h"
#include <stdint.h>
#include <assert.h>
#include <string.h>

static uint8_t mock_mem[256];

int main(void) {
    void *base = mock_mem;

    /* === 32-bit RMW on ctrl register === */
    /* Initialize ctrl to reset value (0x00000050 = mode=5 at bits 4-6) */
    memset(mock_mem, 0, sizeof(mock_mem));
    mock_mem[0] = 0x50;  /* Little-endian: mode=5 at bits 4-6 */

    /* Read, update enable to 1, write back */
    uint32_t rv = REG_READ(base, TEST_BLK_CTRL_ADDR);
    rv = UPDATE_FIELD(rv, TEST_BLK_CTRL_ENABLE, 1);
    REG_WRITE(base, TEST_BLK_CTRL_ADDR, rv);

    /* Verify enable=1, mode unchanged=5, others=0 */
    rv = REG_READ(base, TEST_BLK_CTRL_ADDR);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_ENABLE) == 1);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_MODE) == 5);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_STATUS) == 0);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_IRQ) == 0);
    assert(rv == 0x00000051);

    /* Update count to 0xAB, verify count=0xAB and enable still=1, mode still=5 */
    rv = UPDATE_FIELD(rv, TEST_BLK_CTRL_COUNT, 0xAB);
    REG_WRITE(base, TEST_BLK_CTRL_ADDR, rv);
    rv = REG_READ(base, TEST_BLK_CTRL_ADDR);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_ENABLE) == 1);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_MODE) == 5);
    assert(GET_FIELD(rv, TEST_BLK_CTRL_COUNT) == 0xAB);

    /* === FIELD8_WRITE on data register === */
    memset(mock_mem, 0, sizeof(mock_mem));

    /* Write byte0=0xF — should set mock_mem[4] to 0x0F, leave others 0 */
    FIELD8_WRITE(base, TEST_BLK_DATA_ADDR, TEST_BLK_DATA_BYTE0, 0xF);
    assert(mock_mem[4] == 0x0F);
    assert(mock_mem[5] == 0x00);
    assert(mock_mem[6] == 0x00);
    assert(mock_mem[7] == 0x00);

    /* Write byte1=0x3F — should set mock_mem[5] to 0x3F, leave byte0 untouched */
    FIELD8_WRITE(base, TEST_BLK_DATA_ADDR, TEST_BLK_DATA_BYTE1, 0x3F);
    assert(mock_mem[4] == 0x0F);
    assert(mock_mem[5] == 0x3F);
    assert(mock_mem[6] == 0x00);
    assert(mock_mem[7] == 0x00);

    /* === FIELD16_WRITE on data register === */
    /* Write hword=0xFFF — should set bytes 2-3 (at addr+2), leave bytes 0-1 untouched */
    FIELD16_WRITE(base, TEST_BLK_DATA_ADDR, TEST_BLK_DATA_HWORD, 0xFFF);
    assert(mock_mem[4] == 0x0F);  /* byte0 untouched */
    assert(mock_mem[5] == 0x3F);  /* byte1 untouched */
    assert(mock_mem[6] == 0xFF);  /* hword low byte (LE) */
    assert(mock_mem[7] == 0x0F);  /* hword high byte (LE) */

    return 0;
}
"""


@requires_gcc
def test_c_macros(tmp_path):
    block = _make_test_block()
    block.to_c_header(tmp_path / "test_blk.h")

    driver_c = tmp_path / "test_driver.c"
    driver_c.write_text(C_DRIVER)

    test_bin = tmp_path / "test_bin"

    result = subprocess.run(
        ["gcc", "-std=c11", "-Wall", "-Werror", "-pedantic", "-I", str(tmp_path), str(driver_c), "-o", str(test_bin)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Compile failed:\n{result.stderr}"

    result = subprocess.run([str(test_bin)], capture_output=True)
    assert result.returncode == 0, f"C assertions failed:\n{result.stderr.decode()}"
