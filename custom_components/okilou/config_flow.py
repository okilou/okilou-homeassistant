"""Config flow : URL de l'API (pré-remplie) + jeton rf_api_… du foyer.

Le jeton se crée dans l'app Okilou : Réglages → Ton foyer → API & domotique.
Il couvre tout le foyer (tous les enfants), en lecture seule, révocable à tout
moment depuis l'app.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OkilouApiClient, OkilouAuthError, OkilouApiError
from .const import CONF_BASE_URL, CONF_TOKEN, DEFAULT_BASE_URL, DOMAIN


class OkilouConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Jeton révoqué dans l'app : demander le nouveau (l'URL ne bouge pas)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            client = OkilouApiClient(
                async_get_clientsession(self.hass), entry.data[CONF_BASE_URL], token
            )
            try:
                await client.children()
            except OkilouAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].strip()
            token = user_input[CONF_TOKEN].strip()

            # Un même jeton = une même entrée (le hash évite de stocker le
            # jeton en identifiant unique).
            await self.async_set_unique_id(hashlib.sha256(token.encode()).hexdigest()[:16])
            self._abort_if_unique_id_configured()

            client = OkilouApiClient(async_get_clientsession(self.hass), base_url, token)
            try:
                children = await client.children()
            except OkilouAuthError:
                errors["base"] = "invalid_auth"
            except OkilouApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # réseau, DNS…
                errors["base"] = "cannot_connect"
            else:
                names = ", ".join(c.get("firstName", "?") for c in children) or "foyer"
                return self.async_create_entry(
                    title=f"Okilou ({names})",
                    data={CONF_BASE_URL: base_url, CONF_TOKEN: token},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
