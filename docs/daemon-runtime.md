# Daemon Runtime (M2.3)

The daemon runtime provides the `yyr4d` executable that orchestrates the entire control system lifecycle.

## Overview

`yyr4d` connects the Observation Pipeline (Transport), Control Actions (Configuration), and Action Execution Engine into a long-running background service.

### Features
* **Configurable**: Driven by `RuntimeSettings` and an action configuration TOML file.
* **Resilient**: Automatic backoff and reconnection logic if the device disconnects or the pipeline fails.
* **Bounded execution**: Action plans are buffered in a limited-capacity `DropNewestActionQueue` to prevent unbound growth on slow execution or high burst rates.
* **Signal Handling**: Graceful stop on `SIGINT` and `SIGTERM`. Configuration hot-reload on `SIGHUP`.
* **Safe execution**: Rejects execution if run as root. Uses `DRY_RUN` mode by default, requiring an explicit `--execute` flag.

## Components

1. **`ProductionInputSession` / `InputSessionFactory`**
   Adapts the `IntegrationComposition` (preflight -> discovery -> observation) into an asynchronous event stream that produces `OfficialControlEvent` objects.

2. **`DaemonRuntime`**
   Maintains the state machine of the daemon:
   - Evaluates initial configuration validity (`load_control_config_from_file`).
   - Runs a concurrent executor loop reading from the ActionQueue.
   - Runs a concurrent hot-reload loop waiting for `SIGHUP` events.
   - Reconnects with exponential backoff on `RecoverableSessionError`.
   - Halts completely on `FatalRuntimeError` (e.g. invalid config or missing required system features).

3. **`DropNewestActionQueue`**
   A specialized bounded queue (`asyncio.Queue` backend). Once capacity is hit, incoming events are rejected and discarded, rather than blocking the observation pipeline. This keeps the daemon responsive to device disconnects or signals even if an executed command is stuck.

4. **`NativeSignalController`**
   A platform-specific signal watcher hooking Unix signals (`SIGINT`, `SIGTERM`, `SIGHUP`) into Python `asyncio.Event`s that gracefully interrupt the runtime loop.

5. **`ManagementServer`**
   A Unix Domain Socket server (`$XDG_RUNTIME_DIR/yyr4d.sock`) that exposes a local JSON API. Validates caller identity using `SO_PEERCRED`. Serves the `yyr4ctl` management plane without interrupting the main event loop.

## Flow

1. Initialize `RuntimeSettings` from CLI arguments.
2. Verify EUID != 0.
3. Hook `SIGINT`, `SIGTERM`, `SIGHUP`.
4. Enter `DaemonRuntime.run()`:
   * Evaluate initial configuration.
   * Start `executor_loop` and `reload_loop` as background tasks.
   * Start connecting session loop with reconnect backoff tracking.
   * In session loop, map `OfficialControlEvent`s using `ActionResolver`. Enqueue resolved plans.
5. On `SIGTERM`/`SIGINT`, stop receiving events, cancel pending background tasks, wait up to a grace period for the executor, then exit cleanly.
