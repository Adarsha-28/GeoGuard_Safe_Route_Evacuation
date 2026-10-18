"""Central HTTP request handler and API router for GeoGuard."""

from __future__ import annotations

import http.server
import json
import os
import urllib.parse
from typing import Any

from backend.api.alerts import handle_create_alert, handle_get_alerts
from backend.api.grids import handle_get_grid_by_id, handle_get_grids
from backend.api.health import handle_health
from backend.api.risk import handle_get_risk_by_grid_id, handle_get_risk_by_point, handle_sync_weather
from backend.api.routes import handle_calculate_safe_route, handle_start_evacuation
from backend.api.shelters import (
    handle_get_all_shelters,
    handle_get_nearby_shelters,
    handle_get_shelter_by_id,
)
from backend.config import FRONTEND_DIR, ROOT_DIR, logger


class GeoGuardRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler routing /api/* to services and serving frontend static files."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Default directory to serve static assets from
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def end_headers(self) -> None:
        """Inject CORS and no-cache headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        """Route GET requests to API handlers or static file handler."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. Root and frontend redirects
        if path in ("", "/", "/index.html"):
            # Serve frontend/index.html
            self.send_response(301)
            self.send_header("Location", "/frontend/index.html")
            self.end_headers()
            return

        # Redirect legacy /web/ to /frontend/
        if path.startswith("/web/"):
            new_path = path.replace("/web/", "/frontend/")
            self.send_response(301)
            self.send_header("Location", new_path)
            self.end_headers()
            return

        # 2. REST API Routes
        try:
            if path == "/api/health":
                status, data = handle_health()
                self.send_json_response(data, status=status)
                return

            if path == "/api/grids":
                status, data = handle_get_grids()
                self.send_json_response(data, status=status)
                return

            if path.startswith("/api/grids/"):
                grid_id_str = path.split("/api/grids/", 1)[1]
                status, data = handle_get_grid_by_id(grid_id_str)
                self.send_json_response(data, status=status)
                return

            if path == "/api/risk/point":
                lat = query_params.get("lat", [None])[0]
                lng = query_params.get("lng", [None])[0]
                status, data = handle_get_risk_by_point(lat, lng)
                self.send_json_response(data, status=status)
                return

            if path.startswith("/api/risk/"):
                grid_id_str = path.split("/api/risk/", 1)[1]
                status, data = handle_get_risk_by_grid_id(grid_id_str)
                self.send_json_response(data, status=status)
                return

            if path in ("/api/shelters", "/api/shelters/all"):
                status, data = handle_get_all_shelters()
                self.send_json_response(data, status=status)
                return

            if path == "/api/shelters/nearby":
                status, data = handle_get_nearby_shelters(query_params)
                self.send_json_response(data, status=status)
                return

            if path.startswith("/api/shelters/"):
                shelter_id_str = path.split("/api/shelters/", 1)[1]
                status, data = handle_get_shelter_by_id(shelter_id_str)
                self.send_json_response(data, status=status)
                return

            if path in ("/api/alerts", "/api/alerts/all"):
                status, data = handle_get_alerts()
                self.send_json_response(data, status=status)
                return

            # API 404
            if path.startswith("/api/"):
                self.send_error_response(404, f"API endpoint '{path}' not found.")
                return

        except Exception as e:
            logger.error(f"Internal server error handling GET {self.path}: {e}", exc_info=True)
            self.send_error_response(500, "An internal server error occurred.")
            return

        # 3. Static files
        super().do_GET()

    def do_POST(self) -> None:
        """Route POST requests with JSON payloads."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        # Read JSON body safely
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))
            else:
                payload = {}
        except Exception as e:
            self.send_error_response(400, f"Malformed JSON request body: {e}")
            return

        try:
            if path in ("/api/routes", "/api/routes/safe", "/api/routes/recalculate"):
                status, data = handle_calculate_safe_route(payload)
                self.send_json_response(data, status=status)
                return

            if path == "/api/evacuation/start":
                status, data = handle_start_evacuation(payload)
                self.send_json_response(data, status=status)
                return

            if path in ("/api/alerts", "/api/alerts/create"):
                status, data = handle_create_alert(payload)
                self.send_json_response(data, status=status)
                return

            if path in ("/api/weather/sync", "/api/weather/update"):
                status, data = handle_sync_weather()
                self.send_json_response(data, status=status)
                return

            # API 404
            if path.startswith("/api/"):
                self.send_error_response(404, f"API endpoint '{path}' not found.")
                return

        except Exception as e:
            logger.error(f"Internal server error handling POST {self.path}: {e}", exc_info=True)
            self.send_error_response(500, "An internal server error occurred.")
            return

        self.send_error_response(404, "Endpoint not found.")

    def send_json_response(self, data: Any, status: int = 200) -> None:
        """Serialize and send JSON response."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_response(self, status: int, message: str) -> None:
        """Send standardized JSON error response without exposing stack traces."""
        self.send_json_response({"error": message}, status=status)

    def log_message(self, format: str, *args: Any) -> None:
        """Route standard HTTP server logging to python logger."""
        logger.debug(f"{self.address_string()} - {format % args}")
