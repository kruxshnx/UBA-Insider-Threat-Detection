"""
seed_demo_data.py — Seed the database with demo users + realistic telemetry events.

Run ONCE after the backend has started (it creates the DB tables on startup):
    python seed_demo_data.py

This populates:
  - 10 employees with realistic roles/departments
  - 500 telemetry events spread across the last 7 days
  - Varying risk profiles: low, medium, high, critical
"""
import sqlite3
import random
import math
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join("data", "telemetry.db")

DEMO_USERS = [
    {"user_id": "admin",  "name": "System Administrator", "email": "admin@company.com",      "role": "Admin",     "department": "IT"},
    {"user_id": "U001",   "name": "John Doe",             "email": "john.doe@company.com",    "role": "Developer", "department": "Engineering"},
    {"user_id": "U002",   "name": "Jane Smith",           "email": "jane.smith@company.com",  "role": "HR",        "department": "Human Resources"},
    {"user_id": "U003",   "name": "Bob Wilson",           "email": "bob.wilson@company.com",  "role": "Manager",   "department": "Sales"},
    {"user_id": "U004",   "name": "Alice Chen",           "email": "alice.chen@company.com",  "role": "Developer", "department": "Engineering"},
    {"user_id": "U005",   "name": "Carlos Rivera",        "email": "carlos.r@company.com",    "role": "Analyst",   "department": "Finance"},
    {"user_id": "U006",   "name": "Sarah Lee",            "email": "sarah.lee@company.com",   "role": "Employee",  "department": "Operations"},
    {"user_id": "U007",   "name": "Mark Thompson",        "email": "mark.t@company.com",      "role": "Developer", "department": "Engineering"},
    {"user_id": "U008",   "name": "Priya Patel",          "email": "priya.p@company.com",     "role": "Employee",  "department": "Marketing"},
    {"user_id": "U009",   "name": "David Kim",            "email": "david.k@company.com",     "role": "Manager",   "department": "Operations"},
    {"user_id": "U105",   "name": "Insider Threat Actor", "email": "u105@company.com",        "role": "Employee",  "department": "Finance"},
]

ROLE_APPS = {
    "Admin":     ["powershell.exe", "taskmgr.exe", "cmd.exe", "chrome.exe", "explorer.exe"],
    "Developer": ["code.exe", "chrome.exe", "pycharm64.exe", "terminal.exe", "git.exe"],
    "HR":        ["outlook.exe", "chrome.exe", "excel.exe", "word.exe", "teams.exe"],
    "Manager":   ["outlook.exe", "teams.exe", "chrome.exe", "excel.exe", "powerpoint.exe"],
    "Analyst":   ["excel.exe", "chrome.exe", "python.exe", "tableau.exe", "outlook.exe"],
    "Employee":  ["chrome.exe", "outlook.exe", "word.exe", "slack.exe", "teams.exe"],
}

SUSPICIOUS_APPS = ["usb_transfer.exe", "7zip.exe", "dropbox.exe", "telegram.exe", "tor.exe"]

def risk_profile_for_user(user_id):
    """Return (base_risk, risk_variability) for each user."""
    profiles = {
        "admin": (20, 15),
        "U001":  (15, 10),
        "U002":  (18, 12),
        "U003":  (22, 14),
        "U004":  (16, 10),
        "U005":  (25, 15),
        "U006":  (12, 8),
        "U007":  (14, 10),
        "U008":  (10, 6),
        "U009":  (20, 12),
        "U105":  (65, 30),   # High-risk insider threat user
    }
    return profiles.get(user_id, (15, 10))


def generate_telemetry_event(user, ts, is_anomalous=False):
    role = user["role"]
    user_id = user["user_id"]
    base_risk, variability = risk_profile_for_user(user_id)

    apps = ROLE_APPS.get(role, ROLE_APPS["Employee"])
    if is_anomalous and random.random() < 0.4:
        active_app = random.choice(SUSPICIOUS_APPS)
        risk_boost = random.uniform(20, 45)
    else:
        active_app = random.choice(apps)
        risk_boost = 0

    hour = ts.hour
    after_hours = hour < 7 or hour > 20
    time_multiplier = 1.4 if after_hours else 1.0

    mouse_velocity_avg = random.uniform(80, 400) if not is_anomalous else random.uniform(5, 50)
    mouse_velocity_std = random.uniform(20, 120)
    keystroke_flight_avg = random.uniform(80, 250) if not is_anomalous else random.uniform(300, 800)
    keystroke_flight_std = random.uniform(20, 80)

    raw_risk = (base_risk + random.uniform(-variability, variability) + risk_boost) * time_multiplier
    risk_score = max(0, min(100, raw_risk))

    anomaly_score = risk_score / 100.0
    productivity = max(0.1, 1.0 - (risk_score / 120.0) + random.uniform(-0.1, 0.1))

    return {
        "timestamp": ts.isoformat(),
        "user_id": user_id,
        "session_id": f"sess_{user_id}_{ts.strftime('%Y%m%d%H')}",
        "mouse_velocity_avg": round(mouse_velocity_avg, 2),
        "mouse_velocity_std": round(mouse_velocity_std, 2),
        "mouse_click_count": random.randint(5, 80),
        "mouse_positions_count": random.randint(50, 500),
        "keystroke_flight_avg_ms": round(keystroke_flight_avg, 2),
        "keystroke_flight_std_ms": round(keystroke_flight_std, 2),
        "keystroke_count": random.randint(20, 300),
        "active_app": active_app,
        "window_title": f"{active_app} - {user['name']}",
        "process_id": str(random.randint(1000, 9999)),
        "risk_score": round(risk_score, 2),
        "risk_multiplier": round(time_multiplier, 2),
        "productivity_score": round(productivity, 3),
        "anomaly_score": round(anomaly_score, 4),
    }


