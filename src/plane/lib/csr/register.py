
from .fields import Field


class Register:
    """A register composed of one or more fields."""

    def __init__(
        self,
        name: str,
        fields: list[Field] = None,
        offset: int = 0,
        description: str = "",
        metadata: dict = None,
    ):
        self.name = name
        self.fields = fields or []
        self.offset = offset
        self.description = description
        self.metadata = metadata or {}

    def to_yaml(self, path=None) -> str:
        from .yaml_io import dump_yaml, register_to_dict

        return dump_yaml(register_to_dict(self), path)

    @classmethod
    def from_yaml(cls, path):
        from .yaml_io import load_yaml, register_from_dict

        return register_from_dict(load_yaml(path))
