"""Capteurs par enfant : minutes restantes, points du jour, série.

Le jour de l'autre foyer (garde alternée, isMyDay false), minutes et points
valent 0 ; l'état est porté par le binary_sensor dédié.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
        new_entities: list[SensorEntity] = []
        for child_id, child in coordinator.data["children"].items():
            if child_id in known:
                continue
            known.add(child_id)
            name = child["info"].get("firstName", "?")
            new_entities.extend(
                [
                    OkilouMinutesSensor(coordinator, child_id, name),
                    OkilouPointsSensor(coordinator, child_id, name),
                    OkilouStreakSensor(coordinator, child_id, name),
                    OkilouSessionEndSensor(coordinator, child_id, name),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    _sync_children()
    entry.async_on_unload(coordinator.async_add_listener(_sync_children))


class OkilouMinutesSensor(OkilouChildEntity, SensorEntity):
    """Minutes de récompense restantes aujourd'hui (la jauge de l'app)."""

    _attr_translation_key = "minutes_remaining"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_minutes_remaining"

    @property
    def native_value(self) -> int | None:
        today = self._today
        if today is None:
            return None
        return int(today.get("minutesRemaining", 0) or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = self._today or {}
        return {
            "minutes_unlocked": today.get("minutesUnlocked", 0),
            "minutes_consumed": today.get("minutesConsumed", 0),
            "consumable_today": today.get("consumableToday"),
            "period": today.get("period"),
            "frozen": today.get("frozen"),
            "joker": today.get("joker"),
            "next_tier": today.get("nextTier"),
        }


class OkilouPointsSensor(OkilouChildEntity, SensorEntity):
    """Points du jour (et le détail des comportements en attributs)."""

    _attr_translation_key = "points"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:star-circle-outline"

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_points"

    @property
    def native_value(self) -> int | None:
        today = self._today
        if today is None:
            return None
        return int(today.get("points", 0) or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = self._today or {}
        return {
            "max_points": today.get("maxPoints"),
            "mandatory_ok": today.get("mandatoryOk"),
            "perfect": today.get("perfect"),
            "behaviors": today.get("behaviors", []),
        }


class OkilouStreakSensor(OkilouChildEntity, SensorEntity):
    """Série de jours réussis (le Parcours de l'app)."""

    _attr_translation_key = "streak"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_streak"

    @property
    def native_value(self) -> int | None:
        today = self._today
        if today is None:
            return None
        return int(today.get("streakDays", 0) or 0)


class OkilouSessionEndSensor(OkilouChildEntity, SensorEntity):
    """Fin de la session en cours (HA affiche le compte à rebours).

    endsAt est connue dès le lancement. Hors session : inconnu.
    """

    _attr_translation_key = "session_end"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: OkilouCoordinator, child_id: str, name: str) -> None:
        super().__init__(coordinator, child_id, name)
        self._attr_unique_id = f"{child_id}_session_end"

    @property
    def native_value(self) -> datetime | None:
        session = (self._today or {}).get("session")
        if not session or not session.get("running") or not session.get("endsAt"):
            return None
        return dt_util.parse_datetime(session["endsAt"])
