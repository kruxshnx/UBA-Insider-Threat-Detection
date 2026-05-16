"""
Demo Activity Simulator
Simulates real employee activities for your demo.
Run this after starting employee_manager.py
"""

import requests
import time
import random
from datetime import datetime

API_URL = "http://localhost:8001"

# Sample data for simulation
EMPLOYEES = ["EMP001", "EMP002", "EMP003"]

APPLICATIONS = [
    ("Chrome", "Google Search"),
    ("VS Code", "main.py - Visual Studio Code"),
    ("Outlook", "Inbox - Outlook"),
    ("Excel", "Q4_Report.xlsx"),
    ("Slack", "#general - Slack"),
    ("Teams", "Meeting - Microsoft Teams"),
    ("File Explorer", "C:\\Confidential\\Data"),
    ("Zoom", "Team Meeting"),
]

ACTIVITIES = [
    "application_launch",
    "website_visit",
    "file_access",
    "file_copy",
    "email_send",
    "application_close",
]

def add_activity(employee_id, activity_type, app_name, title, risk_score=0.0):
    """Add an activity to the system."""
    try:
        response = requests.post(
            f"{API_URL}/activities/",
            json={
                "employee_id": employee_id,
                "activity_type": activity_type,
                "application": app_name,
                "title": title,
                "duration_seconds": random.randint(30, 600),
                "risk_score": risk_score
            }
        )
        if response.status_code == 200:
            print(f"✓ Activity added: {employee_id} - {activity_type}")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def simulate_normal_activity():
    """Simulate normal employee activities."""
    print("\n🎯 Simulating normal activities...")
    
    for _ in range(10):
        emp_id = random.choice(EMPLOYEES)
        activity_type = random.choice(ACTIVITIES)
        app, title = random.choice(APPLICATIONS)
        
        # Low risk score for normal activity
        add_activity(emp_id, activity_type, app, title, risk_score=random.uniform(0.05, 0.15))
        time.sleep(0.5)
    
    print("✓ Normal activities simulated\n")

def simulate_suspicious_activity():
    """Simulate suspicious employee activities."""
    print("\n⚠️  Simulating suspicious activities...")
    
    # Bulk file copy
    add_activity("EMP001", "file_bulk_copy", "File Explorer", 
                "Copying 50+ confidential files", risk_score=0.85)
    
    # After hours access
    add_activity("EMP001", "login", "Windows", 
                "After hours login - 11:30 PM", risk_score=0.65)
    
    # USB device
    add_activity("EMP001", "device_connect", "USB Controller", 
                "USB Device Connected", risk_score=0.70)
    
    # Multiple failed logins
    add_activity("EMP002", "failed_login", "Active Directory", 
                "5 failed login attempts", risk_score=0.75)
    
    # Large file download
    add_activity("EMP002", "file_download", "Chrome", 
                "Downloading 2GB+ from internal server", risk_score=0.80)
    
    print("✓ Suspicious activities simulated\n")

def simulate_employee_day():
    """Simulate a full day of employee activities."""
    print("\n📅 Simulating employee workday...")
    
    activities = [
        ("09:00", "EMP001", "login", "Windows", "User login", 0.0),
        ("09:15", "EMP001", "application_launch", "Outlook", "Checking emails", 0.0),
        ("10:00", "EMP001", "application_launch", "VS Code", "Development work", 0.0),
        ("11:00", "EMP002", "login", "Windows", "User login", 0.0),
        ("11:15", "EMP002", "application_launch", "Excel", "Spreadsheet work", 0.0),
        ("12:00", "EMP001", "website_visit", "Chrome", "Lunch break - YouTube", 0.1),
        ("14:00", "EMP001", "file_access", "File Explorer", "Project files", 0.0),
        ("15:00", "EMP002", "email_send", "Outlook", "Sending report", 0.0),
        ("16:00", "EMP003", "login", "Windows", "Admin login", 0.0),
        ("16:30", "EMP003", "file_copy", "File Explorer", "Bulk file operations", 0.6),
        ("17:00", "EMP001", "application_close", "VS Code", "End of day", 0.0),
    ]
    
    for time_str, emp_id, act_type, app, title, risk in activities:
        add_activity(emp_id, act_type, app, title, risk_score=risk)
        time.sleep(0.3)
    
    print("✓ Workday simulated\n")

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║          Employee Activity Simulator                     ║
    ║                                                          ║
    ║  This will simulate employee activities for demo         ║
    ║                                                          ║
    ║  Options:                                                ║
    ║  1. Normal activities                                    ║
    ║  2. Suspicious activities                                ║
    ║  3. Full day simulation                                  ║
    ║  4. All of the above                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == "1":
        simulate_normal_activity()
    elif choice == "2":
        simulate_suspicious_activity()
    elif choice == "3":
        simulate_employee_day()
    elif choice == "4":
        simulate_normal_activity()
        time.sleep(1)
        simulate_suspicious_activity()
        time.sleep(1)
        simulate_employee_day()
    else:
        print("Invalid choice!")
        return
    
    print("\n✅ Simulation complete! Check your dashboard at http://localhost:8001/docs")
    print("Or open dashboard.html in your browser to see live updates.\n")

if __name__ == "__main__":
    # Check if server is running
    try:
        response = requests.get(f"{API_URL}/dashboard/stats", timeout=2)
        if response.status_code == 200:
            print("✓ Connected to Employee Monitoring API")
            main()
        else:
            print(f"✗ Server returned: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server!")
        print("  Make sure employee_manager.py is running on port 8001")
        print("  Run: python employee_manager.py")
    except Exception as e:
        print(f"✗ Error: {e}")
