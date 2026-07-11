# CSR Collateral Generation

Beyond hardware generation, plane's CSR library can produce documentation and verification collateral: YAML descriptions, UVM RAL models, and HTML documentation with interactive bitfield diagrams.

## YAML Serialization

Register blocks and systems can be serialized to YAML for version control, sharing, or external tool integration:

```python
# Save a block to YAML
block.to_yaml("timer.yaml")

# Load a block from YAML
loaded_block = RegisterBlock.from_yaml("timer.yaml")
```

YAML output includes all register and field definitions, offsets, widths, access types, reset values, and descriptions. Field connections are not serialized (they're Python objects, not serializable data).

### YAML Structure

A typical YAML file looks like:

```yaml
block: timer
description: Timer peripheral
width: 32
address_space: 256
module_name: timer
metadata: {}
registers:
  - name: ctrl
    offset: 0
    description: Control register
    metadata: {}
    fields:
      - name: enable
        width: 1
        offset: 0
        reset: 0
        access: RW
        description: Enable bit
        metadata: {}
      - name: mode
        width: 3
        offset: 4
        reset: 5
        access: RW
        description: Timer mode
        metadata: {}
  - name: status
    offset: 4
    description: Status register
    metadata: {}
    fields:
      - name: done
        width: 1
        offset: 0
        reset: 0
        access: RO
        description: Timer done flag
        metadata: {}
```

### Register Systems in YAML

`RegisterSystem` objects can also be serialized. Child blocks and sub-systems are referenced by file path:

```python
system.to_yaml("soc.yaml")
```

The YAML includes a `children` list with each child's kind, file path, name, offset, and address space. When loading, child files are resolved relative to the parent YAML's directory (or a specified `base_dir`).

## UVM RAL Generation

Generate UVM Register Abstraction Layer (RAL) models for testbench integration:

```python
# Generate UVM RAL for a block
ral_sv = block.to_uvm_ral()

# Write to file
block.to_uvm_ral("timer_ral.sv")

# Generate for a system (includes all child blocks)
system.to_uvm_ral()
```

### Generated Classes

For a `RegisterBlock` named "timer" with registers "ctrl" and "status":

- **Register classes**: `timer_ctrl`, `timer_status` (one per register, prefixed with block name)
- **Block class**: `timer` (extends `uvm_reg_block`, contains register instances)

For a `RegisterSystem`, the top-level class contains sub-block instances and address map configuration.

### Access Type Mapping

| plane Access | UVM RAL Access | Volatile |
|--------------|----------------|----------|
| RW | RW | 0 |
| RO | RO | 1 |
| WO | WO | 0 |
| W1C | W1C | 1 |
| W1S | W1S | 1 |
| RC | RC | 1 |
| RCW | WRC | 1 |

The `volatile` flag is set based on whether hardware can change the field value independently of software writes.

### Example Output

```systemverilog
class timer_ctrl extends uvm_reg;
  rand uvm_reg_field enable;
  rand uvm_reg_field mode;

  function new(string name = "timer_ctrl");
    super.new(name, 32, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    enable = uvm_reg_field::type_id::create("enable");
    enable.configure(this, 1, 0, "RW", 0, 1'h0, 1, 1, 0);
    mode = uvm_reg_field::type_id::create("mode");
    mode.configure(this, 3, 4, "RW", 0, 3'h5, 1, 1, 0);
  endfunction

  `uvm_object_utils(timer_ctrl)
endclass

class timer extends uvm_reg_block;
  rand timer_ctrl ctrl;
  rand timer_status status;

  function new(string name = "timer");
    super.new(name, UVM_NO_COVERAGE);
  endfunction

  virtual function void build();
    default_map = create_map("default_map", 0, 4, UVM_LITTLE_ENDIAN, 0);
    ctrl = timer_ctrl::type_id::create("ctrl");
    ctrl.configure(this, null, "");
    ctrl.build();
    default_map.add_register(ctrl, 'h0);
    status = timer_status::type_id::create("status");
    status.configure(this, null, "");
    status.build();
    default_map.add_register(status, 'h4);
  endfunction

  `uvm_object_utils(timer)
endclass
```

### Multi-Instance Blocks

When a `RegisterSystem` contains multiple instances of the same block, the RAL model generates one class definition and multiple instances:

```systemverilog
class soc extends uvm_reg_block;
  rand timer timer0;
  rand timer timer1;

  virtual function void build();
    default_map = create_map("default_map", 0, 4, UVM_LITTLE_ENDIAN, 0);
    timer0 = timer::type_id::create("timer0");
    timer0.configure(this, null, "");
    timer0.build();
    default_map.add_submap(timer0.default_map, 'h1000);
    timer1 = timer::type_id::create("timer1");
    timer1.configure(this, null, "");
    timer1.build();
    default_map.add_submap(timer1.default_map, 'h2000);
  endfunction

  `uvm_object_utils(soc)
endclass
```

## HTML Documentation

Generate interactive HTML documentation with WaveDrom bitfield diagrams:

```python
# Generate docs for a block
block.to_html("docs_output/")

# Generate docs for a system (includes all child blocks)
system.to_html("docs_output/")
```

### Directory Structure

For a `RegisterSystem` named "soc" with blocks "timer" and "uart":

```
docs_output/
  index.html              # Root page with sidebar navigation
  blocks/
    timer.html            # Timer block documentation
    uart.html             # UART block documentation
  systems/
    soc.html              # SoC system page with address map
  _static/
    search.json           # Search index for documentation
```

### Page Contents

**Block pages** include:
- Register list with descriptions
- WaveDrom bitfield diagrams (interactive, rendered in browser)
- Field tables with offset, width, access type, reset value, and description
- Sidebar navigation showing the instance hierarchy

**System pages** include:
- Address map table with child block/sub-system ranges
- Links to child block and sub-system pages
- Sidebar navigation

**Index page** includes:
- Top-level title and description
- Sidebar navigation tree

### WaveDrom Integration

Bitfield diagrams use [WaveDrom](https://wavedrom.com/) for rendering. The diagrams are embedded as JSON in `<script type="WaveDrom">` tags and rendered client-side by the WaveDrom JavaScript library (loaded from CDN).

Example bitfield diagram for a register:

```
+-------+-------+-------+
| mode  |  gap  |enable |
| [6:4] | [3:1] |  [0]  |
+-------+-------+-------+
```

The diagrams are color-coded by access type and include field names and bit ranges.

### Search Index

The `search.json` file contains a searchable index of all blocks, registers, and fields with their descriptions. This can be integrated with a search UI for quick navigation.

## C Header Generation

Generate C header files for firmware integration:

```python
# Generate C header for a block
header = block.to_c_header()

# Write to file
block.to_c_header("timer.h")

# Generate for a system (writes one .h per block + one per system to directory)
system.to_c_header("headers/")

# Disable block name prefix in define names
block.to_c_header("timer.h", prefix_block_name=False)
```

### Generated Content

For a `RegisterBlock` named "timer" with register "ctrl" and field "enable":

```c
#ifndef TIMER_H
#define TIMER_H

/*
 * timer
 * Description: Timer peripheral
 */

/*
 * ctrl
 * Description: Control register
 */
#define TIMER_CTRL_ADDR          0x0000
#define TIMER_CTRL_RESET         0x00000050

/*
 * enable
 * Description: Enable bit
 * Access: RW
 */
#define TIMER_CTRL_ENABLE_OFFSET      0
#define TIMER_CTRL_ENABLE_WIDTH       1
#define TIMER_CTRL_ENABLE_MASK        0x1
#define TIMER_CTRL_ENABLE_BYTE_OFFSET 0

/* ... more fields ... */

/* Generic field access macros */
#ifndef PLANE_FIELD_MACROS
#define PLANE_FIELD_MACROS

#define REG_READ(base, offset)        (*((volatile uint32_t *)((uintptr_t)(base) + (offset))))
#define REG_WRITE(base, offset, val) (*((volatile uint32_t *)((uintptr_t)(base) + (offset))) = (uint32_t)(val))

#define GET_FIELD(reg, field)          (((uint32_t)(reg) >> field##_OFFSET) & field##_MASK)
#define UPDATE_FIELD(reg, field, val) (((uint32_t)(reg) & ~((uint32_t)field##_MASK << field##_OFFSET)) | (((val) & field##_MASK) << field##_OFFSET))

#define FIELD8_WRITE(base, offset, field, val) \
    (*((volatile uint8_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \
        (uint8_t)((val) & field##_MASK))

#define FIELD16_WRITE(base, offset, field, val) \
    (*((volatile uint16_t *)((uintptr_t)(base) + (offset) + field##_BYTE_OFFSET)) = \
        (uint16_t)((val) & field##_MASK))

#endif

#endif /* TIMER_H */
```

### Define Naming

By default, defines are prefixed with the block name:
- `TIMER_CTRL_ADDR` — register address
- `TIMER_CTRL_RESET` — computed reset value (sum of field resets)
- `TIMER_CTRL_ENABLE_OFFSET` — field bit offset
- `TIMER_CTRL_ENABLE_WIDTH` — field width
- `TIMER_CTRL_ENABLE_MASK` — field bitmask
- `TIMER_CTRL_ENABLE_BYTE_OFFSET` — byte index for byte-level access

Set `prefix_block_name=False` to omit the block prefix:
- `CTRL_ADDR`, `CTRL_ENABLE_OFFSET`, etc.

### Generic Macros

The header includes generic macros for firmware use:

**32-bit read-modify-write:**
```c
uint32_t reg_val = REG_READ(base, TIMER_CTRL_ADDR);
reg_val = UPDATE_FIELD(reg_val, TIMER_CTRL_ENABLE, 1);
REG_WRITE(base, TIMER_CTRL_ADDR, reg_val);
```

**8-bit direct write** (field must be sole occupant of its byte):
```c
FIELD8_WRITE(base, TIMER_CTRL_ADDR, TIMER_CTRL_ENABLE, 1);
```

**16-bit direct write** (field must be sole occupant of its halfword):
```c
FIELD16_WRITE(base, TIMER_CTRL_ADDR, TIMER_CTRL_MODE, 5);
```

### System Headers

For a `RegisterSystem`, one `.h` file is generated per unique block plus one per system. System headers include child block headers and define child offsets:

```c
#ifndef SOC_H
#define SOC_H

/*
 * soc
 * Description: Top-level SoC
 */

#include "timer.h"
#include "uart.h"

/* Child block/system offsets */
#define SOC_TIMER_OFFSET    0x0000
#define SOC_UART_OFFSET     0x1000

#endif /* SOC_H */
```

### Comments

Block, register, and field comments are generated from `description` and `metadata` attributes:
- Empty `description` or `metadata` lines are omitted
- Field comments always include the `Access` type (RW, RO, etc.)
- Register/field offset, width, and reset are not duplicated in comments (they're in the defines)

## Gotchas

- **YAML doesn't serialize connections** — Field `connection` parameters are Python objects and aren't saved to YAML. When loading from YAML, you'll need to re-establish connections in Python.
- **UVM RAL requires manual integration** — The generated `.sv` file contains class definitions but no `import uvm_pkg::*;` or `include "uvm_macros.svh"`. You need to wrap it in your own package or include it in your testbench.
- **HTML docs require internet for WaveDrom** — The WaveDrom library is loaded from a CDN. For offline viewing, you'd need to download and host the library locally.
- **Custom field types need collateral support** — If you create a custom field type with a non-standard `access` string, the UVM RAL generator won't know how to map it. You'd need to extend the generator or use a standard access type.

## Next

See the [FSM Example](13_fsm_example.md) for a complete example combining enums, conditionals, and registers in a state machine.
