# Action Execution Engine

The Action Execution Engine is responsible for running the resolved actions from `ActionPlan`. It handles scheduling, backend dispatch, timeout limits, and error handling while strictly containing potential system side effects.

## Execution Model

- The execution is fully **asynchronous** based on `asyncio`.
- It executes steps in a **strict sequence** without parallel interleaving within a single plan.
- The Engine captures all outcomes into immutable, structured dataclasses (`ActionExecutionResult` and `StepExecutionResult`) with stable timestamps and statuses.

## State and Stop Policy

Available execution statuses: `SUCCESS`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `SKIPPED`, `BACKEND_UNAVAILABLE`.

### Stop-On-Failure

If any step in the sequence resolves to a status other than `SUCCESS` (e.g., `FAILED`, `TIMED_OUT`, `CANCELLED`, `BACKEND_UNAVAILABLE`), the engine will **stop** processing the rest of the plan. Any remaining unexecuted steps will be marked as `SKIPPED`.

### UNMAPPED vs NoOp

- **UNMAPPED**: When a control is completely unmapped in the configuration or its resolution fails gracefully, the engine does not attempt execution. The whole result is instantly marked as `SKIPPED`.
- **NoOp**: When explicitly configured as `type = "noop"`, the engine successfully passes over the step. It is considered a valid execution and yields a `SUCCESS` step status, allowing the rest of the macro to continue.

## Cancellation Semantics

The engine natively supports Python's `asyncio.Task.cancel()`.
- **Before Execution Starts**: The whole plan is `CANCELLED`.
- **Between Steps**: Ongoing execution halts, remaining steps are `SKIPPED`.
- **During a Delay**: The sleep is immediately terminated.
- **During a Command**: The subprocess receives a `SIGTERM`. If it does not terminate within the grace period, a `SIGKILL` is issued to reap the process cleanly. 

The `ActionExecutionEngine` **does not swallow** `asyncio.CancelledError`. It sets the execution records properly and then re-raises the error so the calling context handles the cancellation accurately.

## Command Execution & Security

Command action runs through the `AsyncSubprocessCommandRunner` which follows the `CommandExecutionPolicy`.

### Allowlist

Commands are entirely gated by a strict explicit `allow_commands` string set. If the command's base name is not in the set, it is rejected before creation.

### Shell Restrictions

- The engine strictly uses `asyncio.create_subprocess_exec` with an explicit `argv` array.
- **No Shell Eval**: Elements of `argv` are not concatenated or interpolated into a `/bin/sh` instance, avoiding injection vectors.
- Forbidden commands such as `sh`, `bash`, `dash`, `zsh`, `sudo`, and `su` are statically blocked by the policy, even if users try to include them. Path traversals (`.` or `..`) are also blocked.

### Timeout and Output Restrictions

Commands have explicit runtime bounds (e.g. `timeout_seconds=5`). When a timeout expires:
1. `SIGTERM` is sent.
2. The engine waits for `terminate_grace_period_seconds`.
3. If it is still alive, `SIGKILL` is sent.
4. Process output stream is capped strictly at `max_output_bytes` (default 64KB) incrementally. Output beyond this limit is truncated with a `[TRUNCATED]` suffix to protect host memory.

## Backends

### Desktop Input (xdotool)

Desktop inputs (like `HotkeyAction` and `TextAction`) use `XDoToolDesktopInputBackend`.
- **X11 Dependency**: Relies natively on `xdotool` in the `$PATH` and an active `$DISPLAY`.
- **Wayland Restriction**: Explicitly rejects execution under `$XDG_SESSION_TYPE=wayland` because `xdotool` operates unpredictably without native Wayland injection abstractions. In these sessions, the backend marks itself unavailable.
- **Unavailable Mode**: Without dependencies, it falls back to gracefully returning `BACKEND_UNAVAILABLE` on steps, rather than crashing the engine.

### Delay

`AsyncioDelayBackend` executes pure non-blocking yields (`asyncio.sleep()`) making it completely safe for cooperative multitasking.

### Debug Log

`PythonLoggingDebugLogBackend` dumps debug logs natively to the `logging` framework. Note that `DebugLogAction` message strings **may contain untrusted user configuration text**. The engine ensures it only touches `logger.debug` cleanly.

## What is NOT included

- There is no background Daemon in this phase. The engine does not poll evdev automatically yet.
- Wayland injection is explicitly deferred.
