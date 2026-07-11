class SystemChild:
    """A child entry in a RegisterSystem — wraps a block or system with
    parent-assigned relationship data (offset, name, allocated address_space)."""

    def __init__(
        self,
        kind: str,
        file: str,
        name: str,
        offset: int,
        address_space: int,
        obj,
        description: str = "",
    ):
        self.kind = kind
        self.file = file
        self.name = name
        self.offset = offset
        self.address_space = address_space
        self.obj = obj
        self.description = description


class RegisterSystem:
    """A collection of RegisterBlocks and/or other RegisterSystems.
    Used to build collateral (UVM RAL, HTML docs) — not for HW generation."""

    def __init__(
        self,
        name: str,
        children: list = None,
        description: str = "",
        metadata: dict = None,
    ):
        self.name = name
        self.children = children or []
        self.description = description
        self.metadata = metadata or {}

    @property
    def address_space(self) -> int:
        if not self.children:
            return 0
        return max(c.offset + c.address_space for c in self.children)

    def to_system_child(self, file, name, offset, address_space, description=""):
        return SystemChild(
            kind="system",
            file=file,
            obj=self,
            name=name,
            offset=offset,
            address_space=address_space,
            description=description,
        )

    def _validate(self, validate_children=True):
        errors = []
        seen_names = set()
        ranges = []

        for child in self.children:
            if child.name in seen_names:
                errors.append(f"Duplicate child name: {child.name}")
            seen_names.add(child.name)

            inherent = child.obj.address_space
            if child.address_space < inherent:
                errors.append(
                    f"Child {child.name} allocated {child.address_space:#x} "
                    f"< inherent {inherent:#x}"
                )

            lo, hi = child.offset, child.offset + child.address_space
            for lo2, hi2, name2 in ranges:
                if lo < hi2 and lo2 < hi:
                    errors.append(
                        f"Child {child.name} [{lo:#x}, {hi:#x}) overlaps "
                        f"{name2} [{lo2:#x}, {hi2:#x})"
                    )
            ranges.append((lo, hi, child.name))

        if validate_children:
            for child in self.children:
                if hasattr(child.obj, "_validate"):
                    if isinstance(child.obj, RegisterSystem):
                        child.obj._validate(validate_children=True)
                    else:
                        child.obj._validate()

        if errors:
            raise ValueError("RegisterSystem validation failed:\n  - " + "\n  - ".join(errors))

    def to_yaml(self, path=None) -> str:
        from .yaml_io import system_to_dict, dump_yaml

        return dump_yaml(system_to_dict(self), path)

    @classmethod
    def from_yaml(cls, path, base_dir=None, validate_children=True):
        from .yaml_io import system_from_dict, load_yaml

        from pathlib import Path

        path = Path(path)
        if base_dir is None:
            base_dir = path.parent
        system = system_from_dict(
            load_yaml(path),
            base_dir=base_dir,
            _ancestors={path.resolve()},
        )
        system._validate(validate_children=validate_children)
        return system

    def to_html(self, output_dir):
        from .html import generate_html

        generate_html(self, output_dir)

    def to_uvm_ral(self, output_path=None) -> str:
        from .uvm_ral import generate_uvm_ral

        return generate_uvm_ral(self, output_path)

    def to_c_header(self, output_dir, prefix_block_name=True) -> None:
        from .c_header import generate_c_header

        generate_c_header(self, output_dir, prefix_block_name)
