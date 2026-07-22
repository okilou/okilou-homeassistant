"""Coordinateur : un cycle de polling (60 s) pour tout le foyer.

Chaque cycle relève /children, puis /today et /events par enfant. Les faits
nouveaux sont relayés sur le bus (okilou_event). Le curseur d'événements est
persisté : pas de rejeu au redémarrage, l'historique n'est jamais rejoué au
premier lancement.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .api import OkilouApiClient, OkilouAuthError, OkilouRateLimitError
from .const import BUS_EVENT, DOMAIN, STORAGE_VERSION, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class OkilouCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """data = {"children": {child_id: {"info": …, "today": …}}}"""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OkilouApiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self._store: Store[dict[str, str]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_cursors_{entry.entry_id}"
        )
        self._cursors: dict[str, str] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        if self._cursors is None:
            self._cursors = await self._store.async_load() or {}

        try:
            children = await self.client.children()
        except OkilouAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OkilouRateLimitError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # réseau, 5xx…
            raise UpdateFailed(str(err)) from err

        data: dict[str, Any] = {"children": {}}
        cursors_changed = False
        for child in children:
            child_id = child["id"]
            try:
                today = await self.client.today(child_id)
            except OkilouRateLimitError as err:
                raise UpdateFailed(str(err)) from err
            except OkilouAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:
                # 409 (pas encore de règles) ou raté ponctuel : l'enfant reste
                # listé, ses capteurs passent indisponibles.
                _LOGGER.warning("today(%s) : %s", child_id, err)
                today = None

            data["children"][child_id] = {"info": child, "today": today}

            # Premier passage : curseur posé à maintenant, pas de rejeu.
            since = self._cursors.get(child_id)
            if since is None:
                self._cursors[child_id] = dt_util.utcnow().isoformat()
                cursors_changed = True
                continue
            try:
                page = await self.client.events(child_id, since)
            except Exception as err:
                _LOGGER.warning("events(%s) : %s", child_id, err)
                continue
            for event in page.get("events", []):
                # L'API ne fournit que childId, le prénom vient de /children.
                self.hass.bus.async_fire(
                    BUS_EVENT, {**event, "childName": child.get("firstName")}
                )
            cursor = page.get("cursor")
            if cursor and cursor != since:
                self._cursors[child_id] = cursor
                cursors_changed = True

        # Un enfant retiré du foyer emporte son appareil HA et son curseur.
        # Balayage du registry plutôt qu'un diff en mémoire : couvre aussi un
        # retrait survenu pendant que HA était éteint.
        current = set(data["children"])
        dev_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            dev_reg, self.config_entry.entry_id
        ):
            child_ids = {ident[1] for ident in device.identifiers if ident[0] == DOMAIN}
            if child_ids and not (child_ids & current):
                dev_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )
        for child_id in [c for c in self._cursors if c not in current]:
            del self._cursors[child_id]
            cursors_changed = True

        if cursors_changed:
            await self._store.async_save(self._cursors)
        return data
