# Observation Pipeline

The Observation Pipeline connects device discovery, input reading, and transport parsing into a single asynchronous event stream for read-only control observation.

## Architecture

`DeviceSelector` -> `RawInputStream` -> `TransportParser` -> `ControlEvent` Stream

- **Device Discovery**: Only uses the mock/backend to safely find the YYR4 device. Fails closed on mismatches.
- **Input Stream**: Wraps Evdev adapters.
- **Parser**: Converts `RawKeyEvent` to `ControlEvent`.
- **Pipeline**: Coordinates the above, handles cancellations, EOF, and error isolation without running any actual commands or device writes.

## Security Constraints

- Currently Read-Only.
- Does NOT execute `ControlEvent`s.
- Does NOT `EVIOCGRAB` or take exclusive lock of the input device.
- Does NOT create a `uinput` virtual device.
- Requires no elevated privileges to run in simulated/test mode.
- Users do NOT need to switch their profiles to the Transport Codes just yet.

## Source Isolation
The pipeline drops any events from `mouse` sources or unknown sources. Only `yyr4:keyboard` events are parsed, ensuring mouse movements don't corrupt the modifier state.

## Reset and Error Handling
- Normal EOF triggers a synthetic `UP` event for any active controls with `reason="reset"`.
- Input Errors will yield synthetic `UP` events before raising an `ObservationInputError`.
- `CancelledError` correctly drops synthetic yield attempts and propagates the cancellation.
- Concurrent `close()` calls are properly supported to teardown asynchronously.
