"""
Health check system for Alpha Sniper V4.2

Provides:
1. HTTP endpoint on :8080/health for external monitoring
2. Heartbeat file updated every 30s at /var/run/alpha-sniper/heartbeat.json
3. CLI healthcheck command: python -m alpha_sniper.healthcheck
"""
import json
import os
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional


# Global bot reference for health checks
_bot_instance: Optional[object] = None
_heartbeat_file = Path("/var/run/alpha-sniper/heartbeat.json")
_heartbeat_thread: Optional[threading.Thread] = None


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks"""

    def log_message(self, format, *args):
        """Suppress HTTP request logs (too noisy)"""
        pass

    def do_GET(self):
        """Handle GET /health"""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/":
            self._handle_root()
        else:
            self.send_error(404)

    def _handle_root(self):
        """Root endpoint with basic info"""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Alpha Sniper V4.2 Health Check Server\n")
        self.wfile.write(b"GET /health - Health check endpoint\n")

    def _handle_health(self):
        """Health check endpoint"""
        global _bot_instance

        if _bot_instance is None:
            # Bot not initialized yet
            self.send_response(503)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "status": "starting",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Bot initializing"
            }
            self.wfile.write(json.dumps(response).encode())
            return

        try:
            # Check if bot is running
            is_running = getattr(_bot_instance, 'running', False)

            # Check last cycle time (if available)
            risk_engine = getattr(_bot_instance, 'risk_engine', None)
            last_check = None
            if risk_engine:
                last_check = getattr(risk_engine, 'last_update_time', None)

            # Determine health status
            if is_running:
                status_code = 200
                status = "healthy"
                message = "Bot is running normally"
            else:
                status_code = 503
                status = "unhealthy"
                message = "Bot is not running"

            # Build response
            response = {
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "message": message,
                "bot_running": is_running,
                "last_check": last_check.isoformat() if last_check else None
            }

            self.send_response(status_code)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())

        except Exception as e:
            # Health check itself failed
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Health check failed: {str(e)}"
            }
            self.wfile.write(json.dumps(response).encode())


def start_health_server(bot_instance, port: int = 8080):
    """
    Start HTTP health check server in background thread

    Args:
        bot_instance: Reference to AlphaSniperBot instance
        port: HTTP port (default: 8080)
    """
    global _bot_instance
    _bot_instance = bot_instance

    def run_server():
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        bot_instance.logger.info(f"🏥 Health check server started on port {port}")
        bot_instance.logger.info(f"   GET http://localhost:{port}/health")
        try:
            server.serve_forever()
        except Exception as e:
            bot_instance.logger.error(f"Health server error: {e}")

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Also start heartbeat file updater
    start_heartbeat_updater(bot_instance)


def start_heartbeat_updater(bot_instance, interval: int = 30):
    """
    Start background thread that updates heartbeat file every N seconds

    Args:
        bot_instance: Reference to AlphaSniperBot instance
        interval: Update interval in seconds (default: 30)
    """
    global _heartbeat_thread, _heartbeat_file

    # Create runtime directory if it doesn't exist
    runtime_dir = _heartbeat_file.parent
    if not runtime_dir.exists():
        # Fall back to local directory if /var/run not writable
        _heartbeat_file = Path("./heartbeat.json")
        bot_instance.logger.info(f"💓 Heartbeat file: {_heartbeat_file}")
    else:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        bot_instance.logger.info(f"💓 Heartbeat file: {_heartbeat_file}")

    def update_heartbeat():
        while True:
            try:
                is_running = getattr(bot_instance, 'running', False)
                risk_engine = getattr(bot_instance, 'risk_engine', None)

                # Get last scan time (ISO format)
                last_scan_time = None
                if hasattr(bot_instance, 'last_scan_time') and bot_instance.last_scan_time:
                    last_scan_time = datetime.fromtimestamp(bot_instance.last_scan_time).isoformat()

                heartbeat_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "running" if is_running else "stopped",
                    "pid": os.getpid(),
                    "open_positions": len(risk_engine.open_positions) if risk_engine else 0,
                    "equity": float(risk_engine.current_equity) if risk_engine else 0.0,
                    "session_start_equity": float(risk_engine.session_start_equity) if risk_engine and risk_engine.session_start_equity else float(risk_engine.current_equity) if risk_engine else 0.0,
                    "session_pnl_pct": float(((risk_engine.current_equity - risk_engine.session_start_equity) / risk_engine.session_start_equity * 100) if risk_engine and risk_engine.session_start_equity and risk_engine.session_start_equity > 0 else 0.0),
                    "signals_today": int(risk_engine.signals_today) if risk_engine and hasattr(risk_engine, 'signals_today') else 0,
                    "pumps_today": int(risk_engine.pumps_today) if risk_engine and hasattr(risk_engine, 'pumps_today') else 0,
                    "last_scan_time": last_scan_time
                }

                # Atomic write
                temp_file = _heartbeat_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(heartbeat_data, f, indent=2)
                temp_file.replace(_heartbeat_file)

            except Exception as e:
                bot_instance.logger.debug(f"Heartbeat update failed: {e}")

            time.sleep(interval)

    _heartbeat_thread = threading.Thread(target=update_heartbeat, daemon=True)
    _heartbeat_thread.start()


def check_health_from_cli() -> int:
    """
    CLI health check - reads heartbeat file and returns exit code

    Returns:
        0 if healthy, 1 if unhealthy, 2 if unknown
    """
    # Try multiple possible heartbeat locations
    possible_locations = [
        Path("/var/run/alpha-sniper/heartbeat.json"),
        Path("./heartbeat.json"),
    ]

    heartbeat_file = None
    for location in possible_locations:
        if location.exists():
            heartbeat_file = location
            break

    if not heartbeat_file:
        print("❌ Heartbeat file not found. Bot may not be running.")
        print(f"   Checked: {', '.join(str(p) for p in possible_locations)}")
        return 2

    try:
        with open(heartbeat_file, 'r') as f:
            heartbeat = json.load(f)

        timestamp_str = heartbeat.get('timestamp', '')
        status = heartbeat.get('status', 'unknown')
        pid = heartbeat.get('pid', 0)
        positions = heartbeat.get('open_positions', 0)
        equity = heartbeat.get('equity', 0.0)

        # Parse timestamp
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        age_seconds = (datetime.utcnow() - timestamp.replace(tzinfo=None)).total_seconds()

        print(f"📊 Alpha Sniper Health Status")
        print(f"   Status: {status}")
        print(f"   PID: {pid}")
        print(f"   Last heartbeat: {age_seconds:.0f}s ago")
        print(f"   Open positions: {positions}")
        print(f"   Equity: ${equity:.2f}")

        # Healthy if:
        # - Status is "running"
        # - Heartbeat is less than 60s old
        if status == "running" and age_seconds < 60:
            print("✅ Status: HEALTHY")
            return 0
        elif age_seconds >= 60:
            print("⚠️  Status: STALE (heartbeat too old)")
            return 1
        else:
            print("❌ Status: UNHEALTHY")
            return 1

    except Exception as e:
        print(f"❌ Error reading heartbeat: {e}")
        return 2


if __name__ == "__main__":
    # Allow running as: python -m alpha_sniper.health
    exit(check_health_from_cli())
