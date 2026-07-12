from __future__ import annotations
import os
import re
from typing import Sequence, Optional
from .discovery import DiscoveryBackend, UdevInputRecord
from .errors import DependencyUnavailableError

def _truncate_nul_text(value: str) -> str:
    return value.split("\x00", 1)[0].strip()

def _decode_sysfs_bytes(value: bytes) -> str | None:
    prefix = value.split(b"\x00", 1)[0]
    try:
        return prefix.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None

def _decode_udev_encoded_text(encoded: str) -> str | None:
    """Safely decode udev \x20 style hex escapes."""
    result = bytearray()
    i = 0
    n = len(encoded)
    while i < n:
        if encoded[i] == '\\':
            if i + 3 < n and encoded[i+1] == 'x':
                hex_str = encoded[i+2:i+4]
                try:
                    result.append(int(hex_str, 16))
                    i += 4
                    continue
                except ValueError:
                    return None
            else:
                return None
        else:
            result.append(ord(encoded[i]))
            i += 1

    return _decode_sysfs_bytes(bytes(result))

def _read_usb_descriptor(parent, sysfs_key: str, udev_enc_key: str, udev_fallback_key: str, properties_dict: dict) -> str:
    # 1. First priority: sysfs
    val = parent.attributes.get(sysfs_key)
    if val is not None:
        if isinstance(val, bytes):
            val_str = _decode_sysfs_bytes(val)
        else:
            val_str = _truncate_nul_text(str(val))
        if val_str:
            return val_str

    # 2. Second priority: ID_*_ENC
    enc_val = properties_dict.get(udev_enc_key)
    if enc_val:
        dec_val = _decode_udev_encoded_text(enc_val)
        if dec_val:
            return dec_val

    # 3. Third priority: normal ID_* fallback
    fallback = _truncate_nul_text(properties_dict.get(udev_fallback_key, ""))
    return fallback

class LinuxUdevDiscoveryBackend(DiscoveryBackend):
    def __init__(self) -> None:
        try:
            import pyudev
            self._pyudev = pyudev
        except ImportError as e:
            raise DependencyUnavailableError("pyudev is not installed. Install with 'pip install yyr4-linux-control[linux-input]'") from e

    def enumerate_input_records(self) -> Sequence[UdevInputRecord]:
        context = self._pyudev.Context()
        records = []

        # Only enumerate input subsystem
        for device in context.list_devices(subsystem="input"):
            device_node = device.device_node
            if not device_node or "event" not in device_node:
                continue

            # Find parent USB device for syspath correlation
            parent = device.find_parent("usb", "usb_device")
            if not parent:
                continue

            props_dict = {k: str(v) for k, v in device.properties.items()}

            mfg = _read_usb_descriptor(parent, "manufacturer", "ID_VENDOR_ENC", "ID_VENDOR", props_dict)
            prod = _read_usb_descriptor(parent, "product", "ID_MODEL_ENC", "ID_MODEL", props_dict)

            # Prioritize parent sysfs for VID/PID
            sysfs_vid = parent.attributes.get("idVendor")
            if sysfs_vid is not None:
                if isinstance(sysfs_vid, bytes):
                    vid = _decode_sysfs_bytes(sysfs_vid)
                else:
                    vid = _truncate_nul_text(str(sysfs_vid))
            else:
                vid = props_dict.get("ID_VENDOR_ID", "")

            sysfs_pid = parent.attributes.get("idProduct")
            if sysfs_pid is not None:
                if isinstance(sysfs_pid, bytes):
                    pid = _decode_sysfs_bytes(sysfs_pid)
                else:
                    pid = _truncate_nul_text(str(sysfs_pid))
            else:
                pid = props_dict.get("ID_MODEL_ID", "")

            props_dict["YYR4_NORMALIZED_MANUFACTURER"] = mfg
            props_dict["YYR4_NORMALIZED_PRODUCT"] = prod

            if vid:
                props_dict["YYR4_NORMALIZED_VID"] = vid
            if pid:
                props_dict["YYR4_NORMALIZED_PID"] = pid

            import types
            properties = types.MappingProxyType(props_dict)

            # Access permission check without opening

            records.append(UdevInputRecord(
                device_node=device_node,
                syspath=device.sys_path,
                parent_usb_syspath=parent.sys_path,
                properties=properties,
                devlinks=tuple(link for link in device.device_links),
                device_name=device.properties.get("NAME", "").strip('"'),
            ))

        return records
