from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple

class InterfaceRole(Enum):
    KEYBOARD = auto()
    MOUSE = auto()

@dataclass(frozen=True)
class InputInterface:
    role: InterfaceRole
    device_node: str
    device_name: str
    usb_interface_number: str
    syspath: str
    parent_usb_syspath: str
    devlinks: Tuple[str, ...] = field(default_factory=tuple)
    stable_path: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.device_node:
            raise ValueError("device_node cannot be empty")
        if not self.syspath:
            raise ValueError("syspath cannot be empty")
        if not self.parent_usb_syspath:
            raise ValueError("parent_usb_syspath cannot be empty")
        
        # Normalize usb_interface_number to 2 chars (e.g. '02')
        if not self.usb_interface_number:
            raise ValueError("usb_interface_number cannot be empty")
        
        object.__setattr__(self, 'usb_interface_number', self.usb_interface_number.zfill(2))

@dataclass(frozen=True)
class YYR4Identity:
    vendor_id: str
    product_id: str
    manufacturer: str
    product: str
    usb_parent_syspath: str
    keyboard: InputInterface
    mouse: InputInterface
    serial_present: bool
    local_identity_hint: Optional[str] = None

    def __post_init__(self) -> None:
        # Normalize VID/PID to lowercase
        vid = self.vendor_id.lower()
        pid = self.product_id.lower()
        if not (len(vid) == 4 and all(c in "0123456789abcdef" for c in vid)):
            raise ValueError(f"Invalid vendor_id: {vid}")
        if not (len(pid) == 4 and all(c in "0123456789abcdef" for c in pid)):
            raise ValueError(f"Invalid product_id: {pid}")
            
        object.__setattr__(self, 'vendor_id', vid)
        object.__setattr__(self, 'product_id', pid)
        
        if not self.manufacturer:
            raise ValueError("manufacturer cannot be empty")
        if not self.product:
            raise ValueError("product cannot be empty")
            
        if self.keyboard.parent_usb_syspath != self.usb_parent_syspath:
            raise ValueError("Keyboard must share the parent_usb_syspath")
        if self.mouse.parent_usb_syspath != self.usb_parent_syspath:
            raise ValueError("Mouse must share the parent_usb_syspath")
            
        if self.keyboard.usb_interface_number != "02":
            raise ValueError("Keyboard must be on interface 02")
        if self.mouse.usb_interface_number != "02":
            raise ValueError("Mouse must be on interface 02")
            
        if self.keyboard.role == self.mouse.role:
            raise ValueError("Keyboard and mouse cannot have the same role")
            
        if self.keyboard.device_node == self.mouse.device_node:
            raise ValueError("Keyboard and mouse cannot have the same device_node")
            
        if self.keyboard.syspath == self.mouse.syspath:
            raise ValueError("Keyboard and mouse cannot have the same syspath")
