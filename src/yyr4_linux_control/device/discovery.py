from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Sequence, Tuple, Optional, List, Dict
from typing import Protocol
from .identity import YYR4Identity, InputInterface, InterfaceRole
from .errors import DeviceNotFoundError, DeviceAmbiguousError, DeviceIncompleteError
import re

def _matches_canonical_descriptor(observed: str, canonical: str) -> bool:
    if observed == canonical:
        return True
    if observed == canonical.replace(" ", "_"):
        return True
    return False

@dataclass(frozen=True)
class UdevInputRecord:
    device_node: str
    syspath: str
    parent_usb_syspath: str
    properties: Mapping[str, str]
    devlinks: Tuple[str, ...]
    device_name: str

class DiscoveryBackend(Protocol):
    def enumerate_input_records(self) -> Sequence[UdevInputRecord]:
        ...

@dataclass(frozen=True)
class DiscoveryDiagnostics:
    enumerated_records: int
    matched_records: int
    complete_groups: int
    incomplete_groups: int
    rejected_vendor_product: int
    rejected_interface: int
    ambiguous_groups: int

class YYR4DeviceDiscovery:
    def __init__(self, backend: DiscoveryBackend):
        self.backend = backend
        self._diagnostics = DiscoveryDiagnostics(0, 0, 0, 0, 0, 0, 0)

    def discover_all(self) -> Tuple[YYR4Identity, ...]:
        records = self.backend.enumerate_input_records()
        
        enumerated = len(records)
        matched = 0
        rejected_vp = 0
        rejected_iface = 0
        incomplete = 0
        ambiguous = 0
        complete = 0
        
        # Group by parent USB syspath
        groups: Dict[str, List[UdevInputRecord]] = {}
        
        for rec in records:
            if rec.properties.get("ID_BUS") != "usb":
                continue
                
            vid = rec.properties.get("YYR4_NORMALIZED_VID", rec.properties.get("ID_VENDOR_ID", "")).lower()
            pid = rec.properties.get("YYR4_NORMALIZED_PID", rec.properties.get("ID_MODEL_ID", "")).lower()
            mfg = rec.properties.get("YYR4_NORMALIZED_MANUFACTURER", rec.properties.get("ID_VENDOR", ""))
            prod = rec.properties.get("YYR4_NORMALIZED_PRODUCT", rec.properties.get("ID_MODEL", ""))
            
            if vid != "239a" or pid != "80f4":
                rejected_vp += 1
                continue
                
            if not _matches_canonical_descriptor(mfg, "YOUYOU TEC."):
                rejected_vp += 1
                continue
                
            if not _matches_canonical_descriptor(prod, "YOUYOU Keyb_V2"):
                rejected_vp += 1
                continue
                
            if rec.properties.get("ID_USB_INTERFACE_NUM", "").zfill(2) != "02":
                rejected_iface += 1
                continue
                
            matched += 1
            groups.setdefault(rec.parent_usb_syspath, []).append(rec)
            
        identities = []
        
        for parent, group in groups.items():
            kb_rec: Optional[UdevInputRecord] = None
            ms_rec: Optional[UdevInputRecord] = None
            group_ambiguous = False
            
            for rec in group:
                is_kb = rec.properties.get("ID_INPUT_KEYBOARD") == "1"
                is_ms = rec.properties.get("ID_INPUT_MOUSE") == "1"
                
                # Check device name hints as extra safety
                if "Keyboard" in rec.device_name and is_kb:
                    if kb_rec is None:
                        kb_rec = rec
                    else:
                        ambiguous += 1
                        group_ambiguous = True
                elif "Mouse" in rec.device_name and is_ms:
                    if ms_rec is None:
                        ms_rec = rec
                    else:
                        ambiguous += 1
                        group_ambiguous = True

            if group_ambiguous:
                continue

            if not kb_rec or not ms_rec:
                incomplete += 1
                continue
                
            if kb_rec.device_node == ms_rec.device_node:
                ambiguous += 1
                continue
                
            def select_stable_path(links: Tuple[str, ...], expected_suffix: str) -> Optional[str]:
                for link in links:
                    if "by-id" in link and expected_suffix in link:
                        return link
                for link in links:
                    if "by-path" in link and expected_suffix in link:
                        return link
                # Fallback if no suffix is present but we know the role
                for link in links:
                    if "by-path" in link and "event" in link and "event-kbd" not in link and "event-mouse" not in link:
                        return link
                return None

            kb_iface = InputInterface(
                role=InterfaceRole.KEYBOARD,
                device_node=kb_rec.device_node,
                device_name=kb_rec.device_name,
                usb_interface_number=kb_rec.properties.get("ID_USB_INTERFACE_NUM", "02"),
                syspath=kb_rec.syspath,
                parent_usb_syspath=kb_rec.parent_usb_syspath,
                devlinks=kb_rec.devlinks,
                stable_path=select_stable_path(kb_rec.devlinks, "event-kbd")
            )
            
            ms_iface = InputInterface(
                role=InterfaceRole.MOUSE,
                device_node=ms_rec.device_node,
                device_name=ms_rec.device_name,
                usb_interface_number=ms_rec.properties.get("ID_USB_INTERFACE_NUM", "02"),
                syspath=ms_rec.syspath,
                parent_usb_syspath=ms_rec.parent_usb_syspath,
                devlinks=ms_rec.devlinks,
                stable_path=select_stable_path(ms_rec.devlinks, "event-mouse")
            )
            
            serial_present = "ID_SERIAL_SHORT" in kb_rec.properties
            hint = kb_rec.properties.get("ID_USB_INTERFACE_NUM", "") # A non-sensitive hint
            
            identities.append(YYR4Identity(
                vendor_id="239a",
                product_id="80f4",
                manufacturer="YOUYOU TEC.",
                product="YOUYOU Keyb_V2",
                usb_parent_syspath=parent,
                keyboard=kb_iface,
                mouse=ms_iface,
                serial_present=serial_present,
                local_identity_hint=hint
            ))
            complete += 1
            
        self._diagnostics = DiscoveryDiagnostics(
            enumerated_records=enumerated,
            matched_records=matched,
            complete_groups=complete,
            incomplete_groups=incomplete,
            rejected_vendor_product=rejected_vp,
            rejected_interface=rejected_iface,
            ambiguous_groups=ambiguous
        )
        
        return tuple(identities)

    def select_single(self) -> YYR4Identity:
        identities = self.discover_all()
        diag = self.snapshot_diagnostics()
        
        if len(identities) > 1 or diag.ambiguous_groups > 0:
            raise DeviceAmbiguousError(f"Ambiguity detected: {len(identities)} valid, {diag.ambiguous_groups} ambiguous, {diag.incomplete_groups} incomplete.")
            
        if diag.incomplete_groups > 0 and len(identities) == 0:
            raise DeviceIncompleteError(f"Found {diag.incomplete_groups} incomplete YYR4-like groups, but no complete devices.")
            
        if not identities:
            raise DeviceNotFoundError("No YYR4 devices found.")
            
        return identities[0]

    def snapshot_diagnostics(self) -> DiscoveryDiagnostics:
        return self._diagnostics
