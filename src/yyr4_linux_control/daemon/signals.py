import asyncio
import signal
import sys
import logging

from .interfaces import SignalController

logger = logging.getLogger("yyr4_linux_control.daemon")

class NativeSignalController(SignalController):
    def setup(self, loop: asyncio.AbstractEventLoop, on_stop, on_reload) -> None:
        if sys.platform == "win32":
            return # signals not well supported on win32
            
        def handle_stop(signame):
            logger.info(f"Received {signame}, requesting stop.")
            on_stop()

        def handle_reload():
            logger.info("Received SIGHUP, requesting config reload.")
            on_reload()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_stop, sig.name)
            except NotImplementedError:
                pass

        try:
            loop.add_signal_handler(signal.SIGHUP, handle_reload)
        except NotImplementedError:
            pass
