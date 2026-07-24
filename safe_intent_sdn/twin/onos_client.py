"""Minimal ONOS REST client for the Digital Twin (E3).

Ported from ``sdn-xai-pipeline/pipeline/stage4_twin/onos_client.py`` with its
module-level ``config`` dependency removed: connection details are passed
explicitly (defaults match this repo's ControllerSettings/SecretSettings). Uses
only the standard library (``urllib``), so it has no third-party dependency.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any


class OnosError(RuntimeError):
    """Raised when an ONOS REST request fails."""


class OnosClient:
    """Small ONOS REST API client (GET/POST/DELETE over urllib)."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8181/onos/v1",
        username: str = "onos",
        password: str = "rocks",
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        """Issue an ONOS REST request, returning parsed JSON (or None if empty)."""
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8")) if body else None
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OnosError(f"ONOS HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise OnosError(f"ONOS connection failed: {exc.reason}") from exc

    def wait_until_ready(self, timeout: float = 120.0, interval: float = 2.0) -> None:
        """Block until ONOS answers a devices query, or raise after ``timeout``."""
        deadline = time.monotonic() + timeout
        last_error = "not ready"
        while time.monotonic() < deadline:
            try:
                self.request("GET", "devices")
                return
            except OnosError as exc:
                last_error = str(exc)
                time.sleep(interval)
        raise OnosError(f"ONOS not ready within {timeout:.0f}s: {last_error}")

    def devices(self) -> list[dict[str, Any]]:
        return self.request("GET", "devices").get("devices", [])

    def available_device_ids(self) -> set[str]:
        return {d["id"] for d in self.devices() if d.get("available") is True and d.get("id")}

    def wait_for_devices(
        self, expected_ids: set[str], timeout: float = 60.0, interval: float = 2.0
    ) -> set[str]:
        """Block until every id in ``expected_ids`` reports available."""
        deadline = time.monotonic() + timeout
        available: set[str] = set()
        while time.monotonic() < deadline:
            available = self.available_device_ids()
            if expected_ids <= available:
                return available
            time.sleep(interval)
        missing = sorted(expected_ids - available)
        raise OnosError(f"ONOS devices never connected: {missing}")

    def wait_for_hosts(
        self, expected_count: int, timeout: float = 30.0, interval: float = 2.0
    ) -> int:
        """Block until ONOS has discovered at least ``expected_count`` hosts.

        ONOS learns host locations from packet-ins. The twin's topologies build
        with ``autoStaticArp=True``, so hosts never emit ARP and ONOS cannot
        place them until they send real traffic -- until then ``fwd`` has no
        path to install and the first reachability probe fails. Callers pair
        this with a warm-up ``pingAll`` so every host is seen.

        Warns and returns the observed count on timeout rather than raising:
        the reachability checks themselves are the real verdict.
        """
        deadline = time.monotonic() + timeout
        count = 0
        while time.monotonic() < deadline:
            try:
                count = len(self.hosts())
            except OnosError:
                count = 0
            if count >= expected_count:
                return count
            time.sleep(interval)
        print(f"    [Twin] warning: ONOS discovered {count}/{expected_count} hosts before timeout")
        return count

    def wait_for_flow(
        self, device_id: str, priority: int, timeout: float = 15.0, interval: float = 1.0
    ) -> None:
        """Block until a flow of ``priority`` reaches ADDED on ``device_id``.

        On timeout it warns and returns rather than raising, matching the source
        behavior: an un-confirmed flow is a soft signal, and the downstream
        connectivity checks are the real verdict.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                for f in self.request("GET", f"flows/{device_id}").get("flows", []):
                    if f.get("priority") == priority and f.get("state") == "ADDED":
                        return
            except Exception:
                pass
            time.sleep(interval)
        print(f"    [Twin] warning: flow(priority={priority}) not confirmed ADDED (continuing)")

    def activate_application(self, app_name: str) -> None:
        self.request("POST", f"applications/{app_name}/active")

    def deploy_flow_rules(self, payload: dict[str, Any]) -> None:
        flows = payload.get("flows")
        if not isinstance(flows, list) or not flows:
            raise ValueError("payload must contain a non-empty 'flows' array")
        self.request("POST", "flows", payload)

    def flows(self) -> list[dict[str, Any]]:
        return self.request("GET", "flows").get("flows", [])

    def delete_flow(self, device_id: str, flow_id: str) -> None:
        self.request("DELETE", f"flows/{device_id}/{flow_id}")

    def delete_flows_by_priority(self, priority: int) -> int:
        """Delete every flow of ``priority`` (the rollback primitive). Returns count deleted."""
        matches = [f for f in self.flows() if f.get("priority") == priority]
        failed = 0
        for flow in matches:
            try:
                self.delete_flow(flow["deviceId"], flow["id"])
            except Exception as exc:
                failed += 1
                print(f"    [warn] failed to delete flow {flow.get('id')}: {exc}")
        if failed:
            print(f"    [warn] rollback left {failed}/{len(matches)} flows in ONOS")
        return len(matches) - failed

    def hosts(self) -> list[dict[str, Any]]:
        return self.request("GET", "hosts").get("hosts", [])

    def links(self) -> list[dict[str, Any]]:
        return self.request("GET", "links").get("links", [])

    def port_statistics(self) -> list[dict[str, Any]]:
        """Per-port byte/packet counters (used by E3 for link utilization evidence)."""
        return self.request("GET", "statistics/ports").get("statistics", [])

    def clear_app_flows(self, app_ids: list[str] | None = None) -> None:
        """Delete flows installed by the given apps (defaults to REST + fwd)."""
        if app_ids is None:
            app_ids = ["org.onosproject.rest", "org.onosproject.fwd"]
        for app_id in app_ids:
            try:
                self.request("DELETE", f"flows/application/{app_id}")
            except Exception:
                pass
