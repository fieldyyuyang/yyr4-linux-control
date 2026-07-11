from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional
from ..domain.controls import PhysicalControl, ControlKind

@dataclass(frozen=True)
class TransportCode:
    primary_key: str
    required_modifiers: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def string_repr(self) -> str:
        if self.required_modifiers:
            return "+".join(self.required_modifiers) + "+" + self.primary_key
        return self.primary_key

class Codebook:
    def __init__(self, mappings: Dict[TransportCode, PhysicalControl]):
        self._mappings = dict(mappings)
        self._vendor_to_control: Dict[str, PhysicalControl] = {}
        self._id_to_control: Dict[str, PhysicalControl] = {}
        self._id_to_code: Dict[str, TransportCode] = {}
        self._code_to_control: Dict[str, PhysicalControl] = {}

        # Verify 24 items
        if len(self._mappings) != 24:
            raise ValueError(f"Codebook must have exactly 24 mappings, got {len(self._mappings)}")

        used_f_keys = set()

        for code, ctrl in self._mappings.items():
            if ctrl.control_id in self._id_to_control:
                raise ValueError(f"Duplicate control_id: {ctrl.control_id}")
            if ctrl.vendor_name in self._vendor_to_control:
                raise ValueError(f"Duplicate vendor_name: {ctrl.vendor_name}")
            if code.string_repr in self._code_to_control:
                raise ValueError(f"Duplicate transport code: {code.string_repr}")
            if not code.primary_key.startswith("KEY_F"):
                raise ValueError(f"Invalid primary key: {code.primary_key}")

            used_f_keys.add(code.primary_key)

            self._id_to_control[ctrl.control_id] = ctrl
            self._vendor_to_control[ctrl.vendor_name] = ctrl
            self._code_to_control[code.string_repr] = ctrl
            self._id_to_code[ctrl.control_id] = code

        # Verify F13-F24 completeness
        expected_f_keys = {f"KEY_F{i}" for i in range(13, 25)}
        if used_f_keys != expected_f_keys:
            raise ValueError("F13 to F24 must be completely utilized")

    def get_by_vendor_name(self, name: str) -> Optional[PhysicalControl]:
        return self._vendor_to_control.get(name)

    def get_by_control_id(self, control_id: str) -> Optional[PhysicalControl]:
        return self._id_to_control.get(control_id)

    def get_code_for_control_id(self, control_id: str) -> Optional[TransportCode]:
        return self._id_to_code.get(control_id)

    def get_by_transport_code(self, code: TransportCode) -> Optional[PhysicalControl]:
        return self._code_to_control.get(code.string_repr)

    def get_by_primary_key_and_modifiers(self, primary_key: str, modifiers: Tuple[str, ...]) -> Optional[PhysicalControl]:
        return self.get_by_transport_code(TransportCode(primary_key=primary_key, required_modifiers=modifiers))

def _build_default_codebook() -> Codebook:
    mappings = {}

    # 12 Buttons
    for i in range(1, 13):
        ctrl = PhysicalControl(
            control_id=f"button.k{i:02d}",
            vendor_name=f"A{i}",
            kind=ControlKind.BUTTON,
            button_index=i
        )
        code = TransportCode(primary_key=f"KEY_F{12+i}")
        mappings[code] = ctrl

    # Encoders
    encoders = [
        ("AL", "AP", "AR", 1, 13, 14, 15),
        ("BL", "BP", "BR", 2, 16, 17, 18),
        ("CL", "CP", "CR", 3, 19, 20, 21),
        ("DL", "DP", "DR", 4, 22, 23, 24),
    ]

    for l_name, p_name, r_name, idx, l_f, p_f, r_f in encoders:
        mod = ("KEY_LEFTSHIFT",)

        # CCW
        mappings[TransportCode(primary_key=f"KEY_F{l_f}", required_modifiers=mod)] = PhysicalControl(
            control_id=f"encoder.e{idx:02d}.counterclockwise",
            vendor_name=l_name,
            kind=ControlKind.ENCODER_COUNTERCLOCKWISE,
            encoder_index=idx
        )

        # Press
        mappings[TransportCode(primary_key=f"KEY_F{p_f}", required_modifiers=mod)] = PhysicalControl(
            control_id=f"encoder.e{idx:02d}.press",
            vendor_name=p_name,
            kind=ControlKind.ENCODER_PRESS,
            encoder_index=idx
        )

        # CW
        mappings[TransportCode(primary_key=f"KEY_F{r_f}", required_modifiers=mod)] = PhysicalControl(
            control_id=f"encoder.e{idx:02d}.clockwise",
            vendor_name=r_name,
            kind=ControlKind.ENCODER_CLOCKWISE,
            encoder_index=idx
        )

    return Codebook(mappings)

DEFAULT_CODEBOOK = _build_default_codebook()
