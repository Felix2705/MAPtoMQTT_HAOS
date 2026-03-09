"""
MAP to MQTT - Home Assistant Addon
Headless service that bridges Bosch MAP5000 REST-API to MQTT.
MAP devices are registered as real HA entities via MQTT Discovery.
Configuration is read from /data/options.json (HA addon options).
"""

import json
import logging
import signal
import sys
import threading
import time
import urllib3
from pathlib import Path
from typing import Any, Dict, List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .bridge import BridgeController
from .discovery import MqttDiscovery
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


def _enrich(items: list, translation_map: dict) -> list:
    """Add 'name' field from translation map to each item."""
    result = []
    for item in items:
        siid = normalize_siid(str(item.get("@self", "")).lstrip("/"))
        entry = translation_map.get(siid)
        if entry and "name" not in item:
            item = dict(item)
            item["name"] = entry.get("name", "")
        result.append(item)
    return result


class StatePusher:
    """Periodically fetches MAP state and publishes to MQTT (retained).
    These retained topics feed the HA entity states defined by MQTT Discovery."""

    def __init__(
        self,
        map_client: MapClient,
        mqtt: MqttService,
        discovery: MqttDiscovery,
        opts: dict,
        translation_map: dict,
    ) -> None:
        self._map = map_client
        self._mqtt = mqtt
        self._discovery = discovery
        self._opts = opts
        self._translation_map = translation_map
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
        time.sleep(2)
        while self._running:
            try:
                self._refresh()
            except Exception:
                logger.exception("State refresh error")
            deadline = time.monotonic() + self._interval
            while self._running and time.monotonic() < deadline:
                time.sleep(1)

    def _refresh(self) -> None:
        logger.info("Refreshing MAP state")
        areas = _enrich(self._map.get_areas().get("list", []), self._translation_map)
        outputs = _enrich(self._map.get_outputs().get("list", []), self._translation_map)
        points = _enrich(self._map.get_points().get("list", []), self._translation_map)

        # Republish discovery so HA entities survive a HA restart
        self._discovery.publish_all(areas, points, outputs)

        self._publish_category("areas", areas)
        self._publish_category("outputs", outputs)
        self._publish_category("points", points)

    def _publish_category(self, category: str, items: List[dict]) -> None:
        state_base = self._opts.get("state_topic_base", "map/state").strip("/")

        for item in items:
            if not isinstance(item, dict):
                continue
            siid = str(item.get("@self", "")).lstrip("/")
            if not siid:
                continue

            payload: Dict[str, Any] = item
            if category in {"points", "outputs"} and "enabled" in payload and "sperren" not in payload:
                payload = dict(item)
                # enabled=True means "in Betrieb" (not locked), so sperren = not enabled
                payload["sperren"] = not bool(payload.get("enabled"))

            base_topic = f"{state_base}/{category}/{siid}"
            self._publish_item(base_topic, payload)

    def _publish_item(self, base_topic: str, payload: dict) -> None:
        self._mqtt.publish(base_topic, payload, retain=True)
        for key, value in payload.items():
            if key == "@self":
                continue
            self._mqtt.publish(f"{base_topic}/{key}", {"value": value}, retain=True)


def _build_map_client(opts: dict) -> MapClient:
    return MapClient(
        base_url=opts["map_base_url"],
        username=opts["map_username"],
        password=opts["map_password"],
        verify_tls=bool(opts.get("map_verify_tls", False)),
        timeout_sec=int(opts.get("map_request_timeout", 20)),
    )


def _build_sub_payload() -> dict:
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
    logger.info("Options: map=%s  mqtt=%s:%s",
                opts.get("map_base_url"), opts.get("mqtt_host"), opts.get("mqtt_port"))

    # Optionale Übersetzungstabelle (SIID → Name)
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

    state_base = opts.get("state_topic_base", "map/state")
    cmd_base = opts.get("cmd_topic_base", "map/cmd").strip("/")
    event_base = opts.get("event_topic_base", "map/events")

    mqtt_svc = MqttService()
    discovery = MqttDiscovery(mqtt_svc, state_base, cmd_base)
    # Two separate MapClient instances so event long-poll never blocks commands/state-refresh
    map_client = _build_map_client(opts)
    event_map_client = _build_map_client(opts)

    mapper = MapEventMapper(event_base, translation_map)
    cmd_parser = CommandParser(cmd_base, translation_map, translation_name_map)
    bridge = BridgeController()
    bridge.setup(map_client, mqtt_svc, mapper, cmd_parser)

    state_pusher = StatePusher(map_client, mqtt_svc, discovery, opts, translation_map)

    stop_event = threading.Event()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    connected = False
    started = False

    while not stop_event.is_set():
        if not connected:
            logger.info("Connecting to MQTT broker …")
            try:
                mqtt_svc.connect(
                    host=opts["mqtt_host"],
                    port=int(opts.get("mqtt_port", 1883)),
                    username=opts.get("mqtt_username", ""),
                    password=opts.get("mqtt_password", ""),
                    use_tls=bool(opts.get("mqtt_use_tls", False)),
                )
                time.sleep(1)
                mqtt_svc.subscribe(f"{cmd_base}/area/#")
                mqtt_svc.subscribe(f"{cmd_base}/output/#")
                mqtt_svc.subscribe(f"{cmd_base}/point/#")
                connected = True
            except Exception:
                logger.exception("MQTT connect failed, retrying in 15s")
                stop_event.wait(timeout=15)
                continue

        if not started:
            logger.info("Fetching MAP devices and publishing discovery …")
            try:
                areas = _enrich(map_client.get_areas().get("list", []), translation_map)
                outputs = _enrich(map_client.get_outputs().get("list", []), translation_map)
                points = _enrich(map_client.get_points().get("list", []), translation_map)
                discovery.publish_all(areas, points, outputs)
                discovery.publish_availability(True)
                logger.info("Discovery done: %d areas, %d outputs, %d points", len(areas), len(outputs), len(points))
            except Exception:
                logger.exception("Failed to fetch MAP devices, retrying in 15s")
                stop_event.wait(timeout=15)
                continue

            bridge.start_events(_build_sub_payload(), _build_fetch_payload(opts), map_client=event_map_client)
            state_pusher.start()
            started = True
            logger.info("Bridge running")

        stop_event.wait(timeout=5)

        if started and not mqtt_svc.connected:
            logger.warning("MQTT connection lost, reconnecting …")
            discovery.publish_availability(False)
            bridge.stop_events()
            state_pusher.stop()
            mqtt_svc.disconnect()
            connected = False
            started = False
            time.sleep(5)

    logger.info("Shutting down …")
    discovery.publish_availability(False)
    bridge.stop_events()
    state_pusher.stop()
    mqtt_svc.disconnect()
    logger.info("MAP to MQTT Addon stopped")


if __name__ == "__main__":
    main()
