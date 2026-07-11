# Width Checking

plane can detect width mismatches on connections (`@=`) and warn or error at elaboration time.

## Default Behavior

By default, plane warns on width mismatches:

```python
from plane import *

class M(Module):
    def elaborate(self):
        self.a = IO(Input(UInt(8)), name="a")
        self.out = IO(Output(UInt(4)), name="out")
        self.out @= self.a  # Warning: Width mismatch: out (4) <- a (8)
```

## Modes

Control behavior with `width_mismatch_mode`:

```python
from plane import width_mismatch_mode, WidthMismatchError

# Warn (default)
width_mismatch_mode = "warn"

# Error — raises WidthMismatchError on mismatch
width_mismatch_mode = "error"

# Silent — no warnings
width_mismatch_mode = "silent"
```

## Checking Widths

Use `get_node_width()` to inspect a node's width:

```python
from plane.utils import get_node_width

w = get_node_width(self.a)  # returns int
```

## Gotchas

- **Parameterized types are skipped** — Width checking does not apply when a type uses a `Parameter` (e.g., `UInt(self.WIDTH)`).
- **Only `@=` connections are checked** — Python assignment (`=`) is not checked.

## Next

Read the [FSM Example](13_fsm_example.md) to see everything put together.
