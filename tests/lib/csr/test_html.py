import pytest
from pathlib import Path

from plane.lib.csr import (
    Register,
    RegisterBlock,
    RegisterSystem,
    ROField,
    RWField,
    SystemChild,
)


def _sample_block():
    return RegisterBlock(
        name="timer",
        registers=[
            Register(
                name="ctrl",
                offset=0,
                fields=[
                    RWField(name="enable", width=1, offset=0, reset=1, description="Enable bit"),
                    RWField(name="mode", width=3, offset=4, reset=5, description="Mode select"),
                ],
                description="Control register",
            ),
            Register(
                name="status",
                offset=4,
                fields=[ROField(name="done", width=1, offset=0, description="Done flag")],
                description="Status register",
            ),
        ],
        description="Timer block",
    )


def test_block_html_generation(tmp_path):
    block = _sample_block()
    block.to_html(tmp_path)

    block_page = tmp_path / "blocks" / "timer.html"
    assert block_page.exists()

    html = block_page.read_text()
    assert "timer" in html
    assert "ctrl" in html
    assert "status" in html
    assert "enable" in html
    assert "mode" in html
    assert "done" in html
    assert "RW" in html
    assert "RO" in html
    assert "Control register" in html
    assert "Status register" in html


def test_system_html_generation(tmp_path):
    block = _sample_block()
    system = RegisterSystem(
        name="soc",
        children=[
            SystemChild(kind="block", file="timer.yaml", obj=block, name="timer0", offset=0x1000, address_space=0x100),
        ],
        description="Test SoC",
    )
    system.to_html(tmp_path)

    index_page = tmp_path / "index.html"
    system_page = tmp_path / "systems" / "soc.html"
    block_page = tmp_path / "blocks" / "timer.html"

    assert index_page.exists()
    assert system_page.exists()
    assert block_page.exists()

    index_html = index_page.read_text()
    assert "soc" in index_html

    system_html = system_page.read_text()
    assert "soc" in system_html
    assert "timer0" in system_html
    assert "0x1000" in system_html

    block_html = block_page.read_text()
    assert "timer" in block_html
    assert "Referenced by" in block_html


def test_nested_system_html(tmp_path):
    spi = RegisterBlock(
        name="spi",
        registers=[Register(name="ctrl", offset=0, fields=[RWField(name="en", width=1)])],
    )
    peripherals = RegisterSystem(
        name="peripherals",
        children=[
            SystemChild(kind="block", file="spi.yaml", obj=spi, name="spi0", offset=0, address_space=0x100),
        ],
    )
    soc = RegisterSystem(
        name="soc",
        children=[
            SystemChild(kind="system", file="peripherals.yaml", obj=peripherals, name="peripherals", offset=0, address_space=0x1000),
        ],
    )
    soc.to_html(tmp_path)

    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "systems" / "soc.html").exists()
    assert (tmp_path / "systems" / "peripherals.html").exists()
    assert (tmp_path / "blocks" / "spi.html").exists()

    search_json = tmp_path / "_static" / "search.json"
    assert search_json.exists()
    search_content = search_json.read_text()
    assert "soc" in search_content
    assert "peripherals" in search_content
    assert "spi" in search_content
