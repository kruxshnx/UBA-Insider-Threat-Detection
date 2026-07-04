"""
seed_demo_data.py — Reconcile the telemetry DB to the ML risk pipeline output.

Run from the repo root (after the backend has created the DB tables on startup,
or standalone — this script creates the tables it needs):

    python seed_demo_data.py

Single source of truth for user risk = the ML risk pipeline output at
``data/risk_output/risk_report_users.csv`` (which correctly ranks the injected
insider **U105 as #1**). This script:

  - CLEARS and repopulates the ``users`` table from the pipeline output joined
    with ``data/raw/users.csv`` (for role / department). ALL 100 pipeline users
    are seeded so ``total_users`` (100) is consistent everywhere.
  - Scales each user's ``total_risk_score`` into a 0-100 ``risk_score`` such that
    **U105 is the clear, strict maximum** (~97) while preserving the pipeline's
    relative ordering. ``risk_level`` follows Critical/High/Medium/Low thresholds.
  - Generates DETERMINISTIC faker names for every user (RNG seeded), but pins
    U105 to name "Insider Threat Actor" and department "Finance".
  - Populates plausible live-session fields (productivity_score, last_seen,
    active_app, event_count) so the dashboard looks alive — high-risk users get
    lower productivity, and most users' ``last_seen`` is within the last hour so
    some render as "Active".
  - Seeds deterministic ``telemetry_raw`` rows (respecting the real schema incl.
    mitre_tactic / mitre_technique) so the heatmap / recent / hourly endpoints
    return non-empty, realistic data. U105 gets after-hours, high-risk activity
    on suspicious apps so the heatmap highlights it.

Idempotent: safe to re-run (it clears both tables first). Deterministic: the RNG
and Faker are seeded, so re-runs produce identical data.

Dependencies: Python stdlib + pandas (+ Faker for names; a deterministic
fallback name generator is used if Faker is unavailable).
"""
import math
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join("data", "telemetry.db")
RISK_USERS_CSV = os.path.join("data", "risk_output", "risk_report_users.csv")
RAW_USERS_CSV = os.path.join("data", "raw", "users.csv")

# ── Determinism ───────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)

# Faker for deterministic human names, with a stdlib fallback so the script keeps
# working (and stays deterministic) if Faker is not installed.
try:
    from faker import Faker

    _faker = Faker()
    Faker.seed(SEED)

    def _make_name() -> str:
        return _faker.name()
except Exception:  # pragma: no cover - fallback path
    _FIRST = [
        "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
        "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
        "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Priya",
        "Wei", "Amina", "Diego", "Yuki", "Omar", "Ingrid", "Kwame", "Sofia",
        "Ravi",
    ]
    _LAST = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Patel", "Chen", "Okafor", "Rivera", "Nakamura", "Haddad", "Larsen",
        "Mensah", "Rossi", "Kapoor",
    ]

    def _make_name() -> str:
        return f"{random.choice(_FIRST)} {random.choice(_LAST)}"


# ── Special (injected insider) user ───────────────────────────────────────────
INSIDER_ID = "U105"
INSIDER_NAME = "Insider Threat Actor"
INSIDER_DEPT = "Finance"

# Target ceiling for the top threat after scaling (strictly the maximum, Critical)
INSIDER_TARGET_SCORE = 97.0

# ── App catalogues ────────────────────────────────────────────────────────────
ROLE_APPS = {
    "Admin":      ["powershell.exe", "taskmgr.exe", "cmd.exe", "chrome.exe", "explorer.exe"],
    "Developer":  ["code.exe", "chrome.exe", "pycharm64.exe", "terminal.exe", "git.exe"],
    "HR":         ["outlook.exe", "chrome.exe", "excel.exe", "word.exe", "teams.exe"],
    "Manager":    ["outlook.exe", "teams.exe", "chrome.exe", "excel.exe", "powerpoint.exe"],
    "Analyst":    ["excel.exe", "chrome.exe", "python.exe", "tableau.exe", "outlook.exe"],
    "Contractor": ["chrome.exe", "outlook.exe", "vpnclient.exe", "excel.exe", "teams.exe"],
    "Employee":   ["chrome.exe", "outlook.exe", "word.exe", "slack.exe", "teams.exe"],
}
DEFAULT_APPS = ROLE_APPS["Employee"]

