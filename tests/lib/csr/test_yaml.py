import os
import tempfile

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

ALL_FIELD_CLASSES = [
    RWField,
    ROField,
    WOField,
    W1CField,
    W1SField,
    RCField,
    RCWField,
]


def _sample_block():
    return RegisterBlock(
        name="timer",
        registers=[
            Register(
                name="ctrl",
                fields=[
                    RWField(name="enable", width=1, offset=0, reset=1, description="Enable bit"),
                    RWField(name="mode", width=3, offset=1, reset=5, description="Mode"),
                ],
                offset=0,
                description="Control register",
                metadata={"reg_meta": True},
            ),
            Register(
                name="status",
                fields=[
                    ROField(name="done", width=1, offset=0, reset=0, description="Done flag"),
                ],
                offset=4,
                description="Status register",
            ),
        ],
        width=32,
        address_space=256,
        description="Timer block",
        module_name="timer_csr",
        metadata={"vendor": "acme", "version": "1.0"},
    )


# ---------------------------------------------------------------------------
# 1. Field round-trip — all access types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", ALL_FIELD_CLASSES)
def test_roundtrip_field_all_types(cls):
    from plane.lib.csr.yaml_io import field_from_dict, field_to_dict

    f = cls(
        name="f",
        width=8,
        offset=2,
        reset=0xAB,
        description="a field",
        metadata={"k": "v"},
    )
    loaded = field_from_dict(field_to_dict(f))
    assert loaded.name == f.name
    assert loaded.access == f.access
    assert loaded.width == f.width
    assert loaded.offset == f.offset
    assert loaded.reset == f.reset
    assert loaded.description == f.description
    assert loaded.metadata == f.metadata


# ---------------------------------------------------------------------------
# 2. Register round-trip
# ---------------------------------------------------------------------------


def test_roundtrip_register():
    r = Register(
        name="ctrl",
        fields=[RWField(name="enable", width=1, reset=1), ROField(name="flag", width=2, offset=4)],
        offset=0,
        description="Control",
        metadata={"x": 1},
    )
    from plane.lib.csr.yaml_io import register_from_dict, register_to_dict

    d = register_to_dict(r)
    r2 = register_from_dict(d)
    assert r2.name == r.name
    assert r2.offset == r.offset
    assert r2.description == r.description
    assert r2.metadata == r.metadata
    assert len(r2.fields) == len(r.fields)
    for a, b in zip(r.fields, r2.fields):
        assert a.name == b.name
        assert a.access == b.access
        assert a.width == b.width
        assert a.offset == b.offset
        assert a.reset == b.reset


# ---------------------------------------------------------------------------
# 3. Block round-trip
# ---------------------------------------------------------------------------


def test_roundtrip_block():
    b = _sample_block()
    from plane.lib.csr.yaml_io import block_from_dict, block_to_dict

    b2 = block_from_dict(block_to_dict(b))
    assert b2.name == b.name
    assert b2.description == b.description
    assert b2.width == b.width
    assert b2.address_space == b.address_space
    assert b2.module_name == b.module_name
    assert b2.metadata == b.metadata
    assert len(b2.registers) == len(b.registers)


# ---------------------------------------------------------------------------
# 4. Block round-trip via file
# ---------------------------------------------------------------------------


def test_roundtrip_block_file():
    b = _sample_block()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
    try:
        b.to_yaml(path)
        b2 = RegisterBlock.from_yaml(path)
        assert b2.name == b.name
        assert b2.description == b.description
        assert b2.metadata == b.metadata
        assert len(b2.registers) == len(b.registers)
        assert b2.registers[0].name == b.registers[0].name
        assert b2.registers[0].fields[1].reset == b.registers[0].fields[1].reset
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 5. Metadata round-trip
# ---------------------------------------------------------------------------


def test_metadata_roundtrip():
    meta = {"vendor": "acme", "version": "1.0", "custom": {"nested": [1, 2, 3]}}
    b = RegisterBlock(name="b", metadata=meta)
    from plane.lib.csr.yaml_io import block_from_dict, block_to_dict

    b2 = block_from_dict(block_to_dict(b))
    assert b2.metadata == meta
    assert b.metadata == meta


# ---------------------------------------------------------------------------
# 6. Unknown access raises
# ---------------------------------------------------------------------------


