# Layered Configuration Domain

## Overview
YYR4 implements a robust offline resolution engine that uses a layered configuration domain to support complex context-aware action mappings. This capability is managed entirely in the user space daemon (`yyr4d`) using schema_version=2.

## Concepts

### ProfileId
A Profile represents a full contextual configuration set (e.g. `production`, `gaming`, `presentation`). 
- A profile ID must be between 1 and 64 characters long and match the pattern `^[a-z][a-z0-9_-]{0,63}$`.

### LayerId
Within each profile, actions can be grouped into layers. The engine supports a strict predefined set of 9 layers:
- `general`
- `layer_1` through `layer_8`

**Note**: Every valid profile MUST contain a `general` layer as its base fallback.

## Resolution Logic
The resolution logic evaluates incoming events using a specific contextual pair: `(ProfileId, LayerId)` — typically referred to as the active profile and active layer.

1. **Active Layer Priority**: The engine first looks for an explicit control mapping in the active layer. If found, it is evaluated and returned. The `mapping_source` will be marked as `active_layer`.
2. **General Fallback**: If the active layer does not define a mapping for the control, the engine automatically falls back to the `general` layer of the same profile. The `mapping_source` is marked as `general_fallback`.
3. **Explicit NoOp Masking**: If you want to explicitly block a mapping inherited from the `general` layer without triggering an action, define a `NoOpAction` (e.g., `{ type = "noop" }`) in the active layer. The engine evaluates this as a valid `active_layer` mapping and will not fall back.
4. **Profile Isolation**: Profiles are completely isolated. A fallback will never traverse outside the active profile boundaries.

## Backwards Compatibility
The resolution engine preserves perfect backwards compatibility with `schema_version = 1`. 
When a schema v1 configuration is loaded, it is automatically encapsulated into:
- Default Profile: `default`
- Initial Layer: `general`
The result behaves identically to native v2 configurations without modifying the original configuration file on disk.

## Management CLI (yyr4ctl) Integration
The management CLI understands and reflects the layered model explicitly.

- **`yyr4ctl validate`**: Displays full schema details including schema version, default profile, initial layer, profile count, and layer count.
- **`yyr4ctl show-config`**: Presents a clear hierarchical tree structure of the loaded configuration (Profile -> Layer -> Controls).
- **`yyr4ctl dry-run`**: Supports resolving a control offline by explicitly specifying `--profile` and `--layer`. By default, it uses the configuration's `default_profile` and `initial_layer`. It clearly reports the resolution `Mapping Source` (e.g. `active_layer`, `general_fallback`, `unmapped`).

## Daemon Compatibility
Currently, the daemon runtime is fixed to load and execute using the `default_profile` and `initial_layer` as defined in the configuration. 
**Note**: Dynamic active layer switching and runtime multi-layer contexts are planned for Milestone 3.2. There are no runtime layer-switching mechanisms active at this stage. No hardware tests are required for M3.1 validation.
