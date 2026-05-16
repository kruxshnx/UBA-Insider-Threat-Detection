"""
Synthetic Data Generator for UBA & Insider Threat Detection.

Generates synthetic user-activity logs (logon, file, HTTP, device)
with configurable insider-threat scenarios injected.

All parameters (user count, simulation duration, threat scenarios)
are read from config.yaml rather than being hardcoded.
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
import logging
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config
from .schema import LogonEvent, FileEvent, HttpEvent, DeviceEvent

logger = logging.getLogger("uba.data_pipeline.generator")

# Initialize Faker with deterministic seed
fake = Faker()
Faker.seed(42)
np.random.seed(42)

# Robust path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
os.makedirs(DATA_DIR, exist_ok=True)

# ── Configuration-driven parameters ──────────────────────────────────────────
data_gen_cfg = config.get('data_generation', {})
NUM_USERS = data_gen_cfg.get('num_users', 100)
DAYS_TO_SIMULATE = data_gen_cfg.get('days_to_simulate', 30)
START_DATE = datetime(2024, 1, 1)

# Threat scenario settings
INSIDER_THREAT_USER = data_gen_cfg.get('insider_threat_user', 'U105')
INSIDER_THREAT_START_DAY = data_gen_cfg.get('insider_threat_start_day', 25)

# Work-hour definition
features_cfg = config.get('features', {})
WORK_START_HOUR = features_cfg.get('work_start_hour', 7)
WORK_END_HOUR = features_cfg.get('work_end_hour', 20)

# ── User Personas ────────────────────────────────────────────────────────────
users = []
for i in range(NUM_USERS):
    role = np.random.choice(["Employee", "Admin", "Contractor"], p=[0.8, 0.1, 0.1])
    users.append({
        "id": f"U{100+i}",
        "role": role,
        "dept": fake.job(),
        "pc": f"PC-{100+i}"
    })


def generate_noise_time(date, role):
    """Generate a timestamp based on role (normal hours vs random)."""
    if role == "Employee" and random.random() > 0.05:
        start_hour = (WORK_START_HOUR - 1) + random.random() * 2
        return date + timedelta(hours=start_hour)
    else:
        return date + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))


def generate_daily_logs():
    """Generate synthetic daily activity logs with injected threat scenarios."""
    logon_logs = []
    file_logs = []
    http_logs = []
    device_logs = []

    current_date = START_DATE
    event_id_counter = 0

    logger.info(
        "Generating data: %d users, %d days, threat_user=%s (day>%d)",
        NUM_USERS, DAYS_TO_SIMULATE, INSIDER_THREAT_USER, INSIDER_THREAT_START_DAY,
    )

    for day in range(DAYS_TO_SIMULATE):
        date = current_date + timedelta(days=day)

        # Skip weekends for most users
        if date.weekday() >= 5 and random.random() > 0.1:
            continue

        for user in users:
            uid = user['id']
            pc = user['pc']
            role = user['role']

            # 1. Logon Event
            login_time = generate_noise_time(date, role)
            logout_time = login_time + timedelta(hours=8 + random.gauss(0, 1))

            logon_logs.append([f"E{event_id_counter}", uid, login_time, pc, "Logon"])
            event_id_counter += 1
            logon_logs.append([f"E{event_id_counter}", uid, logout_time, pc, "Logoff"])
            event_id_counter += 1

            # 2. File Activity (Normal)
            for _ in range(random.randint(0, 5)):
                f_time = login_time + timedelta(minutes=random.randint(10, 400))
                fname = fake.file_name()
                action = "File Open"
                file_logs.append([f"E{event_id_counter}", uid, f_time, pc, fname, action, False])
                event_id_counter += 1

            # Scenario: Data Exfiltration — config-driven insider threat
            if uid == INSIDER_THREAT_USER and day > INSIDER_THREAT_START_DAY:
                for _ in range(20):
                    f_time = logout_time + timedelta(minutes=random.randint(-30, 0))
                    fname = f"CONFIDENTIAL_{fake.word()}.pdf"
                    file_logs.append([f"E{event_id_counter}", uid, f_time, pc, fname, "File Copy", True])
                    event_id_counter += 1
                device_logs.append([f"E{event_id_counter}", uid, f_time - timedelta(minutes=5), pc, "Connect"])

            # 3. HTTP Activity
            for _ in range(random.randint(5, 20)):
                h_time = login_time + timedelta(minutes=random.randint(0, 480))
                url = fake.url()
                http_logs.append([f"E{event_id_counter}", uid, h_time, pc, url, ""])
                event_id_counter += 1

    # Save to CSV
    logger.info("Saving CSVs to %s", DATA_DIR)
    pd.DataFrame(logon_logs, columns=["id", "user", "date", "pc", "activity"]).to_csv(
        f"{DATA_DIR}/logon.csv", index=False
    )
    pd.DataFrame(file_logs, columns=["id", "user", "date", "pc", "filename", "activity", "to_removable_media"]).to_csv(
        f"{DATA_DIR}/file.csv", index=False
    )
    pd.DataFrame(http_logs, columns=["id", "user", "date", "pc", "url", "content"]).to_csv(
        f"{DATA_DIR}/http.csv", index=False
    )
    pd.DataFrame(device_logs, columns=["id", "user", "date", "pc", "activity"]).to_csv(
        os.path.join(DATA_DIR, "device.csv"), index=False
    )

    # Save Users Metadata for Risk Engine
    pd.DataFrame(users).to_csv(os.path.join(DATA_DIR, "users.csv"), index=False)
    logger.info("Data generation complete. %d total events generated.", event_id_counter)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_daily_logs()
