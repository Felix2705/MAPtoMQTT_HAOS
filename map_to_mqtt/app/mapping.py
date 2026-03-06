import json
from typing import Any, Dict, Optional, Tuple

from .translation import normalize_siid


class MapEventMapper:
    def __init__(self, event_base: str, translation_map: Optional[Dict[str, Dict[str, str]]] = None):
        self._event_base = event_base.strip("/")
        self._translation_map = translation_map or {}

    def map_event(self, evt: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        evt_type = "unknown"
        payload = evt
        if isinstance(evt, dict):
            evt_obj = evt.get("evt")
            if isinstance(evt_obj, dict):
                t = evt_obj.get("@type")
                if isinstance(t, list) and t:
                    evt_type = str(t[0])
                elif isinstance(t, str):
                    evt_type = t
                payload = evt_obj
        payload = self._with_translation(payload)
        topic = f"{self._event_base}/{evt_type}"
        return topic, payload

    def _with_translation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return payload
        if "name" in payload:
            return payload
        siid = self._extract_siid(payload)
        if not siid:
            return payload
        entry = self._translation_map.get(siid)
        if not entry:
            return payload
        enriched = dict(payload)
        enriched["name"] = entry.get("name", "")
        return enriched

    @staticmethod
    def _extract_siid(payload: Dict[str, Any]) -> str:
        for key in ("@self", "siid", "SIID", "resourceURL", "resourceUrl", "url", "@href"):
            value = payload.get(key)
            if not value:
                continue
            return MapEventMapper._normalize_siid(str(value))
        return ""

    @staticmethod
    def _normalize_siid(value: str) -> str:
        text = value.strip()
        if "://" in text:
            text = text.split("://", 1)[1]
        if "/" in text:
            text = text.split("/")[-1]
        return normalize_siid(text)


class CommandParser:
    def __init__(
        self,
        cmd_base: str,
        translation_map: Optional[Dict[str, Dict[str, str]]] = None,
        name_to_siid: Optional[Dict[str, str]] = None,
    ):
        self._cmd_base = cmd_base.strip("/")
        self._translation_map = translation_map or {}
        self._name_to_siid = name_to_siid or {}

    def parse(self, topic: str, payload: str) -> Dict[str, Any]:
        parts = topic.strip("/").split("/")
        base_parts = self._cmd_base.split("/") if self._cmd_base else []
        if base_parts and parts[: len(base_parts)] == base_parts:
            parts = parts[len(base_parts):]
        if len(parts) < 2:
            return {"type": "unknown"}
        resource = parts[0]
        if len(parts) >= 3:
            field = parts[-1]
            siid = "/" + "/".join(parts[1:-1])
        else:
            field = None
            siid = "/" + parts[1]
        siid = self._resolve_siid(siid)
        cmd = payload.strip()
        data = None
        if payload.strip().startswith("{"):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = None
        if data:
            if "cmd" in data:
                cmd = str(data["cmd"]).upper()
            elif "@cmd" in data:
                cmd = str(data["@cmd"]).upper()
            elif "value" in data:
                cmd = str(data["value"]).upper()
            else:
                cmd = ""
        return {
            "type": resource,
            "siid": siid,
            "cmd": cmd.upper(),
            "params": data or {},
            "field": field,
        }

    def _resolve_siid(self, siid: str) -> str:
        raw = siid.lstrip("/")
        normalized = normalize_siid(raw)
        if normalized in self._translation_map:
            return "/" + normalized
        mapped = self._name_to_siid.get(raw)
        if not mapped:
            return "/" + normalized
        return "/" + normalize_siid(mapped)
