import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from .map_client import MapClient
from .mapping import CommandParser, MapEventMapper
from .mqtt_client import MqttService

logger = logging.getLogger(__name__)


class EventWorker:
    def __init__(
        self,
        map_client: MapClient,
        mqtt: MqttService,
        mapper: MapEventMapper,
        sub_payload: Dict[str, Any],
        fetch_payload: Dict[str, Any],
        on_status: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self._map = map_client
        self._mqtt = mqtt
        self._mapper = mapper
        self._sub_payload = sub_payload
        self._fetch_payload = fetch_payload
        self._on_status = on_status
        self._on_error = on_error
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._subscription_url: Optional[str] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="EventWorker")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        try:
            self._emit_status("connecting")
            logger.info("Creating MAP subscription")
            logger.debug("Subscribe payload: %s", self._sub_payload)
            sub = self._map.create_subscription(self._sub_payload)
            self._subscription_url = sub.get("subscriptionURL")
            if not self._subscription_url:
                self._emit_error("Subscription failed: no subscriptionURL in response")
                return
            logger.info("Subscription active: %s", self._subscription_url)
            self._emit_status("subscribed")
            while self._running:
                data = self._map.fetch_events(self._subscription_url, self._fetch_payload)
                norm = self._map.normalize_event_payload(data)
                evt_list = norm.get("evts", [])
                if evt_list:
                    logger.debug("Fetched %d event(s)", len(evt_list))
                for evt in evt_list:
                    topic, payload = self._mapper.map_event(evt)
                    self._mqtt.publish(topic, payload)
                time.sleep(0.1)
        except Exception as exc:
            logger.exception("Event worker error")
            self._emit_error(str(exc))
        finally:
            if self._subscription_url:
                try:
                    logger.info("Deleting subscription: %s", self._subscription_url)
                    self._map.delete_subscription(self._subscription_url)
                except Exception:
                    pass
            self._emit_status("stopped")

    def _emit_status(self, status: str) -> None:
        if self._on_status:
            self._on_status(status)

    def _emit_error(self, msg: str) -> None:
        if self._on_error:
            self._on_error(msg)


