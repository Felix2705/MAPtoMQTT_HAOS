"""
MAP to MQTT - Home Assistant Addon
Headless service that bridges Bosch MAP5000 REST-API to MQTT.
Configuration is read from /data/options.json (HA addon options).
"""

import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .bridge import BridgeController
from .map_client import MapClient
from .mapping import CommandParser, MapEventMapper
from .mqtt_client import MqttService
from .translation import load_translation_map, normalize_siid, topicize_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

OPTIONS_PATH = Path("/data/options.json")


def load_options() -> dict:
    with OPTIONS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class StatePusher:
    """Periodically fetches MAP state and publishes to MQTT (retained)."""

    def __init__(
        self,
        map_client: MapClient,
        mqtt: MqttService,
        opts: dict,
        translation_map: dict,
        translation_name_map: dict,
    ) -> None:
        self._map = map_client
        self._mqtt = mqtt
        self._opts = opts
        self._translation_map = translation_map
        self._translation_name_map = translation_name_map
        self._interval: int = max(10, int(opts.get("state_refresh_interval", 60)))
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="StatePusher")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        # Initial push right after startup (with short delay for MQTT to connect)
        time.sleep(3)
        while self._running:
            try:
                self._refresh()
            except Exception:
                logger.exception("State refresh error")
            # Sleep in small increments so stop() is responsive
            deadline = time.monotonic() + self._interval
            while self._running and time.monotonic() < deadline:
                time.sleep(1)

    def _refresh(self) -> None:
        logger.info("Refreshing MAP state")
        self._publish_category("areas", self._map.get_areas())
        self._publish_category("outputs", self._map.get_outputs())
        self._publish_category("points", self._map.get_points())

    def _publish_category(self, category: str, data: dict) -> None:
        items = data.get("list", [])
        state_base = self._opts.get("state_topic_base", "map/state").strip("/")
        cmd_base = self._opts.get("cmd_topic_base", "map/cmd").strip("/")

        for item in items:
            if not isinstance(item, dict):
                continue
            siid = str(item.get("@self", "")).lstrip("/")
            if not siid:
                continue

            lookup_siid = normalize_siid(siid)
            payload: Dict[str, Any] = item
            entry = self._translation_map.get(lookup_siid)
            name_segment = ""

            if entry and "name" not in item:
                payload = dict(item)
                payload["name"] = entry.get("name", "")

            if category in {"points", "outputs"} and "enabled" in payload and "sperren" not in payload:
                if payload is item:
                    payload = dict(item)
                payload["sperren"] = bool(payload.get("enabled"))

            if entry:
                name_segment = topicize_name(entry.get("name", ""))

            base_topic = f"{state_base}/{category}/{siid}"
            self._publish_item(base_topic, payload)
            if name_segment:
                self._publish_item(f"{state_base}/{category}/{name_segment}", payload)

            if category in {"points", "outputs"}:
                sperren_value = payload.get("sperren")
                if sperren_value is not None:
                    resource = "point" if category == "points" else "output"
                    self._publish_cmd_hint(cmd_base, resource, "sperren", sperren_value, siid, name_segment)

    def _publish_item(self, base_topic: str, payload: dict) -> None:
        self._mqtt.publish(base_topic, payload, retain=True)
        for key, value in payload.items():
            if key == "@self":
                continue
            self._mqtt.publish(f"{base_topic}/{key}", {"value": value}, retain=True)

    def _publish_cmd_hint(
        self, cmd_base: str, resource: str, key: str, value: Any, siid: str, alias: str = ""
    ) -> None:
        p = {"value": value, "source": "bridge"}
        self._mqtt.publish(f"{cmd_base}/{resource}/{siid}/{key}", p, retain=True)
        if alias:
            self._mqtt.publish(f"{cmd_base}/{resource}/{alias}/{key}", p, retain=True)


def _build_map_client(opts: dict) -> MapClient:
    return MapClient(
        base_url=opts["map_base_url"],
        username=opts["map_username"],
        password=opts["map_password"],
        verify_tls=bool(opts.get("map_verify_tls", False)),
        timeout_sec=int(opts.get("map_request_timeout", 20)),
    )