def test_unknown_access_raises():
    from plane.lib.csr.yaml_io import field_from_dict

    # Corrupt: field access type is "NOPE" instead of a valid type (RW, RO, etc.)
    with pytest.raises(ValueError, match="Unknown field access type"):
        field_from_dict({"name": "f", "access": "NOPE", "width": 1})


# ---------------------------------------------------------------------------
# 7. Deterministic output
# ---------------------------------------------------------------------------


def test_deterministic_output():
    b = _sample_block()
    assert b.to_yaml() == b.to_yaml()


# ---------------------------------------------------------------------------
# 8. Hex format
# ---------------------------------------------------------------------------


def test_hex_format():
    b = _sample_block()
    text = b.to_yaml()
    # register offset and address_space should be hex
    assert "address_space: 0x100" in text
    assert "offset: 0x0" in text
    assert "reset: 0x1" in text
    assert "reset: 0x5" in text
    # width should NOT be hex
    assert "width: 32" in text
    assert "width: 0x20" not in text


# ---------------------------------------------------------------------------
# 9. Empty block round-trip
# ---------------------------------------------------------------------------


def test_empty_block():
    b = RegisterBlock(name="empty")
    from plane.lib.csr.yaml_io import block_from_dict, block_to_dict

    b2 = block_from_dict(block_to_dict(b))
    assert b2.name == "empty"
    assert b2.registers == []


# ---------------------------------------------------------------------------
# 10. instance_name not serialized
# ---------------------------------------------------------------------------


def test_instance_name_not_serialized():
    b = RegisterBlock(name="t", instance_name="timer0")
    text = b.to_yaml()
    assert "instance_name" not in text
    assert "timer0" not in text


# ---------------------------------------------------------------------------
# 11. Order preserved
# ---------------------------------------------------------------------------


def test_order_preserved():
    b = RegisterBlock(
        name="b",
        registers=[
            Register(name="z", offset=0, fields=[RWField(name="a", width=1), RWField(name="b", width=1, offset=1)]),
            Register(name="a", offset=4, fields=[RWField(name="x", width=1)]),
        ],
    )
    text = b.to_yaml()
    # First register should be 'z', second should be 'a' — use surrounding context
    z_reg_pos = text.index("\n- name: z\n")
    a_reg_pos = text.index("\n- name: a\n")
    assert z_reg_pos < a_reg_pos
    # First field of 'z' should be 'a', second should be 'b' — use indent dashes
    a_field_in_z = text.index("  - name: a\n")
    b_field_in_z = text.index("  - name: b\n")
    assert a_field_in_z < b_field_in_z
    # Field a of register z should come BEFORE register a
    assert a_field_in_z < a_reg_pos


# ---------------------------------------------------------------------------
# 12. Invalid YAML raises on load (validates)
# ---------------------------------------------------------------------------


def test_invalid_yaml_raises_on_load():
    # Corrupt: field reset value (0xFF) exceeds field width (1 bit)
    bad_yaml = """\
block: bad
description: ''
width: 32
address_space: 0x100
module_name: bad
metadata: {}
registers:
- name: r
  offset: 0x0
  description: ''
  metadata: {}
  fields:
  - name: f
    access: RW
    width: 1
    offset: 0
    reset: 0xFF
    description: ''
    metadata: {}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
        f.write(bad_yaml)
    try:
        with pytest.raises(ValueError, match="RegisterBlock validation failed"):
            RegisterBlock.from_yaml(path)
    finally:
        os.unlink(path)


def test_invalid_yaml_overlap_raises_on_load():
    # Corrupt: two fields overlap — field 'a' occupies bits [0,4), field 'b' occupies bits [2,6)
    bad_yaml = """\
block: bad
description: ''
width: 32
address_space: 0x100
module_name: bad
metadata: {}
registers:
- name: r
  offset: 0x0
  description: ''
  metadata: {}
  fields:
  - name: a
    access: RW
    width: 4
    offset: 0
    reset: 0x0
    description: ''
    metadata: {}
  - name: b
    access: RW
    width: 4
    offset: 2
    reset: 0x0
    description: ''
    metadata: {}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
        f.write(bad_yaml)
    try:
        with pytest.raises(ValueError, match="RegisterBlock validation failed"):
            RegisterBlock.from_yaml(path)
    finally:
        os.unlink(path)
