"""
MAP5000 Web UI – served via HA Ingress on port 8080.
Provides a dashboard with real-time status for areas, points and outputs
and allows sending commands directly to the MAP controller.
"""

import logging
import threading
from typing import Optional

from flask import Flask, jsonify, render_template, request

from .translation import normalize_siid

logger = logging.getLogger(__name__)

_map_client = None
_translation_map: dict = {}
_map_online: bool = True
_refresh_callback = None


def set_map_online(online: bool) -> None:
    """Called by the health monitor to keep the web UI status in sync."""
    global _map_online
    _map_online = online


def set_refresh_callback(callback) -> None:
    """Register a callback that triggers MQTT state refresh after web UI commands."""
    global _refresh_callback
    _refresh_callback = callback


def _enrich(items: list, translation_map: dict) -> list:
    """Add 'name' field from translation map to each item if not already present."""
    result = []
    for item in items:
        siid = normalize_siid(str(item.get("@self", "")).lstrip("/"))
        entry = translation_map.get(siid)
        if entry and "name" not in item:
            item = dict(item)
            item["name"] = entry.get("name", "")
        result.append(item)
    return result


def _compute_status_label(point: dict) -> str:
    """Compute German status label for a point from its fields."""
    op = str(point.get("opState", "")).upper()
    if op in {"ALARM", "ACTIVE", "OPEN", "1"}:
        return "Ausgelöst"
    if op in {"BYPASSED", "DISABLED", "2"}:
        return "Gesperrt"
    if op in {"NORMAL", "CLEAN", "CLOSED", "0"}:
        return "Frei"
    if not point.get("enabled", True):
        return "Gesperrt"
    if point.get("active", False):
        return "Ausgelöst"
    return "Frei"


def create_app(map_client, translation_map: dict) -> Flask:
    global _map_client, _translation_map
    _map_client = map_client
    _translation_map = translation_map

    app = Flask(__name__, template_folder="templates")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        global _map_online
        if _map_client is None:
            return jsonify({"error": "MAP client not initialized", "map_online": False}), 503
        try:
            areas   = _enrich(list(_map_client.get_areas().get("list", [])),   _translation_map)
            points  = _enrich(list(_map_client.get_points().get("list", [])),  _translation_map)
            outputs = _enrich(list(_map_client.get_outputs().get("list", [])), _translation_map)

            for p in points:
                p["status_label"] = _compute_status_label(p)
                if "sperren" not in p:
                    p["sperren"] = not bool(p.get("enabled", True))

            for o in outputs:
                if "sperren" not in o:
                    o["sperren"] = not bool(o.get("enabled", True))

            _map_online = True
            return jsonify({
                "map_online": True,
                "areas": areas,
                "points": points,
                "outputs": outputs,
            })
        except Exception as exc:
            logger.exception("api_status error")
            _map_online = False
            return jsonify({"map_online": False, "error": str(exc)}), 500

    @app.route("/api/cmd", methods=["POST"])
    def api_cmd():
        if _map_client is None:
            return jsonify({"error": "MAP client not initialized"}), 503
        data = request.get_json(force=True, silent=True) or {}
        resource = data.get("resource", "")
        siid = data.get("siid", "").strip("/")
        cmd = data.get("cmd", "").upper()

        if not resource or not siid or not cmd:
            return jsonify({"error": "resource, siid and cmd are required"}), 400

        try:
            payload = {"@cmd": cmd}
            if resource == "area":
                _map_client.post_area_command(siid, payload)
            elif resource == "point":
                _map_client.post_point_command(siid, payload)
            elif resource == "output":
                _map_client.post_output_command(siid, payload)
            else:
                return jsonify({"error": f"unknown resource: {resource}"}), 400
            logger.info("Web UI command: %s %s %s", resource, siid, cmd)
            # Trigger MQTT state refresh so MQTT topics update immediately after web UI commands
            if _refresh_callback:
                try:
                    _refresh_callback()
                except Exception:
                    logger.exception("refresh_callback error")
            return jsonify({"ok": True, "cmd": cmd, "siid": siid})
        except Exception as exc:
            logger.exception("api_cmd error: %s %s %s", resource, siid, cmd)
            return jsonify({"error": str(exc)}), 500

    return app


def start_web_ui(map_client, translation_map: dict, port: int = 8080) -> None:
    """Start Flask in a daemon thread."""
    app = create_app(map_client, translation_map)

    def _run():
        logger.info("Web UI starting on port %d", port)
        app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True, name="WebUI")
    t.start()
    logger.info("Web UI thread started on port %d", port)
