from __future__ import annotations
import os
from typing import Sequence, Optional
from .discovery import DiscoveryBackend, UdevInputRecord
from .errors import DependencyUnavailableError

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
                
            import types
            properties = types.MappingProxyType({k: str(v) for k, v in device.properties.items()})
            
            # Access permission check without opening
            readable = os.access(device_node, os.R_OK) if os.path.exists(device_node) else False
            
            records.append(UdevInputRecord(
                device_node=device_node,
                syspath=device.sys_path,
                parent_usb_syspath=parent.sys_path,
                properties=properties,
                devlinks=tuple(link for link in device.device_links),
                device_name=device.properties.get("NAME", "").strip('"'),
                readable=readable
            ))
            
        return records
