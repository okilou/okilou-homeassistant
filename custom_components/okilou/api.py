"""Client de l'API publique Okilou v1 (lecture seule, jeton de foyer)."""

from __future__ import annotations

import re
from typing import Any

import aiohttp

UUID_RE = re.compile(r"^[0-9a-f-]{36}$", re.IGNORECASE)


class OkilouApiError(Exception):
    """Erreur générique de l'API Okilou."""


class OkilouAuthError(OkilouApiError):
    """Jeton manquant, inconnu ou révoqué (401)."""


class OkilouRateLimitError(OkilouApiError):
    """Rate-limit du jeton atteint (429, max 30 req/min)."""


class OkilouApiClient:
    """Enveloppe fine autour des 3 routes de l'API v1."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with self._session.get(
            url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 401:
                raise OkilouAuthError("jeton inconnu ou révoqué")
            if resp.status == 429:
                raise OkilouRateLimitError("trop de requêtes (max 30/min)")
            if resp.status >= 400:
                body = await resp.text()
                raise OkilouApiError(f"HTTP {resp.status} sur {path} : {body[:200]}")
            return await resp.json()

    @staticmethod
    def _check_id(child_id: str) -> str:
        if not UUID_RE.match(child_id):
            raise OkilouApiError(f"identifiant enfant invalide : {child_id!r}")
        return child_id

    async def children(self) -> list[dict[str, Any]]:
        """Les enfants couverts par le jeton : [{id, firstName}]."""
        return await self._get("/children")

    async def today(self, child_id: str) -> dict[str, Any]:
        """L'état du jour, ou {date, isMyDay: false} le jour de l'autre foyer."""
        return await self._get(f"/children/{self._check_id(child_id)}/today")

    async def events(self, child_id: str, since: str | None) -> dict[str, Any]:
        """Page de faits du journal : {events, cursor}."""
        params = {"since": since} if since else None
        return await self._get(f"/children/{self._check_id(child_id)}/events", params=params)
