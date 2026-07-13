import asyncio
import unittest
import sys
from yyr4_linux_control.execution.command import CommandExecutionPolicy, AsyncSubprocessCommandRunner
from yyr4_linux_control.execution.errors import CommandRejectedError, CommandTimeoutError, CommandExecutionError

class TestExecutionCommand(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.policy = CommandExecutionPolicy(
            allow_commands={"echo", "sleep", sys.executable.split('/')[-1]},
            max_timeout_seconds=2,
            max_output_bytes=10,
            terminate_grace_period_seconds=0.1
        )
        self.runner = AsyncSubprocessCommandRunner(self.policy)

    def test_policy_allow(self):
        self.assertTrue(self.policy.is_allowed(("echo", "hello")))
        self.assertFalse(self.policy.is_allowed(("not_allowed",)))
        self.assertFalse(self.policy.is_allowed(("/bin/echo",))) # no slashes
        self.assertFalse(self.policy.is_allowed(("bash", "-c", "echo")))
        self.assertFalse(self.policy.is_allowed(("sudo", "echo")))

    async def test_run_success(self):
        # We will use python executable itself
        # since python executable filename could be 'python3'
        cmd = sys.executable.split('/')[-1]
        code, stdout, stderr = await self.runner.run((cmd, "-c", "print('hello')"), timeout_seconds=1)
        self.assertEqual(code, 0)
        # Note: 'hello\n' is 6 bytes, fits in 10 bytes limit
        self.assertEqual(stdout.strip(), b"hello")

    async def test_run_truncated(self):
        cmd = sys.executable.split('/')[-1]
        code, stdout, stderr = await self.runner.run((cmd, "-c", "print('hello world of very long output')"), timeout_seconds=1)
        self.assertEqual(code, 0)
        self.assertIn(b"[TRUNCATED]", stdout)
        self.assertEqual(len(stdout), 10 + len(b"\n[TRUNCATED]"))

    async def test_run_timeout(self):
        cmd = sys.executable.split('/')[-1]
        with self.assertRaises(CommandTimeoutError):
            await self.runner.run((cmd, "-c", "import time; time.sleep(10)"), timeout_seconds=1)

    async def test_run_rejected(self):
        with self.assertRaises(CommandRejectedError):
            await self.runner.run(("not_allowed",), timeout_seconds=1)
