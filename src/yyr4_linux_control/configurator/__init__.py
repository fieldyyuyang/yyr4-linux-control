"""Configurator Core — read-only graphical configuration preview.

Milestone 5.1: View Model construction + self-contained HTML generation.
No server, no browser, no editing, no hardware access.
"""

from .models import (
    ConfiguratorDocument, ProfileView, LayerView, ControlView, ActionView,
    ValidationDiagnostic,
)
from .builder import build_document
from .html import generate_html
from .writer import write_preview

__all__ = [
    "ConfiguratorDocument", "ProfileView", "LayerView", "ControlView",
    "ActionView", "ValidationDiagnostic",
    "build_document", "generate_html", "write_preview",
]
