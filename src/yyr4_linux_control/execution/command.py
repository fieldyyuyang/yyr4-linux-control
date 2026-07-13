import asyncio
import os
from dataclasses import dataclass
from typing import Tuple, Optional, Set, List

from .interfaces import CommandRunner
from .errors import CommandRejectedError, CommandTimeoutError, CommandExecutionError

@dataclass(frozen=True)
class CommandExecutionPolicy:
    allow_commands: Set[str]
    max_timeout_seconds: int = 10
    max_output_bytes: int = 65536  # 64 KB
    terminate_grace_period_seconds: float = 1.0
    max_argv_items: int = 50
    max_argv_item_length: int = 4096

    def is_allowed(self, argv: Tuple[str, ...]) -> bool:
        if not argv:
            return False
        if len(argv) > self.max_argv_items:
            return False
        for arg in argv:
            if len(arg) > self.max_argv_item_length:
                return False
                
        cmd = argv[0]
        # Reject shell wrappers and paths that could bypass allowlist
        forbidden_shells = {"sh", "bash", "dash", "zsh", "sudo", "su"}
        if cmd in forbidden_shells:
            return False
        
        if "/" in cmd:
            # We don't allow relative paths or arbitrary path execution 
            # to bypass the command name check easily unless explicitly designed, 
            # but for safety, we only allow commands by their basename.
            return False
        if cmd == ".." or cmd == ".":
            return False

        if cmd not in self.allow_commands:
            return False
            
        return True

class AsyncSubprocessCommandRunner(CommandRunner):
    def __init__(self, policy: CommandExecutionPolicy):
        self.policy = policy

    async def _read_stream(self, stream: Optional[asyncio.StreamReader], limit: int) -> Tuple[bytes, bool]:
        if stream is None:
            return b"", False

        chunks = []
        total_bytes = 0
        truncated = False

        while True:
            try:
                # Read in small chunks to avoid memory spikes
                chunk = await stream.read(4096)
                if not chunk:
                    break
                
                if total_bytes + len(chunk) > limit:
                    allowed = limit - total_bytes
                    if allowed > 0:
                        chunks.append(chunk[:allowed])
                    truncated = True
                    break
                
                chunks.append(chunk)
                total_bytes += len(chunk)
            except Exception:
                # If stream reading fails, stop
                break

        return b"".join(chunks), truncated

    async def run(self, argv: Tuple[str, ...], timeout_seconds: Optional[int]) -> Tuple[int, bytes, bytes]:
        if not self.policy.is_allowed(argv):
            raise CommandRejectedError(f"Command not allowed or invalid: {argv[0] if argv else '<empty>'}")

        effective_timeout = timeout_seconds if timeout_seconds is not None else self.policy.max_timeout_seconds
        if effective_timeout > self.policy.max_timeout_seconds:
            effective_timeout = self.policy.max_timeout_seconds

        try:
            # We must use create_subprocess_exec per requirements
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=True  # Isolate from parent signal group
            )
        except OSError as e:
            raise CommandExecutionError(f"Failed to start process: {e}")

        # Create tasks to read stdout and stderr with limits
        stdout_task = asyncio.create_task(self._read_stream(proc.stdout, self.policy.max_output_bytes))
        stderr_task = asyncio.create_task(self._read_stream(proc.stderr, self.policy.max_output_bytes))
        
        try:
            # Wait for process to finish with timeout
            await asyncio.wait_for(proc.wait(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            # Terminate and kill logic
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
                
            try:
                await asyncio.wait_for(proc.wait(), timeout=self.policy.terminate_grace_period_seconds)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
            
            raise CommandTimeoutError(f"Command exceeded {effective_timeout} seconds")
        except asyncio.CancelledError:
            # Properly clean up on task cancellation
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=self.policy.terminate_grace_period_seconds)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass
            raise

        # Harvest output
        out_bytes, out_trunc = await stdout_task
        err_bytes, err_trunc = await stderr_task

        # If truncated, we append a marker
        if out_trunc:
            out_bytes += b"\n[TRUNCATED]"
        if err_trunc:
            err_bytes += b"\n[TRUNCATED]"

        exit_code = proc.returncode if proc.returncode is not None else -1

        return exit_code, out_bytes, err_bytes
