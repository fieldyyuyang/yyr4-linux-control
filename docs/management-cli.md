# Management CLI (yyr4ctl)

The `yyr4ctl` is the official Management Command Line Interface for the EOSMOSI YYR4 Linux Control system. It provides an interface to query daemon state, validate configuration offline, and trigger runtime behaviors securely via Unix Domain Sockets (UDS).

## Architecture

The CLI is completely unprivileged. It does not require `sudo` or access to hardware devices. It operates via two distinct modes:

1. **Offline Mode**: Operates purely on local files, doing dry-runs and validation without contacting the daemon.
2. **Daemon Connected Mode**: Communicates with the daemon over a `SO_PEERCRED`-secured UDS located at `$XDG_RUNTIME_DIR/yyr4d.sock`.

### Offline Commands

These commands operate using `yyr4_linux_control.control.config` directly.

*   `validate <path>`: Syntactically and semantically validates a TOML control configuration file.
*   `list-controls`: Lists all officially supported hardware control names.
*   `show-config <path>`: Displays a flattened interpretation of a control configuration.
*   `dry-run <path> <control>`: Mocks the execution of an action mapped to the specified control.
*   `preview --config <path> --output <path>`: Generate a read-only HTML configuration preview.
*   `draft create|set-action|clear-action|validate|diff|save ...`: Offline draft editing workflow.
*   `editor --config SOURCE [--target TARGET] [--backup-dir DIR] [--port 0] [--idle-timeout 1800] [--open-browser]`: Start the local graphical editor.
*   `list-controls`: Lists all officially supported hardware control names.
*   `show-config <path>`: Displays a flattened interpretation of a control configuration, with an option to `--show-sensitive` data.
*   `dry-run <path> <control>`: Mocks the execution of an action mapped to the specified control using `DryRunExecutor` without real side effects.

### Connected Commands

These commands require the daemon to be running and the UID of the CLI caller to match the UID of the daemon process.

*   `status`: Retrieves the current telemetry and runtime state of the daemon.
*   `reload`: Instructs the daemon to atomically reload its configuration.
*   `ping`: Verifies the management socket responds.

## Security Constraints

*   **No Arbitrary Commands**: The daemon management socket accepts only strict, predefined payloads.
*   **UID Verification**: Uses `SO_PEERCRED` to guarantee the management command is initiated by the exact same user identity as the daemon, preventing privilege escalation.
*   **No Remote Management**: TCP, HTTP, and DBus are explicitly avoided. The local filesystem permission acts as the boundary.

## Exit Codes

The CLI strictly adheres to defined exit codes for scripting integration:
*   `0`: `EXIT_SUCCESS`
*   `2`: `EXIT_ARGS` (Invalid arguments provided)
*   `3`: `EXIT_CONFIG` (Offline configuration is invalid)
*   `4`: `EXIT_NOT_RUNNING` (Daemon is not running or UDS socket is missing)
*   `5`: `EXIT_PROTOCOL` (Socket communication error)
*   `6`: `EXIT_REJECTED` (Command was explicitly rejected by the daemon)
*   `7`: `EXIT_RELOAD_FAILED` (Daemon rejected the reload)
*   `8`: `EXIT_PERMISSION` (UID validation failed via `SO_PEERCRED`)
*   `9`: `EXIT_INTERNAL` (Unexpected CLI internal failure)