# Apps an insider uses to stage / exfiltrate data (drive MITRE mapping).
SUSPICIOUS_APPS = ["telegram.exe", "dropbox.exe", "7zip.exe", "winscp.exe", "powershell.exe"]


# ── MITRE ATT&CK mapping (mirrors src/api/routers/telemetry.py logic) ─────────
_MITRE_APP_MAP = [
    ({"telegram", "signal", "whatsapp"}, ("TA0010", "T1048")),
    ({"dropbox", "googledrive", "onedrive", "mega", "wetransfer"}, ("TA0010", "T1567")),
    ({"7zip", "winrar", "winzip"}, ("TA0009", "T1560")),
    ({"powershell", "cmd.exe", "bash", "terminal", "wscript", "cscript"}, ("TA0002", "T1059")),
    ({"taskmgr", "processhacker", "procmon", "wireshark"}, ("TA0005", "T1562")),
    ({"keepass", "lastpass", "1password", "bitwarden"}, ("TA0006", "T1555")),
    ({"putty", "mobaxterm", "winscp", "filezilla"}, ("TA0008", "T1021")),
]


def _mitre_for(active_app: str, risk_score: float, hour: int):
    """Return (tactic, technique) for a telemetry event, mirroring the router."""
    app = (active_app or "").lower()
    for keywords, mapping in _MITRE_APP_MAP:
        if any(k in app for k in keywords):
            return mapping
    is_after_hours = hour < 8 or hour > 20
    if is_after_hours and risk_score >= 60:
        return ("TA0003", "T1078")  # Persistence — Valid Accounts
    if risk_score >= 80:
        return ("TA0009", "T1119")  # Collection — Automated Collection
    return (None, None)


# ── Load & join pipeline output ───────────────────────────────────────────────
def load_pipeline_users() -> pd.DataFrame:
    """Load pipeline risk output joined with raw role/department metadata."""
    if not os.path.exists(RISK_USERS_CSV):
        sys.stderr.write(
            "\nERROR: risk pipeline output not found at "
            f"'{RISK_USERS_CSV}'.\n"
            "Run the ML risk pipeline first to generate it, then re-run "
            "this seeder.\n\n"
        )
        sys.exit(1)

    risk = pd.read_csv(RISK_USERS_CSV, encoding="utf-8")
    if "user" not in risk.columns or "total_risk_score" not in risk.columns:
        sys.stderr.write(
            f"\nERROR: '{RISK_USERS_CSV}' is missing required columns "
            "('user', 'total_risk_score'). Re-run the risk pipeline.\n\n"
        )
        sys.exit(1)

    risk["total_risk_score"] = pd.to_numeric(
        risk["total_risk_score"], errors="coerce"
    ).fillna(0.0)

    # Join role / department from raw users (id, role, dept, pc).
    if os.path.exists(RAW_USERS_CSV):
        raw = pd.read_csv(RAW_USERS_CSV, encoding="utf-8")
        raw = raw.rename(columns={"id": "user", "dept": "department"})
        keep = [c for c in ("user", "role", "department") if c in raw.columns]
        risk = risk.merge(raw[keep], on="user", how="left")

    if "role" not in risk.columns:
        risk["role"] = "Employee"
    if "department" not in risk.columns:
        risk["department"] = "General"
    risk["role"] = risk["role"].fillna("Employee")
    risk["department"] = risk["department"].fillna("General")

    return risk


def scale_risk(total_risk_score: float, max_score: float) -> float:
    """Scale pipeline total_risk_score into 0-100 with U105 pinned near the top.

    Linear map so the pipeline max (U105 ~= 146.86) lands at
    INSIDER_TARGET_SCORE (~97). Relative ordering is preserved and no other user
    can equal or exceed U105 (they all have strictly smaller totals).
    """
    if max_score <= 0:
        return 0.0
    scaled = (total_risk_score / max_score) * INSIDER_TARGET_SCORE
    return round(max(0.0, min(100.0, scaled)), 2)


