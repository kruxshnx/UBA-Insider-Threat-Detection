import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os
import sys

# Add parent directory for potential imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Initialize Faker
fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

# Configuration
NUM_USERS = 50
DAYS_TO_SIMULATE = 90  # 3 months for ~10k records
START_DATE = datetime(2024, 1, 1)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data/cert_r4.2")
os.makedirs(DATA_DIR, exist_ok=True)

def generate_users(num_users):
    users = []
    roles = ["Sales", "IT", "HR", "Engineering", "Finance", "Executive"]
    
    for i in range(num_users):
        user_id = f"U{100+i}"
        role = np.random.choice(roles, p=[0.3, 0.2, 0.1, 0.25, 0.1, 0.05])
        
        # Assign risk profile (0 = Normal, 1 = Insider Threat)
        # We'll make U105 and U120 malicious
        is_malicious = False
        if user_id in ["U105", "U120"]:
            is_malicious = True
            
        users.append({
            "user": user_id,
            "role": role,
            "pc": f"PC-{100+i}",
            "email": f"{user_id.lower()}@company.com",
            "is_malicious": is_malicious
        })
    return pd.DataFrame(users)

def generate_noise_time(date, role):
    """Generate a timestamp. Adjust start time based on role/randomness."""
    # Basic 9-5 with noise
    start_hour = 8 + random.gauss(0, 0.5) # mostly around 8am
    if start_hour < 6: start_hour = 6
    return date + timedelta(hours=start_hour, minutes=random.randint(0, 59))

def generate_data(users_df):
    logon_rows = []
    file_rows = []
    http_rows = []
    device_rows = []
    email_rows = []
    
    event_id = 0
    
    print(f"Generating data for {DAYS_TO_SIMULATE} days...")
    
    for day in range(DAYS_TO_SIMULATE):
        current_date_base = START_DATE + timedelta(days=day)
        
        # Skip Weekends (mostly)
        if current_date_base.weekday() >= 5:
            if random.random() > 0.1: # 10% chance of weekend work
                continue
        
        for _, user in users_df.iterrows():
            uid = user['user']
            pc = user['pc']
            role = user['role']
            is_malicious = user['is_malicious']
            
            # --- 1. Logon ---
            login_time = generate_noise_time(current_date_base, role)
            
            # Malicious Scenario 1: U105 logs in at odd hours (3 AM)
            if is_malicious and uid == "U105" and day > 20: 
                 if random.random() > 0.7:
                    login_time = current_date_base + timedelta(hours=3, minutes=random.randint(0, 59))
            
            session_duration = 8 + random.gauss(0, 1) # ~8 hours
            logout_time = login_time + timedelta(hours=session_duration)
            
            logon_rows.append([f"L{event_id}", uid, login_time, pc, "Logon"])
            event_id += 1
            
            # --- Activities within Session ---
            current_time = login_time
            while current_time < logout_time:
                # Advance time randomly
                step = random.randint(5, 60) # mins
                current_time += timedelta(minutes=step)
                if current_time >= logout_time: break
                
                # Pick an activity type
                # Weights: HTTP (high), File (med), Email (med), Device (low)
                act_type = np.random.choice(["HTTP", "File", "Email", "Device"], p=[0.5, 0.3, 0.15, 0.05])
                
                # Malicious Scenario 2: Data Exfiltration (U105)
                # Bursts of File Copy -> USB (Device) late in the month
                if is_malicious and uid == "U105" and day > 25 and random.random() > 0.5:
                     act_type = "Exfil"
                
                if act_type == "HTTP":
                    url = fake.url()
                    http_rows.append([f"H{event_id}", uid, current_time, pc, url, fake.sentence()])
                    event_id += 1
                    
                elif act_type == "File":
                    fname = fake.file_name(category='office')
                    action = np.random.choice(["Open", "Edit"], p=[0.8, 0.2])
                    file_rows.append([f"F{event_id}", uid, current_time, pc, fname, action, False])
                    event_id += 1
                    
                elif act_type == "Email":
                    to_addr = fake.email()
                    is_external = "company.com" not in to_addr
                    size = random.randint(1024, 102400) # bytes
                    email_rows.append([f"M{event_id}", uid, current_time, pc, to_addr, "Send", size, random.randint(0, 2)])
                    event_id += 1
                
                elif act_type == "Device":
                    # Random connect/disconnect
                    device_rows.append([f"D{event_id}", uid, current_time, pc, "Connect"])
                    event_id += 1
                    # Disconnect after some time
                    disc_time = current_time + timedelta(minutes=random.randint(5, 30))
                    if disc_time < logout_time:
                        device_rows.append([f"D{event_id}", uid, disc_time, pc, "Disconnect"])
                        event_id += 1
                
                elif act_type == "Exfil":
                    # Simulate rapid file copies to USB
                    # 1. Connect USB
                    device_rows.append([f"D{event_id}", uid, current_time, pc, "Connect"])
                    event_id += 1
                    current_time += timedelta(seconds=30)
                    
                    # 2. Copy sensitive files
                    for _ in range(random.randint(5, 15)):
                        fname = f"CONFIDENTIAL_{fake.word()}.pdf"
                        file_rows.append([f"F{event_id}", uid, current_time, pc, fname, "Copy", True])
                        event_id += 1
                        current_time += timedelta(seconds=random.randint(5, 20))
                    
                    # 3. Disconnect
                    device_rows.append([f"D{event_id}", uid, current_time, pc, "Disconnect"])
                    event_id += 1
            
            # Finally Logoff
            logon_rows.append([f"L{event_id}", uid, logout_time, pc, "Logoff"])
            event_id += 1

    print("Saving CSVs...")
    
    # Create DataFrames
    df_logon = pd.DataFrame(logon_rows, columns=["id", "user", "date", "pc", "activity"])
    df_file = pd.DataFrame(file_rows, columns=["id", "user", "date", "pc", "filename", "activity", "to_removable_media"])
    df_http = pd.DataFrame(http_rows, columns=["id", "user", "date", "pc", "url", "content"])
    df_device = pd.DataFrame(device_rows, columns=["id", "user", "date", "pc", "activity"])
    df_email = pd.DataFrame(email_rows, columns=["id", "user", "date", "pc", "to", "activity", "size", "attachments"])
    
    # Save
    df_logon.to_csv(os.path.join(DATA_DIR, "logon.csv"), index=False)
    df_file.to_csv(os.path.join(DATA_DIR, "file.csv"), index=False)
    df_http.to_csv(os.path.join(DATA_DIR, "http.csv"), index=False)
    df_device.to_csv(os.path.join(DATA_DIR, "device.csv"), index=False)
    df_email.to_csv(os.path.join(DATA_DIR, "email.csv"), index=False)
    
    # Save user metadata
    users_df.to_csv(os.path.join(DATA_DIR, "users.csv"), index=False)
    
    print(f"Data generation complete. Files saved to {DATA_DIR}")

if __name__ == "__main__":
    print("Starting CERT r4.2 Synthetic Data Generation...")
    users_df = generate_users(NUM_USERS)
    generate_data(users_df)
