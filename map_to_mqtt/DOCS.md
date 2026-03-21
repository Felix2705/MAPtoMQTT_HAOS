# MAP to MQTT

Bridges die Bosch MAP5000 REST-API mit MQTT. Events vom MAP-System werden auf MQTT-Topics publiziert. MQTT-Befehle werden als REST-POST an den MAP-Controller gesendet.

## Konfiguration

| Option | Typ | Standard | Beschreibung |
|---|---|---|---|
| `map_base_url` | string | `https://169.254.10.10` | Basis-URL des MAP REST-API |
| `map_username` | string | – | MAP Benutzername |
| `map_password` | string | – | MAP Passwort |
| `map_verify_tls` | bool | `false` | TLS-Zertifikat validieren (deaktivieren bei selbst-signiertem Zertifikat) |
| `map_request_timeout` | int | `20` | HTTP-Timeout in Sekunden |
| `mqtt_host` | string | `core-mosquitto` | MQTT-Broker Hostname (HA Mosquitto Addon: `core-mosquitto`) |
| `mqtt_port` | int | `1883` | MQTT-Broker Port |
| `mqtt_username` | string | – | MQTT Benutzername (optional) |
| `mqtt_password` | string | – | MQTT Passwort (optional) |
| `mqtt_use_tls` | bool | `false` | TLS für MQTT verwenden |
| `event_topic_base` | string | `map/events` | Basis-Topic für MAP-Events |
| `cmd_topic_base` | string | `map/cmd` | Basis-Topic für Befehle |
| `state_topic_base` | string | `map/state` | Basis-Topic für Zustandsdaten (retained) |
| `poll_max_events` | int | `100` | Maximale Events pro Abfrage |
| `poll_min_events` | int | `1` | Minimale Events vor Rückgabe |
| `poll_max_time` | int | `50` | Maximale Wartezeit in Sekunden |
| `state_refresh_interval` | int | `60` | Interval für Zustandsaktualisierung in Sekunden |
| `translation_xml_path` | string | – | Pfad zu einer MAP XML-Konfigurationsdatei für SIID→Name Mapping (z.B. `/share/map_config.xml`) |

## MQTT Topics

### Events (Eingehend von MAP)
- `map/events/<EventTyp>` – JSON-Payload mit dem Event-Objekt

### Zustand (Periodisch aktualisiert, retained)
- `map/state/areas/<SIID>` – Bereichsstatus (armed, readyToArm, …)
- `map/state/areas/<SIID>/armed` – Einzelnes Feld als `{"value": true}`
- `map/state/outputs/<SIID>` – Ausgangsstatus (enabled, on, opState, …)
- `map/state/points/<SIID>` – Melderstatus (active, enabled, opState, …)

Wenn eine Übersetzungsdatei geladen ist, werden auch Topics mit dem Namen publiziert:
- `map/state/points/<Name>` – z.B. `map/state/points/Haustuer`

### Befehle (Senden an MAP)

**Bereiche:**
- `map/cmd/area/<SIID>` – Payload: `ARM`, `DISARM`, `STARTWALKTEST`, `STOPWALKTEST`, …
- `map/cmd/area/<SIID>/armed` – Payload: `true` / `false`

**Ausgänge:**
- `map/cmd/output/<SIID>` – Payload: `ON`, `OFF`, `ENABLE`, `DISABLE`
- `map/cmd/output/<SIID>/sperren` – Payload: `true` / `false`
- `map/cmd/output/<SIID>/on` – Payload: `true` / `false`

**Melder:**
- `map/cmd/point/<SIID>` – Payload: `ENABLE`, `DISABLE`
- `map/cmd/point/<SIID>/sperren` – Payload: `true` / `false`

Payloads können auch als JSON gesendet werden:
- `{"cmd": "ARM"}` oder `{"value": "true"}`

## Übersetzungsdatei (SIID → Name)

Eine MAP XML-Konfigurationsdatei kann in den HA `/share/` Ordner hochgeladen werden und dann als Pfad angegeben werden:

```
translation_xml_path: /share/map_config.xml
```

Dies ermöglicht das Verwenden von Klarnamen statt SIIDs in Topics:
- `map/cmd/point/Haustuer/sperren` → aktiviert/deaktiviert den Melder "Haustür"

## Beispiel Home Assistant Automation

```yaml
alias: Alarm scharf schalten
trigger:
  - platform: state
    entity_id: input_boolean.alarm_aktiviert
    to: "on"
action:
  - service: mqtt.publish
    data:
      topic: map/cmd/area/1.1.Area.1/armed
      payload: "true"
```

## Logs

Logs sind im HA Addon-Log-Bereich sichtbar. Bei Problemen:
1. MAP Base URL und Zugangsdaten prüfen
2. MQTT Broker Host/Port prüfen (bei HA Mosquitto Addon: `core-mosquitto`, Port `1883`)
3. TLS deaktivieren wenn kein gültiges Zertifikat vorhanden
