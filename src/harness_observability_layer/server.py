"""Localhost-first HOL server."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from harness_observability_layer.plugin.api import load_live_dashboard_data
from harness_observability_layer.reporting.project_dashboard import (
    build_project_dashboard_html,
)


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


def _open_url(url: str) -> bool:
    """Open the dashboard URL without leaking noisy desktop-tool errors."""
    commands: list[list[str]] = []
    if sys.platform == "darwin":
        commands.append(["open", url])
    elif os.name == "nt":
        commands.append(["cmd", "/c", "start", "", url])
    else:
        xdg_open = shutil.which("xdg-open")
        gio = shutil.which("gio")
        if xdg_open:
            commands.append([xdg_open, url])
        if gio:
            commands.append([gio, "open", url])

    for command in commands:
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode == 0:
                return True
        except OSError:
            continue
    return False


@dataclass
class DashboardCache:
    project_root: str
    resolve_file_stats: bool = False
    aggregate: Dict[str, Any] | None = None

    def load(self, *, force: bool = False) -> Dict[str, Any]:
        if self.aggregate is None or force:
            self.aggregate = load_live_dashboard_data(
                self.project_root,
                resolve_file_stats=self.resolve_file_stats,
            )
        return self.aggregate


def create_server(
    *,
    host: str,
    port: int,
    project_root: str,
    resolve_file_stats: bool = False,
) -> ThreadingHTTPServer:
    """Create a local HTTP server with HOL dashboard endpoints."""
    cache = DashboardCache(
        project_root=project_root, resolve_file_stats=resolve_file_stats
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "HOLServer/1.0"

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: Dict[str, Any], *, status: int = 200) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/index.html"}:
                aggregate = cache.load()
                self._send_html(
                    build_project_dashboard_html(aggregate, live_mode=True)
                )
                return

            if self.path == "/api/data":
                self._send_json(cache.load())
                return

            if self.path == "/api/refresh":
                aggregate = cache.load(force=True)
                self._send_json(
                    {
                        "ok": True,
                        "sessions": int(
                            (aggregate.get("totals") or {}).get("sessions", 0) or 0
                        ),
                    }
                )
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve_dashboard(
    *,
    host: str = "127.0.0.1",
    port: int = 3845,
    project_root: str = ".",
    no_open: bool = False,
    resolve_file_stats: bool = False,
) -> None:
    """Start the HOL local dashboard server."""
    server = create_server(
        host=host,
        port=port,
        project_root=project_root,
        resolve_file_stats=resolve_file_stats,
    )
    url = f"http://localhost:{server.server_port}"
    print(f"HOL dashboard running at {url}")
    if not no_open:
        _open_url(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
