import pandas as pd
import numpy as np
from scipy.stats import entropy
import os
import sys
import logging

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.data_pipeline.feature_engineering")

# Config-driven work-hour definition
_features_cfg = config.get('features', {})
WORK_START_HOUR = _features_cfg.get('work_start_hour', 7)
WORK_END_HOUR = _features_cfg.get('work_end_hour', 20)


class BehavioralFeatureEngine:
    """
    Produces a DAILY (per user-day) behavioral feature timeline.

    Beyond the classic peer-relative features (FAR/EDS/IAV/OAF/entropy), this
    engine now emits daily behavioral aggregates that the risk engine consumes:
        file_copy_count, usb_count, removable_media_count, delete_count,
        after_hours_count, after_hours_ratio, event_count.

    The behavioral aggregates are computed from the RAW file/device/logon logs
    (passed via ``raw_logs``) because master_timeline drops the
    ``to_removable_media`` flag and file-level ``activity`` labels.
    """

    def __init__(self, users_df_path):
        self.users_df = pd.read_csv(users_df_path)
        if 'id' in self.users_df.columns:
            self.users_df.rename(columns={'id': 'user'}, inplace=True)
        self.role_map = self.users_df.set_index('user')['role'].to_dict()

    def _daily_behavioral_aggregates(self, raw_logs):
        """
        Compute per user-day behavioral counts from the raw event logs.

        Args:
            raw_logs: dict with keys 'file', 'device', 'logon' -> DataFrames
                      (each with at least 'user', 'date' and event-specific cols)

        Returns:
            DataFrame indexed by ['user', 'day'] with behavioral count columns.
        """
        frames = []

        # Normalise each raw source into a common schema:
        #   user, day, hour, is_file_copy, is_delete, is_usb_connect, is_removable
        def _prep(df, source):
            if df is None or len(df) == 0:
                return None
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df['day'] = df['date'].dt.date
            df['hour'] = df['date'].dt.hour
            act = df['activity'].astype(str) if 'activity' in df.columns else pd.Series('', index=df.index)
            df['is_file_copy'] = (source == 'file') & (act == 'File Copy')
            df['is_delete'] = (source == 'file') & act.str.contains('Delete', case=False, na=False)
            df['is_usb_connect'] = (source == 'device') & (act == 'Connect')
            if 'to_removable_media' in df.columns:
                rem = df['to_removable_media']
                # CSV may load these as strings ("True"/"False") or booleans
                df['is_removable'] = rem.astype(str).str.lower().isin(['true', '1'])
            else:
                df['is_removable'] = False
            return df[['user', 'day', 'hour', 'is_file_copy', 'is_delete',
                       'is_usb_connect', 'is_removable']]

        for source in ('file', 'device', 'logon'):
            prepped = _prep(raw_logs.get(source), source)
            if prepped is not None:
                frames.append(prepped)

        if not frames:
            return pd.DataFrame(columns=['user', 'day'])

        allev = pd.concat(frames, ignore_index=True)
        allev['is_after_hours'] = (allev['hour'] < WORK_START_HOUR) | (allev['hour'] >= WORK_END_HOUR)

        agg = allev.groupby(['user', 'day']).agg(
            file_copy_count=('is_file_copy', 'sum'),
            delete_count=('is_delete', 'sum'),
            usb_count=('is_usb_connect', 'sum'),
            removable_media_count=('is_removable', 'sum'),
            after_hours_count=('is_after_hours', 'sum'),
            event_count=('hour', 'size'),
        ).reset_index()

        agg['after_hours_ratio'] = (
            agg['after_hours_count'] / agg['event_count'].replace(0, np.nan)
        ).fillna(0.0)

        # Ensure integer counts
        for col in ['file_copy_count', 'delete_count', 'usb_count',
                    'removable_media_count', 'after_hours_count', 'event_count']:
            agg[col] = agg[col].astype(int)

        return agg

    def calculate_features(self, df, raw_logs=None):
        logger.info("Calculating behavioral features...")

        # Ensure datetime
        df['date'] = pd.to_datetime(df['date'])
        df['hour'] = df['date'].dt.hour

        # We process day by day per user to create a daily risk profile
        df['day'] = df['date'].dt.date

        daily_stats = []

        for user, group in df.groupby('user'):
            role = self.role_map.get(user, 'Unknown')

            for day, day_data in group.groupby('day'):
                day_data = day_data.sort_values('date')

                # --- Basic Counts ---
                file_count = len(day_data[day_data['source'] == 'File'])
                email_count = len(day_data[day_data['source'] == 'Email'])

                # --- IAV (Inactive Activity Variance) ---
                time_deltas = day_data['date'].diff().dt.total_seconds().dropna()
                if len(time_deltas) > 1:
                    iav = time_deltas.var()
                else:
                    iav = 0

                # --- OAF (Odd Activity Fraction) ---
                odd_hours = day_data[(day_data['hour'] < WORK_START_HOUR) | (day_data['hour'] >= WORK_END_HOUR)]
                oaf = len(odd_hours) / len(day_data) if len(day_data) > 0 else 0

                # --- Login Entropy (entropy of activity across hours of day) ---
                hour_counts = day_data['hour'].value_counts()
                login_entropy = entropy(hour_counts)

                daily_stats.append({
                    'user': user,
                    'role': role,
                    'day': day,
                    'file_count': file_count,
                    'email_count': email_count,
                    'iav': iav,
                    'oaf': oaf,
                    'login_entropy': login_entropy
                })

        features_df = pd.DataFrame(daily_stats)

        # --- Peer Group Stats (FAR & EDS) ---
        logger.info("Calculating Peer Group Statistics...")

        peer_stats = features_df.groupby(['role', 'day']).agg({
            'file_count': 'mean',
            'email_count': ['mean', 'std']
        }).reset_index()

        peer_stats.columns = ['role', 'day', 'peer_file_mean', 'peer_email_mean', 'peer_email_std']

        features_df = pd.merge(features_df, peer_stats, on=['role', 'day'], how='left')

        # FAR
        features_df['far'] = features_df['file_count'] / (features_df['peer_file_mean'] + 1e-6)

        # EDS
        features_df['eds'] = (features_df['email_count'] - features_df['peer_email_mean']) / (features_df['peer_email_std'] + 1e-6)

        # --- DAILY behavioral aggregates from raw logs ---
        logger.info("Calculating daily behavioral aggregates (copy/usb/removable/delete/after-hours)...")
        behav_cols = ['file_copy_count', 'usb_count', 'removable_media_count',
                      'delete_count', 'after_hours_count', 'after_hours_ratio', 'event_count']
        if raw_logs is not None:
            behav = self._daily_behavioral_aggregates(raw_logs)
            features_df = pd.merge(features_df, behav, on=['user', 'day'], how='left')
        else:
            for c in behav_cols:
                features_df[c] = 0

        # Fill NaN (from merges / peer std / missing behavioral days)
        features_df = features_df.fillna(0)

        # day_of_week is a useful numeric temporal feature for the LSTM
        features_df['day_of_week'] = pd.to_datetime(features_df['day']).dt.dayofweek

        # Ensure count columns are ints after fillna
        for c in ['file_copy_count', 'usb_count', 'removable_media_count',
                  'delete_count', 'after_hours_count', 'event_count', 'day_of_week']:
            features_df[c] = features_df[c].astype(int)

        # Select final columns (numeric behavioral + peer-relative features)
        final_cols = ['user', 'role', 'day', 'day_of_week',
                      'far', 'eds', 'iav', 'oaf', 'login_entropy',
                      'file_count', 'email_count',
                      'file_copy_count', 'usb_count', 'removable_media_count',
                      'delete_count', 'after_hours_count', 'after_hours_ratio', 'event_count']
        final_df = features_df[final_cols]

        return final_df


