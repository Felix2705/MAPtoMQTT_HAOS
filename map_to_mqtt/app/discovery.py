"""
MQTT Discovery – publishes Home Assistant auto-discovery messages
so that MAP areas, points and outputs appear as real HA entities.
"""

import logging

logger = logging.getLogger(__name__)

AVAILABILITY_TOPIC = "map/bridge/availability"
_MANUFACTURER = "Bosch"
_MODEL = "MAP5000"
_PANEL_ID = "map5000_panel"
_PANEL_NAME = "MAP5000"


def _device() -> dict:
    return {
        "identifiers": [_PANEL_ID],
        "name": _PANEL_NAME,
        "manufacturer": _MANUFACTURER,
        "model": _MODEL,
    }


def _slug(siid: str) -> str:
    return siid.replace(".", "_").replace("/", "_").strip("_")


class MqttDiscovery:
    def __init__(self, mqtt, state_base: str, cmd_base: str, discovery_prefix: str = "homeassistant") -> None:
        self._mqtt = mqtt
        self._state_base = state_base.strip("/")
        self._cmd_base = cmd_base.strip("/")
        self._prefix = discovery_prefix.strip("/")

    def publish_availability(self, online: bool) -> None:
        self._mqtt.publish_raw(AVAILABILITY_TOPIC, "online" if online else "offline", retain=True)

    def publish_all(self, areas: list, points: list, outputs: list) -> None:
        for item in areas:
            siid = str(item.get("@self", "")).lstrip("/")
            if siid:
                self._publish_area(siid, item.get("name", siid))

        for item in points:
            siid = str(item.get("@self", "")).lstrip("/")
            if siid:
                self._publish_point(siid, item.get("name", siid))

        for item in outputs:
            siid = str(item.get("@self", "")).lstrip("/")
            if siid:
                self._publish_output(siid, item.get("name", siid))

        logger.info(
            "MQTT Discovery published: %d areas, %d points, %d outputs",
            len(areas), len(points), len(outputs),
        )

    def _base(self, component: str, uid: str) -> str:
        return f"{self._prefix}/{component}/{uid}/config"

    def _publish_area(self, siid: str, name: str) -> None:
        uid = f"map_area_{_slug(siid)}"
        state_topic = f"{self._state_base}/areas/{siid}"
        config = {
            "name": name,
            "unique_id": uid,
            "state_topic": state_topic,
            "value_template": "{{ 'armed_away' if value_json.armed else 'disarmed' }}",
            "command_topic": f"{self._cmd_base}/area/{siid}/armed",
            "payload_arm_away": "true",
            "payload_arm_home": "true",
            "payload_arm_night": "true",
            "payload_disarm": "false",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": _device(),
        }
        self._mqtt.publish(self._base("alarm_control_panel", uid), config, retain=True)

    def _publish_point(self, siid: str, name: str) -> None:
        slug = _slug(siid)
        state_topic = f"{self._state_base}/points/{siid}"

        # binary_sensor: Eingeschaltet (aktiv / nicht aktiv)
        bs_uid = f"map_point_{slug}"
        self._mqtt.publish(self._base("binary_sensor", bs_uid), {
            "name": f"{name} (Eingeschaltet)",
            "unique_id": bs_uid,
            "state_topic": state_topic,
            "value_template": "{{ 'ON' if value_json.active else 'OFF' }}",
            "device_class": "motion",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": _device(),
        }, retain=True)

        # switch: Gesperrt (sperren / entsperren)
        sw_uid = f"map_point_{slug}_enabled"
        self._mqtt.publish(self._base("switch", sw_uid), {
            "name": f"{name} (Gesperrt)",
            "unique_id": sw_uid,
            "state_topic": f"{state_topic}/sperren",
            "value_template": "{{ 'ON' if value_json.value else 'OFF' }}",
            "command_topic": f"{self._cmd_base}/point/{siid}/sperren",
            "payload_on": "true",
            "payload_off": "false",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": _device(),
        }, retain=True)

    def _publish_output(self, siid: str, name: str) -> None:
        slug = _slug(siid)
        state_topic = f"{self._state_base}/outputs/{siid}"

        # switch: ein / aus
        on_uid = f"map_output_{slug}"
        self._mqtt.publish(self._base("switch", on_uid), {
            "name": name,
            "unique_id": on_uid,
            "state_topic": state_topic,
            "value_template": "{{ 'ON' if value_json.on else 'OFF' }}",
            "command_topic": f"{self._cmd_base}/output/{siid}/on",
            "payload_on": "true",
            "payload_off": "false",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": _device(),
        }, retain=True)

        # switch: sperren / entsperren
        en_uid = f"map_output_{slug}_enabled"
        self._mqtt.publish(self._base("switch", en_uid), {
            "name": f"{name} (Aktiv)",
            "unique_id": en_uid,
            "state_topic": f"{state_topic}/sperren",
            "value_template": "{{ 'ON' if value_json.value else 'OFF' }}",
            "command_topic": f"{self._cmd_base}/output/{siid}/sperren",
            "payload_on": "true",
            "payload_off": "false",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": _device(),
        }, retain=True)
