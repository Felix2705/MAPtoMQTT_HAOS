DOMAIN = "map5000"
CONF_BASE_URL = "base_url"
DEFAULT_BASE_URL = "http://localhost:8080"
UPDATE_INTERVAL_SECONDS = 10

PLATFORMS = ["alarm_control_panel", "binary_sensor", "sensor", "switch"]

DEVICE_INFO = {
    "identifiers": {(DOMAIN, "map5000_panel")},
    "name": "MAP5000",
    "manufacturer": "Bosch",
    "model": "MAP5000",
}