def _load_raw_logs(raw_dir):
    """Load raw file/device/logon CSVs for behavioral aggregation."""
    raw_logs = {}
    for name in ('file', 'device', 'logon'):
        path = os.path.join(raw_dir, f"{name}.csv")
        if os.path.exists(path):
            raw_logs[name] = pd.read_csv(path)
        else:
            raw_logs[name] = None
    return raw_logs


def build_featured_timeline(master_path, users_path, raw_dir, output_csv, output_parquet):
    """
    Build the daily featured timeline and persist to CSV + Parquet.
    Callable from the normalization step so it runs inside the standard pipeline.
    """
    df = pd.read_parquet(master_path)
    engine = BehavioralFeatureEngine(users_path)
    raw_logs = _load_raw_logs(raw_dir)
    features = engine.calculate_features(df, raw_logs=raw_logs)

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    # 'day' as date objects -> stringify for CSV stability
    features.to_csv(output_csv, index=False)
    features.to_parquet(output_parquet, index=False)
    logger.info("Features saved to %s and %s", output_csv, output_parquet)
    return features


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))

    INPUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
    USERS_PATH = os.path.join(PROJECT_ROOT, "data/raw/users.csv")
    RAW_DIR = os.path.join(PROJECT_ROOT, "data/raw")
    OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.csv")
    PARQUET_PATH = OUTPUT_PATH.replace('.csv', '.parquet')

    if os.path.exists(INPUT_PATH):
        features = build_featured_timeline(INPUT_PATH, USERS_PATH, RAW_DIR, OUTPUT_PATH, PARQUET_PATH)
        logger.info("\n%s", features.head())
    else:
        logger.error("Master timeline not found at %s", INPUT_PATH)