def seed():
    if not os.path.exists("data"):
        os.makedirs("data")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Ensure users table exists ────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT DEFAULT 'Employee',
        department TEXT DEFAULT 'General',
        created_at TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        manager_id TEXT,
        last_seen TEXT,
        risk_score REAL DEFAULT 0.0,
        productivity_score REAL DEFAULT 1.0
    )""")

    # ── Ensure telemetry table exists ────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user_id TEXT NOT NULL,
        session_id TEXT,
        mouse_velocity_avg REAL,
        mouse_velocity_std REAL,
        mouse_click_count INTEGER,
        mouse_positions_count INTEGER,
        keystroke_flight_avg_ms REAL,
        keystroke_flight_std_ms REAL,
        keystroke_count INTEGER,
        active_app TEXT,
        window_title TEXT,
        process_id TEXT,
        risk_score REAL,
        risk_multiplier REAL,
        productivity_score REAL,
        anomaly_score REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()

    # ── Insert users ─────────────────────────────────────────────────────────
    inserted_users = 0
    for user in DEMO_USERS:
        try:
            cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, name, email, role, department, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (user["user_id"], user["name"], user["email"],
                  user["role"], user["department"], datetime.now().isoformat()))
            if cursor.rowcount > 0:
                inserted_users += 1
        except Exception as e:
            print(f"  [skip] {user['user_id']}: {e}")

    conn.commit()
    print(f"✓ Users: {inserted_users} new, {len(DEMO_USERS) - inserted_users} already exist")

    # ── Generate telemetry events ─────────────────────────────────────────────
    now = datetime.now()
    events = []
    for user in DEMO_USERS:
        uid = user["user_id"]
        base_risk, _ = risk_profile_for_user(uid)
        events_per_user = 60 if uid == "U105" else random.randint(30, 50)

        for i in range(events_per_user):
            days_ago = random.uniform(0, 7)
            ts = now - timedelta(days=days_ago)
            # Avoid weekend nights for normal users
            is_anomalous = (uid == "U105" and days_ago < 2) or (base_risk > 40 and random.random() < 0.3)
            events.append(generate_telemetry_event(user, ts, is_anomalous))

    # Sort by timestamp
    events.sort(key=lambda x: x["timestamp"])

    cursor.executemany("""
    INSERT INTO telemetry_raw (
        timestamp, user_id, session_id,
        mouse_velocity_avg, mouse_velocity_std, mouse_click_count, mouse_positions_count,
        keystroke_flight_avg_ms, keystroke_flight_std_ms, keystroke_count,
        active_app, window_title, process_id,
        risk_score, risk_multiplier, productivity_score, anomaly_score
    ) VALUES (
        :timestamp, :user_id, :session_id,
        :mouse_velocity_avg, :mouse_velocity_std, :mouse_click_count, :mouse_positions_count,
        :keystroke_flight_avg_ms, :keystroke_flight_std_ms, :keystroke_count,
        :active_app, :window_title, :process_id,
        :risk_score, :risk_multiplier, :productivity_score, :anomaly_score
    )
    """, events)

    conn.commit()
    print(f"✓ Telemetry: {len(events)} events inserted")

    # ── Update user risk scores from latest telemetry ─────────────────────────
    for user in DEMO_USERS:
        uid = user["user_id"]
        cursor.execute("""
        SELECT AVG(risk_score), AVG(productivity_score), MAX(timestamp)
        FROM telemetry_raw WHERE user_id = ?
        """, (uid,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            cursor.execute("""
            UPDATE users SET risk_score = ?, productivity_score = ?, last_seen = ?
            WHERE user_id = ?
            """, (round(row[0], 2), round(row[1], 3), row[2], uid))

    conn.commit()
    conn.close()

    print(f"✓ User risk scores updated")
    print()
    print("=" * 60)
    print("Demo data seeded successfully!")
    print("  Backend : python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload")
    print("  Frontend: cd website && npm run dev")
    print("  Agent   : python -m src.telemetry.agent --user-id U001")
    print("=" * 60)


if __name__ == "__main__":
    seed()
