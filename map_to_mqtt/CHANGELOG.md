# Changelog

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
