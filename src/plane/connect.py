class Builder:
    """Global builder state."""

    _stack: list = []

    @classmethod
    def current_module(cls):
        """Get the currently active module."""
        return cls._stack[-1] if cls._stack else None

    @classmethod
    def push(cls, module):
        """Enter a module's context."""
        cls._stack.append(module)

    @classmethod
    def pop(cls):
        """Exit current module context."""
        if cls._stack:
            cls._stack.pop()
