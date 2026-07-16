"""Local graphical configuration editor (M5.3).

Provides a self-contained HTTP server that hosts an interactive,
browser-based configuration editor.  No daemon connection, no hardware
access, no action execution — purely offline configuration editing.
"""

from .session import EditorSession
from .server import EditorServer

__all__ = ["EditorSession", "EditorServer"]
