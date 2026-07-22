"""Binary sensors par enfant : session en cours, à la maison aujourd'hui."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OkilouCoordinator
from .entity import OkilouChildEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OkilouCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    @callback
    def _sync_children() -> None:
        new_entities: list[BinarySensorEntity] = []
        for child_id, child in coordinator.data["children"].items():
            if child_id in known:
                continue
            known.add(child_id)
            name = child["info"].get("firstName", "?")
            new_entities.extend(
                [
                    OkilouSessionSensor(coordinator, child_id, name),
                    OkilouMyDaySensor(coordinator, child_id, name),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    _sync_children()
    entry.async_on_unload(coordinator.async_add_listener(_sync_children))


class OkilouSessionSensor(OkilouChildEntity, BinarySensorEntity):
    """Session de récompense en cours (le compte à rebours de l'app)."""

    _attr_translation_key = "session"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_session"

    @property
    def is_on(self) -> bool | None:
        today = self._today
        if today is None:
            return None
        session = today.get("session")
        return bool(session and session.get("running"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = (self._today or {}).get("session") or {}
        # `ends_at` est connue dès le lancement : une automatisation peut se
        # programmer À L'AVANCE (lumière douce 5 min avant la fin, etc.).
        # `minutes` = cumul des lancements du jour (30 min puis +10 → 40).
        return {"ends_at": session.get("endsAt"), "minutes": session.get("minutes")}


class OkilouMyDaySensor(OkilouChildEntity, BinarySensorEntity):
    """Garde alternée : l'enfant est-il ici aujourd'hui ?

    Foyer unique ou règles communes : toujours on. En garde indépendante, le
    jour de l'autre maison passe off et les autres capteurs valent 0, sans
    aucune donnée de l'autre foyer.
    """

    _attr_translation_key = "my_day"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_my_day"

    @property
    def is_on(self) -> bool | None:
        today = self._today
        if today is None:
            return None
        return today.get("isMyDay") is not False