class BridgeController:
    def __init__(self) -> None:
        self._event_worker: Optional[EventWorker] = None
        self._map_client: Optional[MapClient] = None
        self._mqtt: Optional[MqttService] = None
        self._mapper: Optional[MapEventMapper] = None
        self._cmd_parser: Optional[CommandParser] = None

    def setup(self, map_client: MapClient, mqtt: MqttService, mapper: MapEventMapper, cmd_parser: CommandParser) -> None:
        self._map_client = map_client
        self._mqtt = mqtt
        self._mapper = mapper
        self._cmd_parser = cmd_parser
        self._mqtt.set_command_handler(self._handle_command)

    def start_events(self, sub_payload: Dict[str, Any], fetch_payload: Dict[str, Any], map_client: Optional[MapClient] = None) -> None:
        if not self._map_client or not self._mqtt or not self._mapper:
            return
        if self._event_worker and self._event_worker._running:
            return
        logger.info("Starting event worker")
        self._event_worker = EventWorker(
            map_client if map_client is not None else self._map_client,
            self._mqtt,
            self._mapper,
            sub_payload,
            fetch_payload,
            on_status=lambda s: logger.info("MAP status: %s", s),
            on_error=lambda e: logger.error("MAP error: %s", e),
        )
        self._event_worker.start()

    def stop_events(self) -> None:
        if self._event_worker:
            logger.info("Stopping event worker")
            self._event_worker.stop()
            self._event_worker = None

    def _handle_command(self, topic: str, payload: str) -> None:
        if not self._map_client or not self._cmd_parser:
            return
        try:
            self._handle_command_safe(topic, payload)
        except Exception:
            logger.exception("Command execution failed: topic=%s payload=%s", topic, payload)

    def _handle_command_safe(self, topic: str, payload: str) -> None:
        cmd = self._cmd_parser.parse(topic, payload)
        params = cmd.get("params") if isinstance(cmd.get("params"), dict) else {}
        if params.get("source") == "bridge":
            return
        logger.info("Command received: %s", cmd)
        if cmd.get("field"):
            self._execute_field_command(cmd)
            return
        if cmd.get("type") == "area":
            self._execute_area(cmd)
        elif cmd.get("type") == "output":
            self._execute_output(cmd)
        elif cmd.get("type") == "point":
            self._execute_point(cmd)

    def _execute_area(self, cmd: Dict[str, Any]) -> None:
        allowed = {
            "ARM", "DISARM", "STARTWALKTEST", "STOPWALKTEST",
            "STARTMDTEST", "STOPMDTEST", "STARTCHIMEMODE", "STOPCHIMEMODE", "BELLTEST",
        }
        cmd_name = cmd.get("cmd", "")
        if cmd_name not in allowed:
            return
        payload: Dict[str, Any] = {"@cmd": cmd_name}
        payload.update(cmd.get("params", {}))
        self._map_client.post_area_command(cmd["siid"], payload)
        logger.info("Area command sent: %s %s", cmd_name, cmd["siid"])

    def _execute_output(self, cmd: Dict[str, Any]) -> None:
        cmd_name = cmd.get("cmd", "")
        if cmd_name not in {"ON", "OFF", "ENABLE", "DISABLE"}:
            flag = self._to_bool(cmd_name)
            if flag is not None:
                cmd_name = "ENABLE" if flag else "DISABLE"
            else:
                return
        self._map_client.post_output_command(cmd["siid"], {"@cmd": cmd_name})
        logger.info("Output command sent: %s %s", cmd_name, cmd["siid"])

    def _execute_point(self, cmd: Dict[str, Any]) -> None:
        cmd_name = cmd.get("cmd", "")
        if cmd_name not in {"ENABLE", "DISABLE"}:
            flag = self._to_bool(cmd_name)
            if flag is not None:
                cmd_name = "ENABLE" if flag else "DISABLE"
            else:
                return
        self._map_client.post_point_command(cmd["siid"], {"@cmd": cmd_name})
        logger.info("Point command sent: %s %s", cmd_name, cmd["siid"])

    def _execute_field_command(self, cmd: Dict[str, Any]) -> None:
        value = cmd.get("cmd", "")
        if not value and isinstance(cmd.get("params"), dict):
            value = str(cmd["params"].get("value", ""))
        flag = self._to_bool(value)
        if flag is None:
            return
        resource = cmd.get("type")
        field = cmd.get("field")
        if resource == "point" and field == "sperren":
            # sperren=true (switch ON) → DISABLE (Melder Gesperrt/bypassed)
            self._map_client.post_point_command(cmd["siid"], {"@cmd": "DISABLE" if flag else "ENABLE"})
            logger.info("Point sperren set to %s: %s", flag, cmd["siid"])
        elif resource == "point" and field == "enabled":
            self._map_client.post_point_command(cmd["siid"], {"@cmd": "ENABLE" if flag else "DISABLE"})
            logger.info("Point enabled set to %s: %s", flag, cmd["siid"])
        elif resource == "output" and field == "sperren":
            # sperren=true (switch ON) → DISABLE (Ausgang Gesperrt)
            self._map_client.post_output_command(cmd["siid"], {"@cmd": "DISABLE" if flag else "ENABLE"})
            logger.info("Output sperren set to %s: %s", flag, cmd["siid"])
        elif resource == "output" and field == "enabled":
            self._map_client.post_output_command(cmd["siid"], {"@cmd": "ENABLE" if flag else "DISABLE"})
            logger.info("Output enabled set to %s: %s", flag, cmd["siid"])
        elif resource == "output" and field == "on":
            self._map_client.post_output_command(cmd["siid"], {"@cmd": "ON" if flag else "OFF"})
            logger.info("Output on set to %s: %s", flag, cmd["siid"])
        elif resource == "area" and field == "armed":
            self._map_client.post_area_command(cmd["siid"], {"@cmd": "ARM" if flag else "DISARM"})
            logger.info("Area armed set to %s: %s", flag, cmd["siid"])

    @staticmethod
    def _to_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return None
