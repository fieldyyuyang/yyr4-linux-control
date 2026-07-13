# Control Action Configuration

This document describes how to map official YYR4 controls to executable actions.

**Note**: In Milestone 2.1, the Action Execution Engine is not yet implemented. This means configurations can be loaded and validated, and actions can be planned, but they will **not actually be executed on the system**. Execution will be implemented in Milestone 2.2.

## Official Controls

The configuration uses the official physical naming convention:

* **Keys**: `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A7`, `A8`, `A9`, `A10`, `A11`, `A12`
* **Encoders (Left/Press/Right)**: 
  * `AL`, `AP`, `AR`
  * `BL`, `BP`, `BR`
  * `CL`, `CP`, `CR`
  * `DL`, `DP`, `DR`

## Configuration Format

The configuration file is a TOML document with `schema_version = 1`. Each control is defined under the `[controls.<NAME>]` table, and its action is defined in the `[controls.<NAME>.action]` table.

```toml
schema_version = 1

[controls.A1.action]
type = "hotkey"
keys = ["CTRL", "SHIFT", "C"]
```

### Unmapped vs NoOp

- **Unmapped (Missing)**: If a control is not listed in the configuration, or lacks an `action` block, it is considered `UNMAPPED`.
- **Explicit NoOp**: If a control is explicitly configured with `type = "noop"`, it is `CONFIGURED` to do nothing.

## Action Types

### Hotkey Action
Simulates a keyboard shortcut.
```toml
[controls.A1.action]
type = "hotkey"
keys = ["CTRL", "SHIFT", "V"]
```

### Text Action
Outputs a literal string.
```toml
[controls.A2.action]
type = "text"
value = "Hello World"
```

### Command Action
Executes an external command without invoking a shell. You must provide `argv` as a list of strings.
```toml
[controls.AL.action]
type = "command"
argv = ["echo", "Volume Down"]
timeout_seconds = 5
```

### Delay Action
Waits for the specified number of milliseconds.
```toml
[controls.A3.action]
type = "delay"
milliseconds = 500
```

### Debug Log Action
Logs a message to the debugging console.
```toml
[controls.A4.action]
type = "debug_log"
message = "A4 was pressed"
```

### Macro Action
Executes a sequence of actions in order. Macros can contain other macros up to a maximum depth of 10, and a maximum total flattened step limit of 100.
```toml
[controls.AP.action]
type = "macro"
steps = [
    { type = "hotkey", keys = ["CTRL", "ENTER"] },
    { type = "text", value = "---" },
    { type = "hotkey", keys = ["CTRL", "ENTER"] }
]
```

## Dry-Run Execution

To verify your configuration without any side-effects, you can use the `DryRunExecutor` API. It parses the control events and emits a structural trajectory of the actions it would have performed.

* Command actions will only log the `argv`, they will not spawn processes.
* Delay actions will only record the wait time, they will not sleep.
* Hotkey and text actions are safely recorded but not injected.
