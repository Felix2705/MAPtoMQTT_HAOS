import json
import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from .discovery import AVAILABILITY_TOPIC

logger = logging.getLogger(__name__)


class MqttService:
    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._on_command: Optional[Callable[[str, str], None]] = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def set_command_handler(self, handler: Callable[[str, str], None]) -> None:
        self._on_command = handler

    def connect(self, host: str, port: int, username: str, password: str, use_tls: bool) -> None:
        self._client = mqtt.Client()
        if username or password:
            self._client.username_pw_set(username, password)
        if use_tls:
            self._client.tls_set()
        # Last Will: HA markiert alle Entities als "unavailable" wenn der Addon abstürzt
        self._client.will_set(AVAILABILITY_TOPIC, "offline", qos=1, retain=True)
        logger.debug("MQTT connecting to %s:%s tls=%s", host, port, use_tls)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.connect(host, port, keepalive=30)
        self._client.loop_start()

    def disconnect(self) -> None:
        if self._client is None:
            return
        logger.debug("MQTT disconnecting")
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None
        self._connected = False

    def publish(self, topic: str, payload: dict, retain: bool = False) -> None:
        if not self._client:
            return
        data = json.dumps(payload)
        logger.debug("MQTT publish %s (%d bytes)", topic, len(data))
        self._client.publish(topic, data, qos=0, retain=retain)

    def publish_raw(self, topic: str, payload: str, retain: bool = False) -> None:
        """Publish a plain string payload (used for availability)."""
        if not self._client:
            return
        logger.debug("MQTT publish_raw %s = %s", topic, payload)
        self._client.publish(topic, payload, qos=1, retain=retain)

    def subscribe(self, topic: str) -> None:
        if not self._client:
            return
        logger.debug("MQTT subscribe %s", topic)
        self._client.subscribe(topic, qos=0)

    def _on_connect(self, client: mqtt.Client, _userdata, _flags, rc):
        self._connected = rc == 0
        if self._connected:
            logger.info("MQTT connected")
        else:
            logger.error("MQTT connect failed rc=%s", rc)

    def _on_disconnect(self, client: mqtt.Client, _userdata, rc):
        self._connected = False
        logger.warning("MQTT disconnected rc=%s", rc)

    def _on_message(self, client: mqtt.Client, _userdata, msg: mqtt.MQTTMessage):
        if not self._on_command:
            return
        payload = msg.payload.decode("utf-8", errors="ignore")
        logger.debug("MQTT message %s (%d bytes)", msg.topic, len(msg.payload))
        self._on_command(msg.topic, payload)
