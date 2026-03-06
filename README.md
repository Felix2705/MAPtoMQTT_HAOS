# MAP to MQTT - Home Assistant Addon Repository

Dieses Repository enthält das **MAP to MQTT** Home Assistant Addon.

## Installation

1. Navigiere in Home Assistant zu **Einstellungen → Add-ons → Add-on-Store**.
2. Klicke oben rechts auf das Drei-Punkte-Menü → **Repositories**.
3. Füge die URL dieses Repositories hinzu und klicke **Hinzufügen**.
4. Das Addon **MAP to MQTT** erscheint nun im Store. Klicke drauf → **Installieren**.
5. Konfiguriere die Optionen (MAP-IP, Zugangsdaten, MQTT-Broker) und starte das Addon.

## Enthaltene Addons

| Addon | Beschreibung |
|---|---|
| MAP to MQTT | Bridges Bosch MAP5000 REST-API Events zu MQTT und akzeptiert MQTT-Befehle |

## MQTT Topics

### Events (MAP → MQTT)
- `map/events/<EventTyp>` – Rohe MAP-Events als JSON

### Zustand (MAP → MQTT, retained)
- `map/state/areas/<SIID>` – Bereichsstatus
- `map/state/outputs/<SIID>` – Ausgangsstatus
- `map/state/points/<SIID>` – Melderstatus

### Befehle (MQTT → MAP)
- `map/cmd/area/<SIID>` – Bereichsbefehl (ARM, DISARM, …)
- `map/cmd/output/<SIID>` – Ausgangsbefehl (ON, OFF, ENABLE, DISABLE)
- `map/cmd/point/<SIID>` – Melderbefehl (ENABLE, DISABLE)
- `map/cmd/area/<SIID>/armed` – `true` / `false`
- `map/cmd/output/<SIID>/sperren` – `true` / `false`
- `map/cmd/point/<SIID>/sperren` – `true` / `false`
