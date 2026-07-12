"""Integration preflight and permission models."""

from __future__ import annotations

import os
import sys
import importlib.util
from dataclasses import dataclass
from typing import Protocol, Tuple, Optional

from yyr4_linux_control.device.discovery import YYR4Identity


@dataclass(frozen=True)
class DependencyStatus:
    """Status of an optional dependency."""
    name: str
    available: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class RuntimePreflight:
    """Preflight check results for the runtime environment."""
    python_supported: bool
    platform_supported: bool
    is_root: bool
    evdev: DependencyStatus
    pyudev: DependencyStatus
    ready_for_discovery: bool
    blockers: Tuple[str, ...]
    warnings: Tuple[str, ...]


def check_runtime_preflight() -> RuntimePreflight:
    """Check if the environment can safely run the Linux discovery and input adapters."""
    blockers = []
    warnings = []

    # Python version (minimum 3.9)
    python_supported = sys.version_info >= (3, 9)
    if not python_supported:
        blockers.append("Python 3.9+ is required")

    # Platform (Linux only)
    platform_supported = sys.platform.startswith("linux")
    if not platform_supported:
        blockers.append("Only Linux is supported by the yyr4_linux_control backend")

    # Root user check
    is_root = False
    if hasattr(os, "geteuid"):
        try:
            if os.geteuid() == 0:
                is_root = True
                blockers.append("Running as root is forbidden for safety and security reasons")
        except AttributeError:
            pass

    # Optional dependencies
    evdev_available = importlib.util.find_spec("evdev") is not None
    evdev_status = DependencyStatus(
        name="evdev",
        available=evdev_available,
        reason=None if evdev_available else "Missing evdev package"
    )
    if not evdev_available:
        blockers.append("evdev package is missing")

    pyudev_available = importlib.util.find_spec("pyudev") is not None
    pyudev_status = DependencyStatus(
        name="pyudev",
        available=pyudev_available,
        reason=None if pyudev_available else "Missing pyudev package"
    )
    if not pyudev_available:
        blockers.append("pyudev package is missing")

    ready_for_discovery = len(blockers) == 0

    return RuntimePreflight(
        python_supported=python_supported,
        platform_supported=platform_supported,
        is_root=is_root,
        evdev=evdev_status,
        pyudev=pyudev_status,
        ready_for_discovery=ready_for_discovery,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class PermissionCheck:
    """Results of a device permission check."""
    keyboard_readable: bool
    mouse_readable: bool
    all_required_readable: bool
    blockers: Tuple[str, ...]
    warnings: Tuple[str, ...]


class IdentityPermissionChecker(Protocol):
    """Protocol for checking if device nodes are accessible."""
    def check(self, identity: YYR4Identity) -> PermissionCheck:
        """Check accessibility of the identified device nodes."""
        ...


class FilesystemIdentityPermissionChecker:
    """Checks filesystem permissions of device nodes without opening them."""

    def check(self, identity: YYR4Identity) -> PermissionCheck:
        blockers = []
        warnings = []

        keyboard_readable = False
        if identity.keyboard and identity.keyboard.device_node:
            keyboard_readable = os.access(identity.keyboard.device_node, os.R_OK)
            if not keyboard_readable:
                blockers.append("keyboard device node is not readable by the current user")
        else:
            blockers.append("keyboard device node is missing from identity")

        mouse_readable = False
        if identity.mouse and identity.mouse.device_node:
            mouse_readable = os.access(identity.mouse.device_node, os.R_OK)
            if not mouse_readable:
                blockers.append("mouse device node is not readable by the current user")
        else:
            blockers.append("mouse device node is missing from identity")

        all_required_readable = keyboard_readable and mouse_readable

        return PermissionCheck(
            keyboard_readable=keyboard_readable,
            mouse_readable=mouse_readable,
            all_required_readable=all_required_readable,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )
