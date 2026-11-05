"""Base commune : une entité par enfant, rattachée à un appareil « enfant »."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OkilouCoordinator


class OkilouChildEntity(CoordinatorEntity[OkilouCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, first_name: str) -> None:
        super().__init__(coordinator)
        self._child_id = child_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, child_id)},
            name=first_name,
            manufacturer="Okilou",
            model="Child profile",
            configuration_url="https://okilou.fr/api/?src=ha",
        )

    @property
    def _today(self) -> dict[str, Any] | None:
        child = self.coordinator.data["children"].get(self._child_id)
        return child.get("today") if child else None

    @property
    def available(self) -> bool:
        # Enfant retiré du foyer, ou règles pas encore synchronisées (409).
        return super().available and self._today is not None
