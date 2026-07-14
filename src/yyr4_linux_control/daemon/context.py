import asyncio
from dataclasses import dataclass
from enum import Enum, auto

class ContextChangeSource(str, Enum):
    startup = "startup"
    control_action = "control_action"
    management_cli = "management_cli"
    config_reload = "config_reload"
    unchanged = "unchanged"

@dataclass(frozen=True)
class RuntimeContextSnapshot:
    selected_profile: str
    active_layer: str
    revision: int
    changed_at: float
    last_change_source: ContextChangeSource

from yyr4_linux_control.control.models import ProfileId, LayerId

class RuntimeContextManager:
    def __init__(self, default_profile: str | ProfileId, initial_layer: str | LayerId, clock=None):
        import time
        self._clock = clock or time
        self._selected_profile = ProfileId(default_profile) if isinstance(default_profile, str) else default_profile
        self._active_layer = LayerId(initial_layer) if isinstance(initial_layer, str) else initial_layer
        self._revision = 0
        self._changed_at = self._clock.monotonic()
        self._last_change_source = ContextChangeSource.startup
        self._lock = asyncio.Lock()
        
        # We need a reference to the config to validate target layers/profiles
        self._config = None

    def set_config(self, config):
        """Called by runtime on startup and reload"""
        self._config = config

    async def snapshot(self) -> RuntimeContextSnapshot:
        async with self._lock:
            return RuntimeContextSnapshot(
                selected_profile=self._selected_profile,
                active_layer=self._active_layer,
                revision=self._revision,
                changed_at=self._changed_at,
                last_change_source=self._last_change_source
            )

    async def set_layer(self, layer_id: str | LayerId, source: ContextChangeSource) -> bool:
        async with self._lock:
            lid = LayerId(layer_id) if isinstance(layer_id, str) else layer_id
            if self._active_layer == lid:
                return False
            
            self._active_layer = lid
            self._revision += 1
            self._changed_at = self._clock.monotonic()
            self._last_change_source = source
            return True

    async def next_layer(self, source: ContextChangeSource) -> bool:
        async with self._lock:
            if not self._config:
                return False
                
            profile_id = self._selected_profile
            # Only iterate through declared layers. "general" is always there implicitly,
            # but for next_layer we check explicit layers. Wait, requirement:
            # "general始终存在" -> The declared layers are general + explicitly defined.
            
            # Gather ordered available layers
            available = ["general"]
            if profile_id in self._config.profiles:
                for lid in ["layer_1", "layer_2", "layer_3", "layer_4", "layer_5", "layer_6", "layer_7", "layer_8"]:
                    if lid in self._config.profiles[profile_id].layers:
                        available.append(lid)
            
            if self._active_layer in available:
                idx = available.index(self._active_layer)
                next_idx = (idx + 1) % len(available)
            else:
                # If current layer is not in declared, next is after general
                if len(available) > 1:
                    next_idx = 1
                else:
                    next_idx = 0
                    
            next_layer_id = available[next_idx]
            
            if self._active_layer == next_layer_id:
                return False
                
            self._active_layer = next_layer_id
            self._revision += 1
            self._changed_at = self._clock.monotonic()
            self._last_change_source = source
            return True

    async def previous_layer(self, source: ContextChangeSource) -> bool:
        async with self._lock:
            if not self._config:
                return False
                
            profile_id = self._selected_profile
            
            available = [LayerId("general")]
            if profile_id in self._config.profiles:
                for lid in [LayerId("layer_1"), LayerId("layer_2"), LayerId("layer_3"), LayerId("layer_4"), LayerId("layer_5"), LayerId("layer_6"), LayerId("layer_7"), LayerId("layer_8")]:
                    if lid in self._config.profiles[profile_id].layers:
                        available.append(lid)
            
            if self._active_layer in available:
                idx = available.index(self._active_layer)
                prev_idx = (idx - 1) % len(available)
            else:
                prev_idx = len(available) - 1
                
            prev_layer_id = available[prev_idx]
            
            if self._active_layer == prev_layer_id:
                return False
                
            self._active_layer = prev_layer_id
            self._revision += 1
            self._changed_at = self._clock.monotonic()
            self._last_change_source = source
            return True

    async def set_profile(self, profile_id: str | ProfileId, source: ContextChangeSource) -> bool:
        async with self._lock:
            if not self._config:
                return False
            
            pid = ProfileId(profile_id) if isinstance(profile_id, str) else profile_id
            if pid not in self._config.profiles:
                raise ValueError(f"Profile {profile_id} does not exist in configuration")
                
            initial_layer = self._config.initial_layer
            
            if self._selected_profile == pid and self._active_layer == initial_layer:
                return False
                
            self._selected_profile = pid
            self._active_layer = initial_layer
            self._revision += 1
            self._changed_at = self._clock.monotonic()
            self._last_change_source = source
            return True

    async def reconcile_after_reload(self, new_config) -> bool:
        async with self._lock:
            self._config = new_config
            changed = False
            
            if self._selected_profile in new_config.profiles:
                # selected_profile still exists, check active_layer
                if self._active_layer not in new_config.profiles[self._selected_profile].layers and self._active_layer != new_config.initial_layer:
                    self._active_layer = new_config.initial_layer
                    changed = True
            else:
                self._selected_profile = new_config.default_profile
                self._active_layer = new_config.initial_layer
                changed = True
                
            if changed:
                self._revision += 1
                self._changed_at = self._clock.monotonic()
                self._last_change_source = ContextChangeSource.config_reload
                
            return changed
