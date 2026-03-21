# Changelog

## 1.0.9

- Fix: Icon-Zuweisung für BM_-Melder – `icon` wird jetzt explizit im Discovery-Payload gesetzt (nicht via dict-Unpacking)
- Fix: BM_-Erkennung jetzt case-insensitiv (`bm_`, `BM_`, `Bm_` werden alle erkannt)
- Fix: Normale Melder erhalten explizit `mdi:motion-sensor` statt keinen Icon
- Debug-Log: `is_smoke`-Erkennung wird pro Melder geloggt zur Diagnose

## 1.0.8

- Neu: Melder mit Namen-Präfix `BM_` werden als Rauchmelder registriert (`device_class: smoke`, Icon `mdi:fire-circle`)
- Status-Sensor und Sperren-Switch bleiben für Rauchmelder unverändert (`mdi:shield-check`)

## 1.0.7

- Fix: Eckige Klammern in MAP-API-Namen werden automatisch entfernt (`[Ausgang AUX 1]` → `Ausgang AUX 1`)
- Fix: Translation-Map hat immer Vorrang vor dem API-Namen (nicht nur wenn API-Name leer ist)
- Fix: Fallback-Anzeige wenn kein Name vorhanden: letztes SIID-Segment statt vollem Pfad (`1.1.Area.2.2` statt `areas/1.1.Area.2.2`)

## 1.0.6

- Fix: MQTT `disconnect()` Reihenfolge korrigiert (disconnect vor loop_stop) – LWT feuerte fälschlicherweise bei jedem Reconnect und graut alle Entities aus
- Fix: `publish_availability(True)` wird jetzt bei jedem State-Refresh (alle 60s) erneut gesendet – Entities erholen sich automatisch nach verlorener Verbindung
- Fix: `publish_bridge_sensors()` wird beim State-Refresh mitveröffentlicht – MAP5000-Verbindungsentität überlebt HA-Neustarts zuverlässig
- Fix: Translation (SIID → Klarname) funktioniert jetzt zuverlässig – beide SIID-Formate werden geprüft (voller API-Pfad und nur numerischer Teil)
- Neu: `health_check_interval` Option (Standard: 30s) – Verbindungsprüfung zur MAP5000 ist jetzt konfigurierbar

## 1.0.4

- Neu: MapHealthMonitor – dauerhafter Ping zur MAP5000, publiziert `map/state/bridge/map_online` (retained)
- Neu: HA `binary_sensor` entity "MAP5000 Verbindung" (device_class: connectivity) via MQTT Discovery
- Web-UI: MAP-Verbindungsstatus-Indikator in der Kopfzeile (grün/rot Pill)
- Web-UI: Fehlerbanner wenn MAP5000 nicht erreichbar
- Web-UI: Übersetzungsdatei wird genutzt – Klarnamen statt SIIDs werden angezeigt
- Fix: paho-mqtt 2.x – `mqtt.Client(CallbackAPIVersion.VERSION1)`
- Fix: `AVAILABILITY_TOPIC` jetzt konfigurierbar aus `state_topic_base`
- Fix: EventWorker wird automatisch neu gestartet wenn er abstürzt
- Neu: `status_label` Feld für Melder (Frei / Ausgelöst / Gesperrt)
- Neu: HA `sensor` entity für Melderstatus
- Neu: Web-UI Dashboard (HA Ingress Port 8080) mit Bereichen, Meldern, Ausgängen

## 1.0.0

- Initial release as Home Assistant Addon
- MAP5000 REST-API event subscription and MQTT publishing
- MQTT command handling for areas, outputs and points
- Periodic state publishing with retained MQTT topics
- SIID to name translation via MAP XML config export
- Auto-reconnect for MQTT broker