def risk_level(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


# ── Schema helpers (do NOT change the schema — just ensure it exists) ─────────
def ensure_tables(cursor) -> None:
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
        mitre_tactic TEXT,
        mitre_technique TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # Back-fill MITRE columns for older databases (mirrors database.py migration).
    for col in ("mitre_tactic", "mitre_technique"):
        try:
            cursor.execute(f"ALTER TABLE telemetry_raw ADD COLUMN {col} TEXT")
        except Exception:
            pass  # column already exists


# ── Telemetry event generation ────────────────────────────────────────────────
def _pick_apps(role: str):
    return ROLE_APPS.get(role, DEFAULT_APPS)


def make_event(user_id, name, role, base_score, ts, is_anomalous):
    """Build one telemetry_raw row dict for a user at a given timestamp."""
    hour = ts.hour
    after_hours = hour < 8 or hour > 20
    time_multiplier = 1.4 if after_hours else 1.0

    if is_anomalous:
        active_app = random.choice(SUSPICIOUS_APPS)
        risk_boost = random.uniform(25, 45)
        mouse_velocity_avg = random.uniform(5, 50)
        keystroke_flight_avg = random.uniform(300, 800)
    else:
        active_app = random.choice(_pick_apps(role))
        risk_boost = 0.0
        mouse_velocity_avg = random.uniform(80, 400)
        keystroke_flight_avg = random.uniform(80, 250)

    variability = random.uniform(-8, 8)
    raw_risk = (base_score + variability + risk_boost) * time_multiplier
    risk_score = round(max(0.0, min(100.0, raw_risk)), 2)

    anomaly_score = round(risk_score / 100.0, 4)
    productivity = round(
        max(0.05, min(1.0, 1.0 - (risk_score / 120.0) + random.uniform(-0.1, 0.1))),
        3,
    )
    mitre_tactic, mitre_technique = _mitre_for(active_app, risk_score, hour)

    return {
        "timestamp": ts.isoformat(),
        "user_id": user_id,
        "session_id": f"sess_{user_id}_{ts.strftime('%Y%m%d%H')}",
        "mouse_velocity_avg": round(mouse_velocity_avg, 2),
        "mouse_velocity_std": round(random.uniform(20, 120), 2),
        "mouse_click_count": random.randint(5, 80),
        "mouse_positions_count": random.randint(50, 500),
        "keystroke_flight_avg_ms": round(keystroke_flight_avg, 2),
        "keystroke_flight_std_ms": round(random.uniform(20, 80), 2),
        "keystroke_count": random.randint(20, 300),
        "active_app": active_app,
        "window_title": f"{active_app} - {name}",
        "process_id": str(random.randint(1000, 9999)),
        "risk_score": risk_score,
        "risk_multiplier": round(time_multiplier, 2),
        "productivity_score": productivity,
        "anomaly_score": anomaly_score,
        "mitre_tactic": mitre_tactic,
        "mitre_technique": mitre_technique,
    }


def build_events(user_records, now):
    """Generate deterministic telemetry events for all users.

    Every user gets recent activity (within the last hour for some, spread over
    the last 7 days for the rest) so the heatmap / recent / hourly endpoints are
    non-empty. U105 gets extra after-hours, suspicious-app, high-risk events.
    """
    events = []
    for rec in user_records:
        uid = rec["user_id"]
        name = rec["name"]
        role = rec["role"]
        base = rec["risk_score"]
        is_insider = uid == INSIDER_ID

        n_events = 40 if is_insider else random.randint(12, 22)

        for i in range(n_events):
            if is_insider:
                # Insider: concentrated in the last 3 days, mostly after-hours.
                days_ago = random.uniform(0, 3)
                ts = now - timedelta(days=days_ago)
                # Force many events into after-hours (late night / early morning).
                if random.random() < 0.7:
                    ts = ts.replace(hour=random.choice([1, 2, 3, 22, 23]),
                                    minute=random.randint(0, 59))
                is_anom = random.random() < 0.75
            else:
                # Ensure the first event for each user is very recent (last hour)
                # so some users show as "Active"; the rest spread over 7 days.
                if i == 0:
                    ts = now - timedelta(minutes=random.randint(1, 55))
                else:
                    ts = now - timedelta(
                        days=random.uniform(0, 7),
                        hours=random.uniform(0, 23),
                    )
                is_anom = base > 40 and random.random() < 0.25

            events.append(make_event(uid, name, role, base, ts, is_anom))

    events.sort(key=lambda e: e["timestamp"])
    return events


# ── Main seeding routine ──────────────────────────────────────────────────────
def seed():
    os.makedirs("data", exist_ok=True)

    pipeline = load_pipeline_users()
    max_score = float(pipeline["total_risk_score"].max())
    now = datetime.now()

    # Build per-user records (deterministic order = pipeline CSV order).
    user_records = []
    used_emails = set()
    for _, row in pipeline.iterrows():
        uid = str(row["user"])
        total = float(row["total_risk_score"])
        score = scale_risk(total, max_score)

        if uid == INSIDER_ID:
            name = INSIDER_NAME
            department = INSIDER_DEPT
            score = INSIDER_TARGET_SCORE  # pin insider strictly at the top
        else:
            name = _make_name()
            department = str(row.get("department") or "General")

        role = str(row.get("role") or "Employee")

        # Deterministic, unique email derived from the user id.
        email = f"{uid.lower()}@company.com"
        if email in used_emails:  # extremely unlikely; guard anyway
            email = f"{uid.lower()}.{len(used_emails)}@company.com"
        used_emails.add(email)

        # Productivity: lower for higher-risk users, deterministic jitter.
        productivity = round(
            max(0.05, min(1.0, 1.0 - (score / 130.0) + random.uniform(-0.08, 0.08))),
            3,
        )

        # last_seen: keep most users recent (within the last hour) so some show
        # "Active"; give a slice older timestamps for realism.
        if random.random() < 0.65:
            last_seen = (now - timedelta(minutes=random.randint(1, 58))).isoformat()
        else:
            last_seen = (now - timedelta(hours=random.randint(2, 72))).isoformat()

        apps = _pick_apps(role)
        active_app = random.choice(SUSPICIOUS_APPS) if uid == INSIDER_ID else random.choice(apps)

        user_records.append({
            "user_id": uid,
            "name": name,
            "email": email,
            "role": role,
            "department": department,
            "risk_score": score,
            "risk_level": risk_level(score),
            "productivity_score": productivity,
            "last_seen": last_seen,
            "active_app": active_app,
        })

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ensure_tables(cursor)
    conn.commit()

    # ── Idempotent reset ──────────────────────────────────────────────────────
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM telemetry_raw")
    conn.commit()

    # ── Insert users ──────────────────────────────────────────────────────────
    created_at = now.isoformat()
    cursor.executemany("""
        INSERT INTO users (
            user_id, name, email, role, department, created_at,
            is_active, last_seen, risk_score, productivity_score
        ) VALUES (
            :user_id, :name, :email, :role, :department, :created_at,
            1, :last_seen, :risk_score, :productivity_score
        )
    """, [dict(r, created_at=created_at) for r in user_records])
    conn.commit()

    top = max(user_records, key=lambda r: r["risk_score"])
    print(f"Users: {len(user_records)} seeded from pipeline output")
    print(f"   Top threat: {top['user_id']} ({top['name']}) "
          f"risk_score={top['risk_score']} level={top['risk_level']}")

    # ── Insert telemetry events ───────────────────────────────────────────────
    events = build_events(user_records, now)
    cursor.executemany("""
        INSERT INTO telemetry_raw (
            timestamp, user_id, session_id,
            mouse_velocity_avg, mouse_velocity_std, mouse_click_count, mouse_positions_count,
            keystroke_flight_avg_ms, keystroke_flight_std_ms, keystroke_count,
            active_app, window_title, process_id,
            risk_score, risk_multiplier, productivity_score, anomaly_score,
            mitre_tactic, mitre_technique
        ) VALUES (
            :timestamp, :user_id, :session_id,
            :mouse_velocity_avg, :mouse_velocity_std, :mouse_click_count, :mouse_positions_count,
            :keystroke_flight_avg_ms, :keystroke_flight_std_ms, :keystroke_count,
            :active_app, :window_title, :process_id,
            :risk_score, :risk_multiplier, :productivity_score, :anomaly_score,
            :mitre_tactic, :mitre_technique
        )
    """, events)
    conn.commit()
    print(f"Telemetry: {len(events)} events inserted")

    # ── Refresh users.active_app-adjacent context via last event (optional) ───
    # The users table has no active_app column (schema stays unchanged); the
    # /users/ endpoint derives last_active_app from the latest telemetry row,
    # which now exists for every user.

    conn.close()

    print()
    print("=" * 64)
    print("Telemetry DB reconciled to the ML risk pipeline.")
    print(f"   total_users = {len(user_records)} (matches pipeline)")
    print(f"   top_threat  = {top['user_id']} (unambiguous maximum)")
    print("=" * 64)


if __name__ == "__main__":
    seed()
