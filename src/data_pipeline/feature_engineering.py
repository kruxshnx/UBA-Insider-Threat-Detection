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
    def __init__(self, users_df_path):
        self.users_df = pd.read_csv(users_df_path)
        if 'id' in self.users_df.columns:
            self.users_df.rename(columns={'id': 'user'}, inplace=True)
        self.role_map = self.users_df.set_index('user')['role'].to_dict()
        
    def calculate_features(self, df):
        logger.info("Calculating behavioral features...")
        
        # Ensure datetime
        df['date'] = pd.to_datetime(df['date'])
        df['hour'] = df['date'].dt.hour
        
        # 1. FAR: File Access Ratio (Daily)
        # 2. EDS: Email Deviation Score (Daily)
        # 3. IAV: Inactive Activity Variance (Daily)
        # 4. OAF: Odd Activity Fraction (Daily)
        # 5. Login Entropy (Historical/Windowed - but let's do Daily for simplicity or rolling)
        
        # We process day by day per user to create a daily risk profile
        df['day'] = df['date'].dt.date
        
        daily_stats = []
        
        # Pre-calculate role stats for z-scores
        # Group by Role -> Day -> Count
        # This is complex in a streaming sense, so we'll do batch processing
        
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
                # Odd hours: Before 7 AM or after 8 PM (20:00)
                odd_hours = day_data[(day_data['hour'] < WORK_START_HOUR) | (day_data['hour'] > WORK_END_HOUR)]
                oaf = len(odd_hours) / len(day_data) if len(day_data) > 0 else 0
                
                # --- Login Entropy ---
                # Calculate entropy of activity hours for this day
                # (Or maybe historical? The prompt says "Login Time Entropy")
                # Let's map activity distribution across hours
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
        
        # Now calculate Peer Group Stats (FAR & EDS)
        # FAR = User File Count / Peer Avg
        # EDS = (User Email Count - Peer Avg) / Peer Std
        
        logger.info("Calculating Peer Group Statistics...")
        
        # Join with peer stats per day/role
        peer_stats = features_df.groupby(['role', 'day']).agg({
            'file_count': 'mean',
            'email_count': ['mean', 'std']
        }).reset_index()
        
        peer_stats.columns = ['role', 'day', 'peer_file_mean', 'peer_email_mean', 'peer_email_std']
        
        features_df = pd.merge(features_df, peer_stats, on=['role', 'day'], how='left')
        
        # FAR
        features_df['far'] = features_df['file_count'] / (features_df['peer_file_mean'] + 1e-6) # Avoid div/0
        
        # EDS
        features_df['eds'] = (features_df['email_count'] - features_df['peer_email_mean']) / (features_df['peer_email_std'] + 1e-6)
        
        # Fill NaN
        features_df = features_df.fillna(0)
        
        # Select final columns
        final_df = features_df[['user', 'role', 'day', 'far', 'eds', 'iav', 'oaf', 'login_entropy', 'file_count', 'email_count']]
        
        return final_df

if __name__ == "__main__":
    import argparse
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
    
    INPUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
    USERS_PATH = os.path.join(PROJECT_ROOT, "data/raw/users.csv")
    OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.csv")
    
    if os.path.exists(INPUT_PATH):
        df = pd.read_parquet(INPUT_PATH)
        engine = BehavioralFeatureEngine(USERS_PATH)
        features = engine.calculate_features(df)
        
        features.to_csv(OUTPUT_PATH, index=False)
        # Also save as parquet for train_role_lstm.py compatibility
        parquet_path = OUTPUT_PATH.replace('.csv', '.parquet')
        features.to_parquet(parquet_path, index=False)
        logger.info("Features saved to %s and %s", OUTPUT_PATH, parquet_path)
        logger.info("\n%s", features.head())
    else:
        logger.error("Master timeline not found at %s", INPUT_PATH)
