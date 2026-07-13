"""Identity and permission validation application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from yyr4_linux_control.device.discovery import DiscoveryBackend, YYR4DeviceDiscovery
from yyr4_linux_control.device.errors import (
    DeviceNotFoundError,
    DeviceAmbiguousError,
    DeviceIncompleteError,
)
from yyr4_linux_control.integration.preflight import IdentityPermissionChecker


@dataclass(frozen=True)
class IdentityPermissionValidationResult:
    """Structured result of identity and permission validation."""

    # Execution State
    result_status: int
    exit_code: int
    exception_class: Optional[str]
    identity_created: bool
    permission_checked: bool

    # Discovery Diagnostics
    enumerated_records: int
    matched_records: int
    complete_groups: int
    incomplete_groups: int
    ambiguous_groups: int
    rejected_vendor_product: int
    rejected_interface: int

    # Identity Desensitized Fields
    vendor_id: Optional[str]
    product_id: Optional[str]
    manufacturer: Optional[str]
    product: Optional[str]
    keyboard_present: bool
    mouse_present: bool
    keyboard_interface: Optional[str]
    mouse_interface: Optional[str]
    same_usb_parent: bool
    serial_present: bool
    keyboard_stable_path_available: bool
    keyboard_stable_path_kind: str
    mouse_stable_path_available: bool
    mouse_stable_path_kind: str

    # Permission Desensitized Fields
    keyboard_readable: bool
    mouse_readable: bool
    all_required_readable: bool
    blocker_count: int
    warning_count: int
    checked_role_count: int


def _get_stable_path_kind(stable_path: Optional[str]) -> str:
    if not stable_path:
        return "none"
    if "by-id" in stable_path:
        return "by-id"
    if "by-path" in stable_path:
        return "by-path"
    return "other"


def validate_identity_and_permissions(
    *,
    discovery_backend: DiscoveryBackend,
    permission_checker: IdentityPermissionChecker,
) -> IdentityPermissionValidationResult:
    """Validate YYR4 identity and check permissions of selected nodes."""

    # Default values for fields
    result_status = 8  # RUNTIME_OR_DEPENDENCY_FAILURE (default if something weird happens)
    exit_code = 8
    exception_class = None
    identity_created = False
    permission_checked = False

    # Diagnostics defaults
    enumerated = 0
    matched = 0
    complete = 0
    incomplete = 0
    ambiguous = 0
    rej_vp = 0
    rej_iface = 0

    # Identity defaults
    vendor_id = None
    product_id = None
    manufacturer = None
    product = None
    kbd_present = False
    ms_present = False
    kbd_iface = None
    ms_iface = None
    same_parent = False
    serial_present = False
    kbd_sp_avail = False
    kbd_sp_kind = "none"
    ms_sp_avail = False
    ms_sp_kind = "none"

    # Permission defaults
    kbd_read = False
    ms_read = False
    all_read = False
    blockers = 0
    warnings = 0
    checked_roles = 0

    try:
        discovery = YYR4DeviceDiscovery(discovery_backend)
        identity = discovery.select_single()
        diag = discovery.snapshot_diagnostics()

        # Populate diagnostics
        enumerated = diag.enumerated_records
        matched = diag.matched_records
        complete = diag.complete_groups
        incomplete = diag.incomplete_groups
        ambiguous = diag.ambiguous_groups
        rej_vp = diag.rejected_vendor_product
        rej_iface = diag.rejected_interface

        identity_created = True
        vendor_id = identity.vendor_id
        product_id = identity.product_id
        manufacturer = identity.manufacturer
        product = identity.product
        kbd_present = identity.keyboard is not None
        ms_present = identity.mouse is not None

        if kbd_present and ms_present:
            kbd_iface = identity.keyboard.usb_interface_number
            ms_iface = identity.mouse.usb_interface_number
            same_parent = identity.keyboard.parent_usb_syspath == identity.mouse.parent_usb_syspath
            kbd_sp_avail = identity.keyboard.stable_path is not None
            kbd_sp_kind = _get_stable_path_kind(identity.keyboard.stable_path)
            ms_sp_avail = identity.mouse.stable_path is not None
            ms_sp_kind = _get_stable_path_kind(identity.mouse.stable_path)

        serial_present = identity.serial_present

        # Identity contract check
        if not (vendor_id == "239a" and product_id == "80f4" and
                kbd_iface == "02" and ms_iface == "02" and same_parent):
            result_status = 7  # IDENTITY_CONTRACT_FAILURE
            exit_code = 7
        else:
            # Permissions check
            perm_result = permission_checker.check(identity)
            permission_checked = True
            kbd_read = perm_result.keyboard_readable
            ms_read = perm_result.mouse_readable
            all_read = perm_result.all_required_readable
            blockers = len(perm_result.blockers)
            warnings = len(perm_result.warnings)
            checked_roles = 2 if (kbd_present and ms_present) else 1

            if all_read:
                result_status = 0  # READY_FOR_TRANSPORT_PROFILE_EVENT_PROBE
                exit_code = 0
            else:
                result_status = 5  # PERMISSION_BLOCKED
                exit_code = 5

    except Exception as e:
        exception_class = e.__class__.__name__
        if isinstance(e, DeviceNotFoundError):
            result_status = 4
            exit_code = 4
        elif isinstance(e, (DeviceAmbiguousError, DeviceIncompleteError)):
            result_status = 6
            exit_code = 6
        else:
            result_status = 9  # DIAGNOSTIC_EXECUTION_ERROR
            exit_code = 9

        # Try to salvage diagnostics if discovery was created
        try:
            diag = discovery.snapshot_diagnostics()
            enumerated = diag.enumerated_records
            matched = diag.matched_records
            complete = diag.complete_groups
            incomplete = diag.incomplete_groups
            ambiguous = diag.ambiguous_groups
            rej_vp = diag.rejected_vendor_product
            rej_iface = diag.rejected_interface
        except Exception:
            pass

    return IdentityPermissionValidationResult(
        result_status=result_status,
        exit_code=exit_code,
        exception_class=exception_class,
        identity_created=identity_created,
        permission_checked=permission_checked,
        enumerated_records=enumerated,
        matched_records=matched,
        complete_groups=complete,
        incomplete_groups=incomplete,
        ambiguous_groups=ambiguous,
        rejected_vendor_product=rej_vp,
        rejected_interface=rej_iface,
        vendor_id=vendor_id,
        product_id=product_id,
        manufacturer=manufacturer,
        product=product,
        keyboard_present=kbd_present,
        mouse_present=ms_present,
        keyboard_interface=kbd_iface,
        mouse_interface=ms_iface,
        same_usb_parent=same_parent,
        serial_present=serial_present,
        keyboard_stable_path_available=kbd_sp_avail,
        keyboard_stable_path_kind=kbd_sp_kind,
        mouse_stable_path_available=ms_sp_avail,
        mouse_stable_path_kind=ms_sp_kind,
        keyboard_readable=kbd_read,
        mouse_readable=ms_read,
        all_required_readable=all_read,
        blocker_count=blockers,
        warning_count=warnings,
        checked_role_count=checked_roles,
    )
