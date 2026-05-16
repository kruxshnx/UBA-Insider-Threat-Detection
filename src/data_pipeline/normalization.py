import polars as pl
from datetime import datetime
import os
import sys
import logging
from .schema import validate_schema

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.data_pipeline.normalization")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
RAW_DIR = os.path.join(PROJECT_ROOT, "data/raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data/processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

def load_and_normalize():
    logger.info("Loading Raw Data...")
    
    # Load with Polars for speed
    try:
        df_logon = pl.read_csv(f"{RAW_DIR}/logon.csv", try_parse_dates=True)
        df_file = pl.read_csv(f"{RAW_DIR}/file.csv", try_parse_dates=True)
        df_http = pl.read_csv(f"{RAW_DIR}/http.csv", try_parse_dates=True)
        df_device = pl.read_csv(f"{RAW_DIR}/device.csv", try_parse_dates=True)
    except Exception as e:
        logger.error("Error loading CSVs: %s", e)
        return

    # 1. Standardize Timestamps
    # Ensure all are proper Datetime objects
    # (Polars try_parse_dates handles generic ISO formats, but we explicitly cast if needed)
    
    # 2. Add Source Type Column
    df_logon = df_logon.with_columns(pl.lit("Logon").alias("source"))
    df_file = df_file.with_columns(pl.lit("File").alias("source"))
    df_http = df_http.with_columns(pl.lit("Http").alias("source"))
    df_device = df_device.with_columns(pl.lit("Device").alias("source"))

    # 3. Missing Data Handling
    # Fill missing content in HTTP
    df_http = df_http.with_columns(pl.col("content").fill_null(""))
    # Add 'activity' to HTTP if missing (it's not in generator schema for HTTP)
    df_http = df_http.with_columns(pl.lit("Http Request").alias("activity"))

    # 4. Unified Event Log (Merge)
    # Select common columns for the master timeline
    common_cols = ["id", "user", "date", "pc", "source", "activity"]
    
    master_log = pl.concat([
        df_logon.select(common_cols),
        df_file.select(common_cols),
        df_http.select(common_cols),
        df_device.select(common_cols)
    ])

    # 5. Time Synchronization & Ordering
    master_log = master_log.sort("date")

    # 6. Save Normalized Parquet
    master_log.write_parquet(f"{PROCESSED_DIR}/master_timeline.parquet")
    
    # Save individual normalized files too
    df_logon.write_parquet(f"{PROCESSED_DIR}/logon.parquet")
    df_file.write_parquet(f"{PROCESSED_DIR}/file.parquet")
    
    logger.info("Normalization Complete. Master Log: %d events.", len(master_log))

if __name__ == "__main__":
    load_and_normalize()
