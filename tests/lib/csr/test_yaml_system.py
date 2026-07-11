import pathlib
import tempfile

import pytest

from plane.lib.csr import (
    Register,
    RegisterBlock,
    RegisterSystem,
    RWField,
    SystemChild,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_block(name="blk", addr_space=0x100, offset=0):
    return RegisterBlock(
        name=name,
        registers=[Register(name="ctrl", fields=[RWField(name="en", width=1, reset=1)], offset=offset)],
        address_space=addr_space,
        description=f"{name} block",
    )


def _write_tree(root: pathlib.Path, blocks: dict, systems: dict):
    """blocks: {relpath: RegisterBlock}; systems: {relpath: RegisterSystem}"""
    root.mkdir(parents=True, exist_ok=True)
    for rel, blk in blocks.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        blk.to_yaml(str(p))
    for rel, sys_ in systems.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        sys_.to_yaml(str(p))
    return root


# ---------------------------------------------------------------------------
# 1. Round-trip (in-memory)
# ---------------------------------------------------------------------------


def test_system_roundtrip(tmp_path):
    from plane.lib.csr.yaml_io import system_from_dict, system_to_dict

    b1 = _make_block("tx")
    b2 = _make_block("rx")
    (tmp_path / "tx.yaml").write_text(b1.to_yaml())
    (tmp_path / "rx.yaml").write_text(b2.to_yaml())
    sys_ = RegisterSystem(
        name="phy",
        children=[
            b1.to_system_child(file="tx.yaml", name="tx", offset=0x0, address_space=0x100),
            b2.to_system_child(file="rx.yaml", name="rx", offset=0x100, address_space=0x100),
        ],
        description="PHY subsystem",
        metadata={"vendor": "acme"},
    )
    d = system_to_dict(sys_)
    sys2 = system_from_dict(
        d,
        base_dir=tmp_path,
        _ancestors=set(),
    )
    sys2._validate()
    assert sys2.name == "phy"
    assert sys2.description == "PHY subsystem"
    assert sys2.metadata == {"vendor": "acme"}
    assert len(sys2.children) == 2
    assert sys2.children[0].name == "tx"
    assert sys2.children[1].name == "rx"
    assert sys2.children[0].offset == 0x0
    assert sys2.children[1].offset == 0x100


# ---------------------------------------------------------------------------
# 2. Round-trip via files (with nested system child)
# ---------------------------------------------------------------------------


def test_system_file_roundtrip():
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        # leaf blocks — create parent dirs first
        (tmp / "blocks").mkdir(parents=True)
        (tmp / "subsystems/clock/blocks").mkdir(parents=True)
        b_tx = _make_block("tx")
        (tmp / "blocks/tx.yaml").write_text(b_tx.to_yaml())
        b_rx = _make_block("rx")
        (tmp / "blocks/rx.yaml").write_text(b_rx.to_yaml())
        b_clk = _make_block("clk")
        (tmp / "subsystems/clock/blocks/clk.yaml").write_text(b_clk.to_yaml())
        b_rst = _make_block("rst")
        (tmp / "subsystems/clock/blocks/rst.yaml").write_text(b_rst.to_yaml())

        # nested system
        clk_sys = RegisterSystem(
            name="clk_sys",
            children=[
                b_clk.to_system_child(
                    file="subsystems/clock/blocks/clk.yaml",
                    name="clk0",
                    offset=0x0,
                    address_space=0x100,
                    description="Clock divider",
                ),
                b_rst.to_system_child(
                    file="subsystems/clock/blocks/rst.yaml",
                    name="rst0",
                    offset=0x100,
                    address_space=0x100,
                    description="Reset controller",
                ),
            ],
            description="Clock subsystem",
            metadata={"author": "team"},
        )
        (tmp / "subsystems/clock").mkdir(parents=True, exist_ok=True)
        (tmp / "subsystems/clock/clk.yaml").write_text(clk_sys.to_yaml())

        # top system
        top = RegisterSystem(
            name="phy",
            children=[
                b_tx.to_system_child(
                    file="blocks/tx.yaml",
                    name="tx",
                    offset=0x0,
                    address_space=0x100,
                    description="Transmitter",
                ),
                b_rx.to_system_child(
                    file="blocks/rx.yaml",
                    name="rx",
                    offset=0x100,
                    address_space=0x100,
                    description="Receiver",
                ),
                clk_sys.to_system_child(
                    file="subsystems/clock/clk.yaml",
                    name="clk",
                    offset=0x200,
                    address_space=0x200,
                    description="Clock subsystem",
                ),
            ],
            description="PHY subsystem",
            metadata={"vendor": "acme"},
        )
        p_sys = tmp / "phy.yaml"
        top.to_yaml(str(p_sys))

        loaded = RegisterSystem.from_yaml(str(p_sys))
        assert loaded.name == "phy"
        assert len(loaded.children) == 3
        assert loaded.children[0].name == "tx"
        assert loaded.children[2].name == "clk"
        assert loaded.children[2].kind == "system"
        # nested system children should be available
        nested = loaded.children[2].obj
        assert nested.name == "clk_sys"
        assert len(nested.children) == 2
        assert nested.children[0].name == "clk0"
        assert nested.children[1].name == "rst0"
    finally:
        import shutil

        shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# 3. Overlap detected
# ---------------------------------------------------------------------------


def test_system_overlap_detected():
    b1 = _make_block("tx")
    b2 = _make_block("rx")
    # Corrupt: tx occupies [0x0, 0x100) and rx occupies [0x80, 0x180) — they overlap
    sys_ = RegisterSystem(
        name="bad",
        children=[
            b1.to_system_child(file="a.yaml", name="tx", offset=0x0, address_space=0x100),
            b2.to_system_child(file="b.yaml", name="rx", offset=0x80, address_space=0x100),
        ],
    )
    with pytest.raises(ValueError, match="RegisterSystem validation failed"):
        sys_._validate()


# ---------------------------------------------------------------------------
# 4. Allocated < inherent
# ---------------------------------------------------------------------------


def test_system_child_too_small():
    # Block inherent size = address_space = 256 (0x100)
    b1 = RegisterBlock(name="blk", address_space=256, registers=[])
    # Corrupt: allocated address_space (0x80) is smaller than block's inherent size (0x100)
    sys_ = RegisterSystem(
        name="bad",
        children=[
            b1.to_system_child(file="blk.yaml", name="b", offset=0x0, address_space=0x80),
        ],
    )
    with pytest.raises(ValueError, match="allocated 0x80 < inherent 0x100"):
        sys_._validate()


# ---------------------------------------------------------------------------
# 5. Address auto-computed
# ---------------------------------------------------------------------------


def test_system_addr_auto_computed():
    b1 = _make_block("a", addr_space=0x100)
    b2 = _make_block("b", addr_space=0x80)
    sys_ = RegisterSystem(
        name="s",
        children=[
            b1.to_system_child(file="a.yaml", name="a", offset=0x0, address_space=0x100),
            b2.to_system_child(file="b.yaml", name="b", offset=0x200, address_space=0x80),
        ],
    )
    # 0x200 + 0x80 = 0x280
    assert sys_.address_space == 0x280
    sys_._validate()


# ---------------------------------------------------------------------------
# 6. Reserved space (allocated > inherent)
# ---------------------------------------------------------------------------


def test_system_addr_reserved():
    b1 = RegisterBlock(name="blk", address_space=0x100, registers=[])
    sys_ = RegisterSystem(
        name="s",
        children=[
            b1.to_system_child(file="blk.yaml", name="b", offset=0x0, address_space=0x200),
        ],
    )
    # 0x200 > inherent 0x100 — OK (reserved space)
    assert sys_.address_space == 0x200
    sys_._validate()


# ---------------------------------------------------------------------------
# 7. Cycle detected
# ---------------------------------------------------------------------------


def test_system_cycle_detected(tmp_path):
    # Corrupt: self-reference — loop.yaml references itself as a child
    sys_yaml = """\
system: loop
description: ''
metadata: {}
children:
- kind: system
  file: loop.yaml
  name: self
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    p = tmp_path / "loop.yaml"
    p.write_text(sys_yaml)
    with pytest.raises(ValueError, match="Cycle detected"):
        RegisterSystem.from_yaml(str(p))


def test_system_cycle_detected_indirect(tmp_path):
    # Corrupt: indirect cycle — a.yaml references b.yaml, which references a.yaml
    a_yaml = """\
system: a
description: ''
metadata: {}
children:
- kind: system
  file: b.yaml
  name: bb
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    b_yaml = """\
system: b
description: ''
metadata: {}
children:
- kind: system
  file: a.yaml
  name: aa
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    (tmp_path / "a.yaml").write_text(a_yaml)
    (tmp_path / "b.yaml").write_text(b_yaml)
    with pytest.raises(ValueError, match="Cycle detected"):
        RegisterSystem.from_yaml(str(tmp_path / "a.yaml"))


# ---------------------------------------------------------------------------
# 8. Multiple instances of same YAML
# ---------------------------------------------------------------------------


def test_system_multiple_instances_same_yaml(tmp_path):
    blk_yaml = """\
block: blk
description: ''
width: 32
address_space: 0x100
module_name: blk
metadata: {}
registers: []
"""
    (tmp_path / "blk.yaml").write_text(blk_yaml)
    sys_yaml = """\
system: s
description: ''
metadata: {}
children:
- kind: block
  file: blk.yaml
  name: i0
  offset: 0x0
  address_space: 0x100
  description: ''
- kind: block
  file: blk.yaml
  name: i1
  offset: 0x100
  address_space: 0x100
  description: ''
"""
    p = tmp_path / "s.yaml"
    p.write_text(sys_yaml)
    loaded = RegisterSystem.from_yaml(str(p))
    assert len(loaded.children) == 2
    assert loaded.children[0].name == "i0"
    assert loaded.children[1].name == "i1"
    assert loaded.children[0].name != loaded.children[1].name


# ---------------------------------------------------------------------------
# 9. base_dir override
# ---------------------------------------------------------------------------


def test_system_base_dir_override(tmp_path):
    b = _make_block("blk")
    (tmp_path / "real_blk.yaml").write_text(b.to_yaml())

    # system references "blk.yaml" — which exists at tmp_path, not at sys path
    sys_yaml = """\
system: s
description: ''
metadata: {}
children:
- kind: block
  file: blk.yaml
  name: bb
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    # rename the block file so it's not co-located with sys yaml
    # ensure the real path is different from default (sys_yaml.parent)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    p_sys = other_dir / "s.yaml"
    p_sys.write_text(sys_yaml)

    # default base_dir = p_sys.parent = other_dir — file not found there
    # model: same filename "blk.yaml" exists at tmp_path, not other_dir
    # but our block is at tmp_path/blk.yaml; need to put a copy in other_dir for default
    (other_dir / "blk.yaml").write_text(b.to_yaml())

    loaded = RegisterSystem.from_yaml(str(p_sys))
    assert loaded.children[0].name == "bb"

    # Now test override: put another block somewhere else
    third_dir = tmp_path / "third"
    third_dir.mkdir()
    b2 = _make_block("blk2")
    (third_dir / "blk.yaml").write_text(b2.to_yaml())

    loaded2 = RegisterSystem.from_yaml(str(p_sys), base_dir=str(third_dir))
    assert loaded2.children[0].obj.name == "blk2"


# ---------------------------------------------------------------------------
# 10. validate_children default True
# ---------------------------------------------------------------------------


def test_system_validate_children_default_true(tmp_path):
    # Write a system whose nested block is invalid (will be loaded, but we
    # monkey-patch the loaded block later). Easier: write system referencing
    # a block that's fine, then corrupt the block for re-validation.
    b = _make_block("blk")
    (tmp_path / "blk.yaml").write_text(b.to_yaml())
    sys_yaml = """\
system: s
description: ''
metadata: {}
children:
- kind: block
  file: blk.yaml
  name: bb
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    p = tmp_path / "s.yaml"
    p.write_text(sys_yaml)

    # First load works
    loaded = RegisterSystem.from_yaml(str(p))
    assert loaded.children[0].obj.name == "blk"

    # Corrupt: field reset value (0xFF) exceeds field width (4 bits)
    bad = """\
block: blk
description: ''
width: 32
address_space: 0x100
module_name: blk
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
    reset: 0xFF
    description: ''
    metadata: {}
"""
    (tmp_path / "blk.yaml").write_text(bad)
    # validate_children=True (default) re-validates the block, catching the corruption
    with pytest.raises(ValueError, match="RegisterBlock validation failed"):
        RegisterSystem.from_yaml(str(p))


# ---------------------------------------------------------------------------
# 11. validate_children=False skips descendant re-validation
# ---------------------------------------------------------------------------


def test_system_validate_children_false(tmp_path):
    b = _make_block("blk")
    (tmp_path / "blk.yaml").write_text(b.to_yaml())
    sys_yaml = """\
system: s
description: ''
metadata: {}
children:
- kind: block
  file: blk.yaml
  name: bb
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    p = tmp_path / "s.yaml"
    p.write_text(sys_yaml)

    # First load succeeds and validates block (block self-validation at load)
    loaded = RegisterSystem.from_yaml(str(p), validate_children=False)
    assert loaded.children[0].obj.name == "blk"

    # Corrupt block — reload with validate_children=False should still
    # fail because block self-validates at its own from_yaml call.
    # So instead test: load valid block first (cached), then reload system —
    # the block gets re-loaded from disk each time, so corruption catches it
    # at block-load, not at system-revalidate.
    # To genuinely test validate_children=False, we need a *nested system*
    # whose own _validate only runs at top level.
    pass  # see test_system_validate_children_false_nested


def test_system_validate_children_false_nested(tmp_path):
    # Corrupt: nested system has two children with overlapping address ranges
    nested_yaml = """\
system: nested
description: ''
metadata: {}
children:
- kind: block
  file: blk.yaml
  name: b0
  offset: 0x0
  address_space: 0x100
  description: ''
- kind: block
  file: blk.yaml
  name: b1
  offset: 0x10
  address_space: 0x100
  description: ''
"""
    b = _make_block("blk")
    (tmp_path / "blk.yaml").write_text(b.to_yaml())
    (tmp_path / "nested.yaml").write_text(nested_yaml)

    top_yaml = """\
system: top
description: ''
metadata: {}
children:
- kind: system
  file: nested.yaml
  name: nn
  offset: 0x0
  address_space: 0x200
  description: ''
"""
    p = tmp_path / "top.yaml"
    p.write_text(top_yaml)

    # Default (validate_children=True) should fail because nested has overlap
    with pytest.raises(ValueError, match="RegisterSystem validation failed"):
        RegisterSystem.from_yaml(str(p))

    # validate_children=False: top system itself is fine (one child),
    # nested self-validation is skipped, should succeed
    loaded = RegisterSystem.from_yaml(str(p), validate_children=False)
    assert loaded.name == "top"
    assert loaded.children[0].obj.name == "nested"


# ---------------------------------------------------------------------------
# 12. No build() method
# ---------------------------------------------------------------------------


def test_system_no_build():
    sys_ = RegisterSystem(name="s")
    assert not hasattr(sys_, "build")


# ---------------------------------------------------------------------------
# 13. Metadata round-trip
# ---------------------------------------------------------------------------


def test_system_metadata_roundtrip():
    sys_ = RegisterSystem(name="s", metadata={"k": "v", "n": {"nested": [1, 2]}})
    text = sys_.to_yaml()
    loaded_text = yaml_safe_load(text)
    from plane.lib.csr.yaml_io import system_from_dict

    loaded = system_from_dict(loaded_text, base_dir=".", _ancestors=set())
    loaded._validate()
    assert loaded.metadata == {"k": "v", "n": {"nested": [1, 2]}}


def yaml_safe_load(text):
    import yaml

    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# 14. Child description round-trip
# ---------------------------------------------------------------------------


def test_system_child_description():
    b = _make_block("blk")
    sys_ = RegisterSystem(
        name="s",
        children=[
            b.to_system_child(file="blk.yaml", name="bb", offset=0x0,
                              address_space=0x100, description="an instance"),
        ],
    )
    text = sys_.to_yaml()
    assert "description: an instance" in text


# ---------------------------------------------------------------------------
# 15. Unknown kind raises
# ---------------------------------------------------------------------------


def test_system_unknown_kind_raises(tmp_path):
    # Corrupt: child kind is "NOPE" instead of "block" or "system"
    sys_yaml = """\
system: s
description: ''
metadata: {}
children:
- kind: NOPE
  file: x.yaml
  name: x
  offset: 0x0
  address_space: 0x100
  description: ''
"""
    p = tmp_path / "s.yaml"
    p.write_text(sys_yaml)
    with pytest.raises(ValueError, match="Unknown child kind"):
        RegisterSystem.from_yaml(str(p))


# ---------------------------------------------------------------------------
# 16. Empty system
# ---------------------------------------------------------------------------


def test_system_empty():
    sys_ = RegisterSystem(name="empty")
    assert sys_.address_space == 0
    sys_._validate()
    text = sys_.to_yaml()
    assert "children: []" in text


# ---------------------------------------------------------------------------
# 17. Duplicate child names raise
# ---------------------------------------------------------------------------


def test_system_unique_child_names():
    b1 = _make_block("a")
    b2 = _make_block("b")
    # Corrupt: both children have the same name "dup"
    sys_ = RegisterSystem(
        name="s",
        children=[
            b1.to_system_child(file="a.yaml", name="dup", offset=0x0, address_space=0x100),
            b2.to_system_child(file="b.yaml", name="dup", offset=0x100, address_space=0x100),
        ],
    )
    with pytest.raises(ValueError, match="Duplicate child name: dup"):
        sys_._validate()


# ---------------------------------------------------------------------------
# 18. to_system_child helpers
# ---------------------------------------------------------------------------


def test_block_to_system_child():
    b = _make_block("blk")
    c = b.to_system_child(file="blk.yaml", name="b0", offset=0x0, address_space=0x100,
                          description="an instance")
    assert c.kind == "block"
    assert c.file == "blk.yaml"
    assert c.name == "b0"
    assert c.offset == 0x0
    assert c.address_space == 0x100
    assert c.description == "an instance"
    assert c.obj is b


def test_system_to_system_child():
    sys_ = RegisterSystem(name="inner")
    c = sys_.to_system_child(file="inner.yaml", name="i0", offset=0x0,
                             address_space=0x100, description="nested")
    assert c.kind == "system"
    assert c.file == "inner.yaml"
    assert c.name == "i0"
    assert c.obj is sys_


# ---------------------------------------------------------------------------
# 19. to_yaml requires file on SystemChild
# ---------------------------------------------------------------------------


def test_system_to_yaml_requires_file():
    b = _make_block("blk")
    # Corrupt: SystemChild has file=None — cannot serialize without a file path
    c = SystemChild(kind="block", file=None, obj=b, name="b0",
                    offset=0x0, address_space=0x100)
    sys_ = RegisterSystem(name="s", children=[c])
    with pytest.raises(ValueError, match="file is None"):
        sys_.to_yaml()


# ---------------------------------------------------------------------------
# 20. Deterministic output
# ---------------------------------------------------------------------------


def test_system_deterministic_output():
    b = _make_block("blk")
    sys_ = RegisterSystem(
        name="s",
        children=[
            b.to_system_child(file="blk.yaml", name="b0", offset=0x0, address_space=0x100),
        ],
        metadata={"k": "v"},
    )
    assert sys_.to_yaml() == sys_.to_yaml()


# ---------------------------------------------------------------------------
# 21. Hex format on children
# ---------------------------------------------------------------------------


def test_system_hex_format():
    b = _make_block("blk")
    sys_ = RegisterSystem(
        name="s",
        children=[
            b.to_system_child(file="blk.yaml", name="b0", offset=0x100, address_space=0x80),
        ],
    )
    text = sys_.to_yaml()
    assert "offset: 0x100" in text
    assert "address_space: 0x80" in text
