"""
Real-Time Telemetry Agent for Vigilant Lens.

Captures:
- Mouse velocity (pixels/sec) and click frequency
- Keystroke flight time (time between key presses)
- Active window title (for productivity alignment)

Sends data to /api/telemetry endpoint every 5 seconds.
"""

import os
import json
import time
import threading
import platform
import subprocess
import psutil
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
import requests
from pynput import mouse, keyboard
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyboardListener
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uba.telemetry.agent")


class TelemetryAgent:
    """
    Real-time telemetry collection agent.
    
    Captures behavioral biometrics and system activity,
    sends to backend every 5 seconds.
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000/api/v1/telemetry/",
        user_id: str = "U001",
        send_interval: int = 5,
        debug: bool = False,
        track_keystrokes: bool = False
    ):
        self.api_url = api_url
        self.user_id = user_id
        self.send_interval = send_interval
        self.debug = debug

        # Consent-gated keystroke capture.
        #
        # The global keyboard hook records keystroke *timing* (flight time), but
        # a system-wide key listener is a keylogger and MUST NOT run without
        # explicit consent. This is OFF by default and only enabled when
        # track_keystrokes=True is passed (or UBA_TRACK_KEYSTROKES=1 is set).
        # When disabled, mouse/window telemetry still runs but no keyboard
        # listener is registered.
        env_flag = os.environ.get("UBA_TRACK_KEYSTROKES", "").strip().lower()
        env_consent = env_flag in ("1", "true", "yes", "on")
        self.track_keystrokes = bool(track_keystrokes or env_consent)
        
        # Mouse tracking
        self.mouse_positions: List[Dict] = []
        self.mouse_clicks = 0
        self.last_mouse_time = None
        self.mouse_velocity_samples: deque = deque(maxlen=100)
        
        # Keyboard tracking
        self.last_key_time = None
        self.key_flight_times: deque = deque(maxlen=100)
        self.key_press_count = 0
        
        # Active window tracking
        self.current_app = None
        self.current_window_title = None
        
        # Control flags
        self.running = False
        self.mouse_listener: Optional[MouseListener] = None
        self.keyboard_listener: Optional[KeyboardListener] = None
        self.telemetry_thread: Optional[threading.Thread] = None

        logger.info(
            f"TelemetryAgent initialized for user {user_id} "
            f"(keystroke tracking {'ENABLED' if self.track_keystrokes else 'disabled'})"
        )
    
    def get_active_window(self) -> Dict[str, str]:
        """
        Get currently active window/application.
        
        Returns:
            Dict with 'app_name' and 'window_title'
        """
        try:
            if platform.system() == 'Windows':
                try:
                    import win32gui
                    import win32process
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process = psutil.Process(pid)
                        app_name = process.name()
                    except Exception:
                        app_name = "unknown"
                    return {
                        "app_name": app_name.lower(),
                        "window_title": title,
                        "pid": str(pid)
                    }
                except ImportError:
                    logger.warning("pywin32 not installed — install with: pip install pywin32")
                    # Without pywin32 we cannot determine the *foreground* window.
                    # psutil can enumerate processes but has no notion of which
                    # one is focused; returning an arbitrary running process
                    # (e.g. procs[0]) would be misleading telemetry. Report
                    # 'unknown' truthfully instead.
                    return {"app_name": "unknown", "window_title": "Unknown", "pid": "0"}
            
            elif platform.system() == 'Darwin':  # macOS
                try:
                    from AppKit import NSWorkspace
                    workspace = NSWorkspace.sharedWorkspace()
                    app = workspace.activeApplication()
                    return {
                        "app_name": app.get('ApplicationName', 'Unknown').lower(),
                        "window_title": app.get('ApplicationName', ''),
                        "pid": str(app.get('ProcessIdentifier', 0))
                    }
                except:
                    return {"app_name": "unknown", "window_title": "Unknown", "pid": "0"}
            
            else:  # Linux
                try:
                    result = subprocess.run(
                        ['xdotool', 'getactivewindow', 'getwindowname', '--sync'],
                        capture_output=True, text=True, timeout=1
                    )
                    return {
                        "app_name": "unknown",
                        "window_title": result.stdout.strip() or "Unknown",
                        "pid": "0"
                    }
                except:
                    return {"app_name": "unknown", "window_title": "Unknown", "pid": "0"}
        
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return {"app_name": "unknown", "window_title": "Unknown", "pid": "0"}
    
    def on_mouse_move(self, x, y):
        """Handle mouse movement."""
        current_time = datetime.now()

        # Initialize first position
        if not self.mouse_positions:
            self.mouse_positions.append({
                'x': x,
                'y': y,
                'timestamp': current_time.isoformat(),
                'velocity': 0
            })
            self.last_mouse_time = current_time
            return

        if self.last_mouse_time:
            time_delta = (current_time - self.last_mouse_time).total_seconds()
            if time_delta > 0:
                # Calculate velocity (pixels per second)
                last_x, last_y = self.mouse_positions[-1]['x'], self.mouse_positions[-1]['y']
                distance = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
                velocity = distance / time_delta if time_delta > 0 else 0

                self.mouse_velocity_samples.append(velocity)

                self.mouse_positions.append({
                    'x': x,
                    'y': y,
                    'timestamp': current_time.isoformat(),
                    'velocity': velocity
                })

            self.last_mouse_time = current_time
    
    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse clicks."""
        if pressed:
            self.mouse_clicks += 1
    
    def on_key_press(self, key):
        """Handle key presses."""
        current_time = datetime.now()
        self.key_press_count += 1
        
        if self.last_key_time:
            flight_time = (current_time - self.last_key_time).total_seconds() * 1000  # Convert to ms
            self.key_flight_times.append(flight_time)
        
        self.last_key_time = current_time
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate aggregated metrics from collected data.
        
        Returns:
            Dictionary with mouse and keyboard metrics
        """
        # Mouse metrics
        mouse_velocity_avg = sum(self.mouse_velocity_samples) / len(self.mouse_velocity_samples) if self.mouse_velocity_samples else 0
        mouse_velocity_std = (sum((v - mouse_velocity_avg) ** 2 for v in self.mouse_velocity_samples) / len(self.mouse_velocity_samples)) ** 0.5 if len(self.mouse_velocity_samples) > 1 else 0
        
        # Keyboard metrics
        flight_time_avg = sum(self.key_flight_times) / len(self.key_flight_times) if self.key_flight_times else 0
        flight_time_std = (sum((t - flight_time_avg) ** 2 for t in self.key_flight_times) / len(self.key_flight_times)) ** 0.5 if len(self.key_flight_times) > 1 else 0
        
        return {
            'mouse_velocity_avg': mouse_velocity_avg,
            'mouse_velocity_std': mouse_velocity_std,
            'mouse_click_count': self.mouse_clicks,
            'mouse_positions_count': len(self.mouse_positions),
            'keystroke_flight_avg_ms': flight_time_avg,
            'keystroke_flight_std_ms': flight_time_std,
            'keystroke_count': self.key_press_count,
        }
    
    def create_telemetry_payload(self) -> Dict:
        """Create JSON payload for API."""
        active_window = self.get_active_window()
        metrics = self.calculate_metrics()
        
        payload = {
            "user_id": self.user_id,
            "timestamp": datetime.now().isoformat(),
            "mouse": {
                "velocity_avg": metrics['mouse_velocity_avg'],
                "velocity_std": metrics['mouse_velocity_std'],
                "click_count": metrics['mouse_click_count'],
                "positions_count": metrics['mouse_positions_count'],
                "recent_positions": self.mouse_positions[-10:] if self.mouse_positions else []  # Last 10 positions
            },
            "keyboard": {
                "flight_time_avg_ms": metrics['keystroke_flight_avg_ms'],
                "flight_time_std_ms": metrics['keystroke_flight_std_ms'],
                "key_press_count": metrics['keystroke_count'],
            },
            "active_window": active_window,
            "session_id": f"session_{self.user_id}_{datetime.now().strftime('%Y%m%d')}",
        }
        
        return payload
    
    def send_telemetry(self):
        """Send telemetry data to API endpoint."""
        try:
            payload = self.create_telemetry_payload()
            
            if self.debug:
                logger.info(f"Sending telemetry: {json.dumps(payload, indent=2)}")
            else:
                response = requests.post(self.api_url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"Telemetry sent successfully. Risk: {response.json().get('risk_score', 'N/A')}")
                else:
                    logger.error(f"Failed to send telemetry: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error sending telemetry: {e}")
        
        finally:
            # Reset counters
            self.mouse_positions.clear()
            self.mouse_clicks = 0
            self.key_press_count = 0
            self.mouse_velocity_samples.clear()
            self.key_flight_times.clear()
    
    def telemetry_loop(self):
        """Main telemetry collection loop."""
        while self.running:
            self.send_telemetry()
            time.sleep(self.send_interval)
    
    def start(self):
        """Start the telemetry agent."""
        self.running = True

        # Start mouse listener
        self.mouse_listener = MouseListener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click
        )
        self.mouse_listener.start()

        # Start keyboard listener ONLY when keystroke tracking is consented to.
        # A global on_press hook is a keylogger; it stays off unless explicitly
        # enabled via track_keystrokes / UBA_TRACK_KEYSTROKES.
        if self.track_keystrokes:
            self.keyboard_listener = KeyboardListener(
                on_press=self.on_key_press
            )
            self.keyboard_listener.start()
            logger.info("Keystroke timing capture enabled (consent granted)")
        else:
            self.keyboard_listener = None
            logger.info(
                "Keystroke tracking disabled — no keyboard hook registered. "
                "Enable explicitly via track_keystrokes=True or UBA_TRACK_KEYSTROKES=1."
            )

        # Start telemetry loop in separate thread
        self.telemetry_thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.telemetry_thread.start()

        logger.info("Telemetry agent started")

    def stop(self):
        """Stop the telemetry agent."""
        self.running = False

        if self.mouse_listener:
            self.mouse_listener.stop()

        if self.keyboard_listener:
            self.keyboard_listener.stop()

        # Join the telemetry loop thread so it fully exits before we return.
        # The loop checks self.running and sleeps up to send_interval seconds,
        # so allow a little more than one interval before giving up.
        if self.telemetry_thread is not None and self.telemetry_thread.is_alive():
            self.telemetry_thread.join(timeout=self.send_interval + 2)
            if self.telemetry_thread.is_alive():
                logger.warning("Telemetry thread did not stop within timeout")

        logger.info("Telemetry agent stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vigilant Lens Telemetry Agent")
    parser.add_argument("--user-id", type=str, default="U001", help="User ID")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000/api/v1/telemetry/", help="API endpoint")
    parser.add_argument("--interval", type=int, default=5, help="Send interval in seconds")
    parser.add_argument("--debug", action="store_true", help="Debug mode (no API calls)")
    parser.add_argument(
        "--track-keystrokes",
        action="store_true",
        help="Enable keystroke-timing capture (global keyboard hook). "
             "OFF by default; requires explicit consent."
    )

    args = parser.parse_args()

    agent = TelemetryAgent(
        user_id=args.user_id,
        api_url=args.api_url,
        send_interval=args.interval,
        debug=args.debug,
        track_keystrokes=args.track_keystrokes
    )
    
    try:
        agent.start()
        print(f"Telemetry agent running for user {args.user_id}")
        print("Press Ctrl+C to stop")
        
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nStopping telemetry agent...")
        agent.stop()
    except Exception as e:
        logger.error(f"Error: {e}")
        agent.stop()


if __name__ == "__main__":
    main()
