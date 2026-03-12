"""
MAP5000 Web UI – served via HA Ingress on port 8080.
Provides a dashboard with real-time status for areas, points and outputs
and allows sending commands directly to the MAP controller.
"""

import logging
import threading
from typing import Optional

from flask import Flask, jsonify, render_template, request

logger = logging.getLogger(__name__)

_map_client = None
_translation_map: dict = {}


def _compute_status_label(point: dict) -> str:
    """Compute German status label for a point from its fields."""
    op = str(point.get("opState", "")).upper()
    if op in {"ALARM", "ACTIVE", "OPEN", "1"}:
        return "Ausgelöst"
    if op in {"BYPASSED", "DISABLED", "2"}:
        return "Gesperrt"
    if op in {"NORMAL", "CLEAN", "CLOSED", "0"}:
        return "Frei"
    # Derive from active/enabled when opState is absent or unknown
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
        if _map_client is None:
            return jsonify({"error": "MAP client not initialized"}), 503
        try:
            areas = list(_map_client.get_areas().get("list", []))
            points = list(_map_client.get_points().get("list", []))
            outputs = list(_map_client.get_outputs().get("list", []))

            for p in points:
                p["status_label"] = _compute_status_label(p)
                # Derive sperren field for consistency with MQTT state
                if "sperren" not in p:
                    p["sperren"] = not bool(p.get("enabled", True))

            for o in outputs:
                if "sperren" not in o:
                    o["sperren"] = not bool(o.get("enabled", True))

            return jsonify({"areas": areas, "points": points, "outputs": outputs})
        except Exception as exc:
            logger.exception("api_status error")
            return jsonify({"error": str(exc)}), 500

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
