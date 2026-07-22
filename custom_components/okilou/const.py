"""Constantes de l'intégration Okilou."""

DOMAIN = "okilou"

CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"

# L'API publique v1 d'Okilou (lecture seule, jeton de foyer).
DEFAULT_BASE_URL = "https://api.okilou.com/functions/v1/api"

# L'app synchronise toutes les 4 s (push) / 60 s (pull) : en dessous de 60 s
# on ne verrait rien de plus, et le rate-limit du jeton est de 30 req/min.
UPDATE_INTERVAL_SECONDS = 60

# Événements relayés sur le bus HA (déclencheurs d'automatisations).
BUS_EVENT = "okilou_event"

STORAGE_VERSION = 1
