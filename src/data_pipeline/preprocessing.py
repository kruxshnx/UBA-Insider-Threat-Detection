import pandas as pd
import os
import sys
import logging

# Add parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.data_pipeline.preprocessing")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, "data/processed")
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

def load_and_standardize():
    dfs = []
    
    # 1. Logon
    if os.path.exists(os.path.join(RAW_DATA_DIR, "logon.csv")):
        df_logon = pd.read_csv(os.path.join(RAW_DATA_DIR, "logon.csv"))
        df_logon['source'] = 'Logon'
        df_logon['details'] = df_logon['activity'] # Logon/Logoff
        dfs.append(df_logon[['id', 'user', 'date', 'pc', 'source', 'activity', 'details']])
        
    # 2. File
    if os.path.exists(os.path.join(RAW_DATA_DIR, "file.csv")):
        df_file = pd.read_csv(os.path.join(RAW_DATA_DIR, "file.csv"))
        df_file['source'] = 'File'
        df_file['details'] = df_file['filename']
        # Map True/False to boolean or string if needed
        dfs.append(df_file[['id', 'user', 'date', 'pc', 'source', 'activity', 'details']])

    # 3. HTTP
    if os.path.exists(os.path.join(RAW_DATA_DIR, "http.csv")):
        df_http = pd.read_csv(os.path.join(RAW_DATA_DIR, "http.csv"))
        df_http['source'] = 'HTTP'
        df_http['activity'] = 'Visit'
        df_http['details'] = df_http['url']
        dfs.append(df_http[['id', 'user', 'date', 'pc', 'source', 'activity', 'details']])

    # 4. Device
    if os.path.exists(os.path.join(RAW_DATA_DIR, "device.csv")):
        df_device = pd.read_csv(os.path.join(RAW_DATA_DIR, "device.csv"))
        df_device['source'] = 'Device'
        df_device['details'] = df_device['activity'] # Connect/Disconnect
        dfs.append(df_device[['id', 'user', 'date', 'pc', 'source', 'activity', 'details']])

    # 5. Email
    if os.path.exists(os.path.join(RAW_DATA_DIR, "email.csv")):
        df_email = pd.read_csv(os.path.join(RAW_DATA_DIR, "email.csv"))
        df_email['source'] = 'Email'
        df_email['details'] = df_email['to'] # Recipient
        dfs.append(df_email[['id', 'user', 'date', 'pc', 'source', 'activity', 'details']])

    if not dfs:
        logger.error("No raw data found in %s", RAW_DATA_DIR)
        return

    # Merge
    logger.info("Merging %d dataframes...", len(dfs))
    master_df = pd.concat(dfs, ignore_index=True)
    
    # Convert date
    master_df['date'] = pd.to_datetime(master_df['date'])
    
    # Sort
    master_df = master_df.sort_values(['date', 'user']).reset_index(drop=True)
    
    # Save
    output_path = os.path.join(PROCESSED_DATA_DIR, "master_timeline.parquet")
    master_df.to_parquet(output_path, index=False)
    logger.info("Saved master timeline to %s with %d events.", output_path, len(master_df))

if __name__ == "__main__":
    load_and_standardize()
