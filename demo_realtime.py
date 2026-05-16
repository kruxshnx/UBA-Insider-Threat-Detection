"""
Real-time UBA Demo for Mentor Presentation

This script demonstrates real-time behavioral biometrics collection:
- Mouse velocity tracking
- Keystroke timing
- Active window detection
- Risk score calculation
"""

import time
import json
from datetime import datetime
from src.telemetry.agent import TelemetryAgent
from src.telemetry.integrity_engine import integrity_engine
from src.telemetry.database import telemetry_db

def demo_realtime_telemetry(user_id: str = "DemoUser", duration: int = 30):
    """
    Demo real-time telemetry collection with live risk scores.
    
    Args:
        user_id: User ID to track
        duration: Demo duration in seconds
    """
    print("=" * 70)
    print("REAL-TIME UBA DEMO - Behavioral Biometrics Monitoring")
    print("=" * 70)
    print(f"User: {user_id}")
    print(f"Duration: {duration} seconds")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\nInstructions:")
    print("- Move your mouse normally")
    print("- Type on your keyboard")
    print("- Switch between applications")
    print("- Watch the real-time risk scores update!\n")
    print("-" * 70)
    
    agent = TelemetryAgent(user_id=user_id, send_interval=3, debug=True)
    
    try:
        agent.start()
        print("\nTelemetry agent started...")
        print("\nLive telemetry data (updating every 3 seconds):\n")
        
        start_time = time.time()
        iteration = 0
        
        while time.time() - start_time < duration:
            iteration += 1
            metrics = agent.calculate_metrics()
            active_window = agent.get_active_window()
            
            # Simulate integrity engine calculation
            telemetry_data = {
                'active_app': active_window.get('app_name', 'unknown'),
                'mouse_velocity_avg': metrics.get('mouse_velocity_avg', 0),
                'mouse_velocity_std': metrics.get('mouse_velocity_std', 0),
                'keystroke_flight_avg_ms': metrics.get('keystroke_flight_avg_ms', 0),
                'keystroke_flight_std_ms': metrics.get('keystroke_flight_std_ms', 0),
            }
            
            # Calculate risk (simplified for demo)
            risk_score = min(100, (
                (telemetry_data['mouse_velocity_avg'] / 100) * 20 +  # Mouse speed contribution
                (telemetry_data['keystroke_flight_avg_ms'] / 10) * 5 +  # Keystroke contribution
                (iteration % 5) * 2  # Small variation
            ))
            
            productivity = 1.0 if any(app in active_window.get('app_name', '').lower() 
                                     for app in ['code', 'vscode', 'python', 'terminal', 'pycharm']) else 0.5
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteration {iteration}")
            print(f"  Active App: {active_window.get('app_name', 'Unknown')}")
            print(f"  Window: {active_window.get('window_title', 'Unknown')[:50]}...")
            print(f"  Mouse Velocity: {metrics.get('mouse_velocity_avg', 0):.1f} px/s")
            print(f"  Keystroke Flight: {metrics.get('keystroke_flight_avg_ms', 0):.1f} ms")
            print(f"  Productivity: {productivity:.1f}")
            print(f"  Risk Score: {risk_score:.1f}/100")
            
            # Risk level indicator
            if risk_score < 30:
                print(f"  Status: [NORMAL]")
            elif risk_score < 60:
                print(f"  Status: [ELEVATED]")
            else:
                print(f"  Status: [HIGH RISK]")
            
            print("-" * 70)
            
            # Reset for next iteration
            agent.mouse_positions.clear()
            agent.mouse_clicks = 0
            agent.key_press_count = 0
            agent.mouse_velocity_samples.clear()
            agent.key_flight_times.clear()
            
            time.sleep(3)
        
        print(f"\n{'=' * 70}")
        print("DEMO COMPLETE")
        print(f"{'=' * 70}")
        print(f"Total iterations: {iteration}")
        print("\nThis demonstrates real-time behavioral biometrics collection!")
        print("The system tracks mouse movement, keystroke timing, and app usage.")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    finally:
        agent.stop()
        print("Telemetry agent stopped.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time UBA Demo")
    parser.add_argument("--user-id", type=str, default="DemoUser", help="User ID")
    parser.add_argument("--duration", type=int, default=30, help="Demo duration (seconds)")
    
    args = parser.parse_args()
    
    demo_realtime_telemetry(user_id=args.user_id, duration=args.duration)
