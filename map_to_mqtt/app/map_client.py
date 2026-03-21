import logging
import threading
import time
from typing import Any, Dict, Optional

import requests
import urllib3
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class MapClient:
    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool, timeout_sec: int = 20):
        self._base_url = base_url.rstrip("/")
        self._auth = HTTPDigestAuth(username, password)
        self._verify_tls = verify_tls
        self._timeout_sec = timeout_sec
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._min_delay_sec = 1.0

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        effective_timeout = timeout if timeout is not None else self._timeout_sec
        with self._lock:
            wait = self._min_delay_sec - (time.time() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            start = time.time()
            response = self._session.request(
                method=method,
                url=url,
                auth=self._auth,
                json=payload,
                timeout=effective_timeout,
                verify=self._verify_tls,
            )
            self._last_request_at = time.time()
        elapsed = time.time() - start
        logger.debug("MAP %s %s -> %s in %.2fs", method, path, response.status_code, elapsed)
        if response.status_code >= 400:
            snippet = response.text[:300] if response.text else ""
            logger.warning("MAP error %s %s: %s", response.status_code, path, snippet)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def get_panel(self) -> Dict[str, Any]:
        return self._request("GET", "/panel")

    def get_desc(self) -> Dict[str, Any]:
        return self._request("GET", "/desc")

    def get_areas(self) -> Dict[str, Any]:
        return self._request("GET", "/areas")

    def get_outputs(self) -> Dict[str, Any]:
        return self._request("GET", "/outputs")

    def get_points(self) -> Dict[str, Any]:
        return self._request("GET", "/points")

    def create_subscription(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/sub", payload)

    def get_subscriptions(self) -> Dict[str, Any]:
        return self._request("GET", "/sub")

    def fetch_events(self, subscription_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Long-poll: MAP hält die Verbindung für maxTime Sekunden offen.
        # Timeout muss größer sein als maxTime + Puffer.
        max_time = payload.get("maxTime", 50)
        fetch_timeout = int(max_time) + 15
        return self._request("POST", subscription_url, payload, timeout=fetch_timeout)

    def delete_subscription(self, subscription_url: str) -> Dict[str, Any]:
        return self._request("DELETE", subscription_url)

    def post_area_command(self, area_siid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", f"/{area_siid.lstrip('/')}", payload)

    def post_output_command(self, output_siid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", f"/{output_siid.lstrip('/')}", payload)

    def post_point_command(self, point_siid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", f"/{point_siid.lstrip('/')}", payload)

    @staticmethod
    def normalize_event_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        if "evts" in data:
            return data
        if "events" in data:
            return {"evts": data.get("events", [])}
        return {"evts": []}
