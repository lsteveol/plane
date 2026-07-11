import os
import tempfile

import pytest

from plane.lib.csr import (
    Register,
    RegisterBlock,
    ROField,
    RWField,
)


def _block_with_duplicate_field_names():
    return RegisterBlock(
        name="dup",
        registers=[
            Register(
                name="r0",
                offset=0,
                fields=[RWField(name="enable", width=1, offset=0)],
            ),
            Register(
                name="r1",
                offset=4,
                fields=[RWField(name="enable", width=1, offset=0)],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 1. unique_field_names=False (default) — cross-block duplicates allowed
# ---------------------------------------------------------------------------


def test_cross_block_duplicates_allowed_by_default():
    b = _block_with_duplicate_field_names()
    b._validate()


# ---------------------------------------------------------------------------
# 2. unique_field_names=True — cross-block duplicates rejected
# ---------------------------------------------------------------------------


def test_cross_block_duplicates_rejected_when_unique():
    b = _block_with_duplicate_field_names()
    b.unique_field_names = True
    with pytest.raises(ValueError, match="Duplicate field name across block: enable"):
        b._validate()


# ---------------------------------------------------------------------------
# 3. unique_field_names=True — unique names pass
# ---------------------------------------------------------------------------


def test_unique_names_pass_validation():
    b = RegisterBlock(
        name="ok",
        registers=[
            Register(
                name="r0",
                offset=0,
                fields=[RWField(name="enable", width=1, offset=0)],
            ),
            Register(
                name="r1",
                offset=4,
                fields=[RWField(name="mode", width=1, offset=0)],
            ),
        ],
        unique_field_names=True,
    )
    b._validate()


# ---------------------------------------------------------------------------
# 4. bare_field_ports forced False when unique_field_names=False
# ---------------------------------------------------------------------------


def test_bare_field_ports_forced_false():
    b = RegisterBlock(
        name="t",
        bare_field_ports=True,
        unique_field_names=False,
    )
    assert b.bare_field_ports is False


def test_bare_field_ports_kept_when_unique():
    b = RegisterBlock(
        name="t",
        bare_field_ports=True,
        unique_field_names=True,
    )
    assert b.bare_field_ports is True


# ---------------------------------------------------------------------------
# 5. YAML round-trip — flags default to False when missing
# ---------------------------------------------------------------------------


def test_yaml_defaults_to_false():
    yaml_text = """\
block: t
description: ''
width: 32
address_space: 0x100
module_name: t
metadata: {}
registers: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        path = f.name
        f.write(yaml_text)
    try:
        b = RegisterBlock.from_yaml(path)
        assert b.unique_field_names is False
        assert b.bare_field_ports is False
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 6. YAML round-trip — flags preserved
# ---------------------------------------------------------------------------


def test_yaml_flags_roundtrip():
    from plane.lib.csr.yaml_io import block_from_dict, block_to_dict

    b = RegisterBlock(
        name="t",
        unique_field_names=True,
        bare_field_ports=True,
    )
    b2 = block_from_dict(block_to_dict(b))
    assert b2.unique_field_names is True
    assert b2.bare_field_ports is True


# ---------------------------------------------------------------------------
# 7. YAML — flags omitted when False
# ---------------------------------------------------------------------------


def test_yaml_flags_omitted_when_false():
    b = RegisterBlock(name="t")
    text = b.to_yaml()
    assert "unique_field_names" not in text
    assert "bare_field_ports" not in text


# ---------------------------------------------------------------------------
# 8. YAML — flags present when True
# ---------------------------------------------------------------------------


def test_yaml_flags_present_when_true():
    b = RegisterBlock(name="t", unique_field_names=True, bare_field_ports=True)
    text = b.to_yaml()
    assert "unique_field_names: true" in text
    assert "bare_field_ports: true" in text