def _build_sub_payload(opts: dict) -> dict:
    return {
        "@cmd": "SUBSCRIBE",
        "leaseTime": 600,
        "bufferSize": 100,
        "subscriptions": [
            {
                "urls": ["/areas", "/outputs", "/points", "/inc", "/history"],
                "eventType": ["CHANGED", "CREATED", "DELETED"],
            }
        ],
    }


def _build_fetch_payload(opts: dict) -> dict:
    return {
        "@cmd": "FETCHEVENTS",
        "maxEvents": int(opts.get("poll_max_events", 100)),
        "minEvents": int(opts.get("poll_min_events", 1)),
        "maxTime": int(opts.get("poll_max_time", 50)),
    }


def main() -> None:
    logger.info("MAP to MQTT Addon starting")

    opts = load_options()
    logger.info("Options loaded: map_base_url=%s mqtt_host=%s:%s",
                opts.get("map_base_url"), opts.get("mqtt_host"), opts.get("mqtt_port"))

    # Load optional translation XML
    translation_map: dict = {}
    translation_name_map: dict = {}
    xml_path = opts.get("translation_xml_path", "").strip()
    if xml_path:
        translation_map = load_translation_map(xml_path)
        for siid, entry in translation_map.items():
            name_seg = topicize_name(entry.get("name", ""))
            if name_seg:
                translation_name_map[name_seg] = normalize_siid(siid)
        logger.info("Translation loaded: %d entries from %s", len(translation_map), xml_path)

    # MQTT
    mqtt = MqttService()
    cmd_base = opts.get("cmd_topic_base", "map/cmd").strip("/")

    def connect_mqtt() -> bool:
        try:
            mqtt.connect(
                host=opts["mqtt_host"],
                port=int(opts.get("mqtt_port", 1883)),
                username=opts.get("mqtt_username", ""),
                password=opts.get("mqtt_password", ""),
                use_tls=bool(opts.get("mqtt_use_tls", False)),
            )
            # Give paho time to complete the connection
            time.sleep(1)
            mqtt.subscribe(f"{cmd_base}/area/#")
            mqtt.subscribe(f"{cmd_base}/output/#")
            mqtt.subscribe(f"{cmd_base}/point/#")
            logger.info("MQTT connected to %s:%s", opts["mqtt_host"], opts.get("mqtt_port", 1883))
            return True
        except Exception:
            logger.exception("MQTT connect failed")
            return False

    # MAP client
    map_client = _build_map_client(opts)

    # Bridge
    mapper = MapEventMapper(opts.get("event_topic_base", "map/events"), translation_map)
    cmd_parser = CommandParser(cmd_base, translation_map, translation_name_map)
    bridge = BridgeController()
    bridge.setup(map_client, mqtt, mapper, cmd_parser)

    # State pusher
    state_pusher = StatePusher(map_client, mqtt, opts, translation_map, translation_name_map)

    # Graceful shutdown
    stop_event = threading.Event()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Main loop with auto-reconnect
    connected = False
    bridge_started = False

    while not stop_event.is_set():
        if not connected:
            logger.info("Connecting to MQTT broker …")
            connected = connect_mqtt()
            if not connected:
                logger.warning("MQTT connection failed, retrying in 15s")
                stop_event.wait(timeout=15)
                continue

        if not bridge_started:
            logger.info("Starting MAP event bridge …")
            bridge.start_events(_build_sub_payload(opts), _build_fetch_payload(opts))
            state_pusher.start()
            bridge_started = True

        stop_event.wait(timeout=5)

        # Check if MQTT is still alive; reconnect if needed
        if bridge_started and not mqtt.connected:
            logger.warning("MQTT connection lost, reconnecting …")
            connected = False
            bridge_started = False
            bridge.stop_events()
            state_pusher.stop()
            mqtt.disconnect()
            time.sleep(5)

    logger.info("Shutting down …")
    bridge.stop_events()
    state_pusher.stop()
    mqtt.disconnect()
    logger.info("MAP to MQTT Addon stopped")


if __name__ == "__main__":
    main()
