from pathlib import Path

import yaml

from .block import RegisterBlock
from .fields import (
    Field,
    RCField,
    RCWField,
    ROField,
    RWField,
    W1CField,
    W1SField,
    WOField,
)
from .register import Register
from .system import RegisterSystem, SystemChild

_ACCESS_TO_CLASS = {
    "RW": RWField,
    "RO": ROField,
    "WO": WOField,
    "W1C": W1CField,
    "W1S": W1SField,
    "RC": RCField,
    "RCW": RCWField,
}


class _HexInt(int):
    """int subclass that emits as hex in YAML."""


def _hex_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:int", f"0x{int(data):X}")


yaml.add_representer(_HexInt, _hex_representer, Dumper=yaml.SafeDumper)


def field_to_dict(field) -> dict:
    return {
        "name": field.name,
        "access": field.access,
        "width": field.width,
        "offset": field.offset,
        "reset": _HexInt(field.reset),
        "description": field.description,
        "metadata": field.metadata or {},
    }


def field_from_dict(data: dict) -> Field:
    access = data["access"]
    cls = _ACCESS_TO_CLASS.get(access)
    if cls is None:
        raise ValueError(f"Unknown field access type: {access!r}")
    return cls(
        name=data["name"],
        width=data["width"],
        offset=data.get("offset", 0),
        reset=data.get("reset", 0),
        description=data.get("description", ""),
        metadata=data.get("metadata", {}) or {},
    )


def register_to_dict(reg) -> dict:
    return {
        "name": reg.name,
        "offset": _HexInt(reg.offset),
        "description": reg.description,
        "metadata": reg.metadata or {},
        "fields": [field_to_dict(f) for f in reg.fields],
    }


def register_from_dict(data: dict) -> Register:
    return Register(
        name=data["name"],
        fields=[field_from_dict(f) for f in data.get("fields", [])],
        offset=data.get("offset", 0),
        description=data.get("description", ""),
        metadata=data.get("metadata", {}) or {},
    )


def block_to_dict(block) -> dict:
    d = {
        "block": block.name,
        "description": block.description,
        "width": block.width,
        "address_space": _HexInt(block.address_space),
        "module_name": block.module_name,
        "metadata": block.metadata or {},
        "registers": [register_to_dict(r) for r in block.registers],
    }
    if block.unique_field_names:
        d["unique_field_names"] = True
    if block.bare_field_ports:
        d["bare_field_ports"] = True
    return d


def block_from_dict(data: dict, base_dir=None) -> RegisterBlock:
    block = RegisterBlock(
        name=data["block"],
        registers=[register_from_dict(r) for r in data.get("registers", [])],
        width=data.get("width", 32),
        address_space=data.get("address_space", 256),
        description=data.get("description", ""),
        module_name=data.get("module_name"),
        metadata=data.get("metadata", {}) or {},
        unique_field_names=data.get("unique_field_names", False),
        bare_field_ports=data.get("bare_field_ports", False),
    )
    block._validate()
    return block


def dump_yaml(data: dict, path: Path | None = None) -> str:
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=4096)
    if path is not None:
        Path(path).write_text(text)
    return text


def load_yaml_text(text: str) -> dict:
    return yaml.safe_load(text)


def load_yaml(path) -> dict:
    return load_yaml_text(Path(path).read_text())


def child_to_dict(child) -> dict:
    if child.file is None:
        raise ValueError(
            f"Cannot serialize child {child.name!r}: file is None. "
            "Save the child block/system to YAML and set the file path."
        )
    return {
        "kind": child.kind,
        "file": child.file,
        "name": child.name,
        "offset": _HexInt(child.offset),
        "address_space": _HexInt(child.address_space),
        "description": child.description,
    }


def child_from_dict(data: dict, base_dir, _ancestors: set) -> SystemChild:
    kind = data["kind"]
    file = data["file"]
    child_path = (Path(base_dir) / file).resolve()

    if kind == "block":
        obj = RegisterBlock.from_yaml(child_path)
    elif kind == "system":
        if child_path in _ancestors:
            raise ValueError(f"Cycle detected: {child_path}")
        obj = system_from_dict(
            load_yaml(child_path),
            base_dir=base_dir,
            _ancestors=_ancestors | {child_path},
        )
    else:
        raise ValueError(f"Unknown child kind: {kind!r}")

    return SystemChild(
        kind=kind,
        file=file,
        obj=obj,
        name=data["name"],
        offset=data["offset"],
        address_space=data["address_space"],
        description=data.get("description", ""),
    )


def system_to_dict(system) -> dict:
    return {
        "system": system.name,
        "description": system.description,
        "metadata": system.metadata or {},
        "children": [child_to_dict(c) for c in system.children],
    }


def system_from_dict(data: dict, base_dir, _ancestors=None) -> RegisterSystem:
    if _ancestors is None:
        _ancestors = set()
    children = [
        child_from_dict(c, base_dir, _ancestors)
        for c in data.get("children", [])
    ]
    return RegisterSystem(
        name=data["system"],
        children=children,
        description=data.get("description", ""),
        metadata=data.get("metadata", {}) or {},
    )
