"""
Behavioral Biometrics Feature Engineering Module.

This module implements privacy-compliant behavioral biometric features:
- Mouse Dynamics: Velocity, Acceleration, Tortuosity (path efficiency)
- Keystroke Dynamics: Flight-Time, Dwell-Time, Rhythm patterns
- Work Integrity Monitoring: Active vs idle states, productivity metrics

All features are designed to be privacy-preserving (no keylogging content).
"""

import polars as pl
import numpy as np
from scipy.stats import entropy
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("uba.data_pipeline.behavioral_biometrics")


class BehavioralBiometricsEngine:
    """
    Extracts behavioral biometric features from endpoint telemetry.
    
    Features are computed at multiple timescales:
    - Micro (1Hz): Instantaneous mouse/keyboard dynamics
    - Meso (5-min windows): Aggregated patterns
    - Macro (daily): Long-term behavioral signatures
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Configurable thresholds
        self.mouse_velocity_threshold = self.config.get('mouse_velocity_threshold', 500.0)
        self.keystroke_flight_min = self.config.get('keystroke_flight_min', 0.03)
        self.keystroke_flight_max = self.config.get('keystroke_flight_max', 2.0)
        self.idle_threshold_seconds = self.config.get('idle_threshold_seconds', 300)
        
        # Work hours configuration
        work_cfg = self.config.get('work_hours', {})
        self.work_start = work_cfg.get('start_hour', 7)
        self.work_end = work_cfg.get('end_hour', 20)
        
        logger.info("BehavioralBiometricsEngine initialized")
    
    def compute_mouse_features(
        self,
        df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Compute mouse dynamics features from raw telemetry.
        
        Input DataFrame must have columns:
        - timestamp: datetime (ns precision)
        - mouse_x, mouse_y: screen coordinates
        - mouse_velocity: optional, pre-computed velocity
        
        Returns DataFrame with mouse features per session/window.
        """
        logger.info("Computing mouse dynamics features...")
        
        if df.height == 0:
            return self._empty_mouse_features()
        
        # Ensure sorted by timestamp
        df = df.sort('timestamp')
        
        # Compute deltas if not present
        if 'mouse_x' in df.columns and 'mouse_y' in df.columns:
            # Calculate Euclidean distance between consecutive points
            df = df.with_columns([
                (pl.col('mouse_x').shift(1) - pl.col('mouse_x')).alias('dx'),
                (pl.col('mouse_y').shift(1) - pl.col('mouse_y')).alias('dy'),
                (pl.col('timestamp').diff().dt.total_seconds() * 1000).alias('dt_ms'),
            ])
            
            # Path length (Euclidean distance)
            df = df.with_columns([
                ((pl.col('dx') ** 2 + pl.col('dy') ** 2) ** 0.5).alias('path_segment')
            ])
            
            # Mouse Tortuosity: ratio of actual path length to straight-line distance
            # High tortuosity = erratic, circular, or hesitant movement
            # Low tortuosity = direct, purposeful movement
            df = df.with_columns([
                (pl.col('path_segment') / (pl.col('path_segment').sum() + 1e-6)).alias('tortuosity_contribution')
            ])
        
        # Aggregate features per user per session
        features = df.group_by('user').agg([
            # Mean velocity
            pl.col('mouse_velocity').mean().alias('mouse_velocity_mean') if 'mouse_velocity' in df.columns else pl.lit(0.0).alias('mouse_velocity_mean'),
            
            # Velocity standard deviation (consistency)
            pl.col('mouse_velocity').std().alias('mouse_velocity_std') if 'mouse_velocity' in df.columns else pl.lit(0.0).alias('mouse_velocity_std'),
            
            # Mouse Tortuosity Index (MTI)
            # Sum of segment lengths / straight line distance
            pl.col('tortuosity_contribution').sum().alias('mouse_tortuosity_index') if 'tortuosity_contribution' in df.columns else pl.lit(1.0).alias('mouse_tortuosity_index'),
            
            # Mouse activity ratio (moving vs stationary time)
            (pl.col('mouse_velocity').filter(pl.col('mouse_velocity') > 0).count() / pl.len()).alias('mouse_activity_ratio') if 'mouse_velocity' in df.columns else pl.lit(0.0).alias('mouse_activity_ratio'),
        ])
        
        return features
    
    def compute_keystroke_features(
        self,
        df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Compute keystroke dynamics features from raw telemetry.
        
        Input DataFrame must have columns:
        - timestamp: datetime
        - key_event: boolean or event type
        - key_flight_time: time between key releases (if available)
        
        Features computed:
        - Flight-Time: Time between releasing one key and pressing next
        - Dwell-Time: Duration a key is held down
        - Rhythm consistency: Variance in typing patterns
        """
        logger.info("Computing keystroke dynamics features...")
        
        if df.height == 0:
            return self._empty_keystroke_features()
        
        df = df.sort('timestamp')
        
        # Compute flight times if not present
        if 'key_press_time' in df.columns:
            # Flight time: time between key release and next key press
            df = df.with_columns([
                (pl.col('key_press_time') - pl.col('key_release_time').shift(1)).alias('flight_time_ms')
            ])
            
            # Dwell time: key press duration
            df = df.with_columns([
                (pl.col('key_release_time') - pl.col('key_press_time')).alias('dwell_time_ms')
            ])
        
        # Aggregate features
        features = df.group_by('user').agg([
            # Mean flight time
            pl.col('flight_time_ms').mean().alias('keystroke_flight_mean') if 'flight_time_ms' in df.columns else pl.lit(0.0).alias('keystroke_flight_mean'),
            
            # Flight time standard deviation (rhythm consistency)
            pl.col('flight_time_ms').std().alias('keystroke_flight_std') if 'flight_time_ms' in df.columns else pl.lit(0.0).alias('keystroke_flight_std'),
            
            # Mean dwell time
            pl.col('dwell_time_ms').mean().alias('keystroke_dwell_mean') if 'dwell_time_ms' in df.columns else pl.lit(0.0).alias('keystroke_dwell_mean'),
            
            # Typing speed (keys per minute)
            (pl.len() / (pl.col('timestamp').max() - pl.col('timestamp').min()).dt.total_seconds() * 60).alias('typing_speed_wpm') if 'timestamp' in df.columns else pl.lit(0.0).alias('typing_speed_wpm'),
        ])
        
        return features
    
    def compute_work_integrity_features(
        self,
        df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Compute work integrity and productivity monitoring features.
        
        Detects:
        - Active work time (IDE, Office apps, coding tools)
        - Anomalous idleness (unusual inactive periods)
        - Distraction patterns (excessive non-work HTTP/app usage)
        - Anomalous velocity in file operations
        """
        logger.info("Computing work integrity features...")
        
        if df.height == 0:
            return self._empty_work_integrity_features()
        
        df = df.sort('timestamp')
        
        # Calculate session-level features
        features = df.group_by('user').agg([
            # Active application ratio
            pl.col('is_productive_app').mean().alias('productive_app_ratio') if 'is_productive_app' in df.columns else pl.lit(1.0).alias('productive_app_ratio'),
            
            # Idle time ratio
            pl.col('is_idle').mean().alias('idle_time_ratio') if 'is_idle' in df.columns else pl.lit(0.0).alias('idle_time_ratio'),
            
            # Non-work HTTP ratio
            pl.col('is_non_work_http').mean().alias('non_work_http_ratio') if 'is_non_work_http' in df.columns else pl.lit(0.0).alias('non_work_http_ratio'),
            
            # File operation velocity (operations per minute)
            (pl.col('file_operation').count() / (pl.col('timestamp').max() - pl.col('timestamp').min()).dt.total_seconds() * 60).alias('file_op_velocity') if 'file_operation' in df.columns else pl.lit(0.0).alias('file_op_velocity'),
            
            # After-hours activity ratio
            ((pl.col('hour') < self.work_start) | (pl.col('hour') > self.work_end)).cast(pl.Float32).mean().alias('after_hours_ratio') if 'hour' in df.columns else pl.lit(0.0).alias('after_hours_ratio'),
        ])
        
        return features
    
    def compute_session_entropy(
        self,
        df: pl.DataFrame,
        window_minutes: int = 5
    ) -> pl.DataFrame:
        """
        Compute Dynamic Role-Entropy for each session window.
        
        Entropy measures the diversity/erraticness of user activity:
        - Low entropy: Focused, role-consistent activity
        - High entropy: Erratic, multi-domain activity (potential threat)
        
        Uses Shannon entropy over activity type distribution.
        """
        logger.info("Computing session entropy features...")
        
        if df.height == 0:
            return self._empty_entropy_features()
        
        # Group by user and time windows
        df = df.with_columns([
            (pl.col('timestamp').dt.epoch('s') // (window_minutes * 60)).alias('time_window')
        ])
        
        # Compute entropy per window
        entropy_features = []
        
        for (user, window), group in df.group_by('user', 'time_window', maintain_order=True):
            # Activity distribution
            if 'activity_type' in group.columns:
                activity_counts = group['activity_type'].value_counts()
                probabilities = activity_counts / activity_counts.sum()
                session_entropy = entropy(probabilities, base=2)
            else:
                session_entropy = 0.0
            
            # Application switching frequency
            if 'app_category' in group.columns:
                app_transitions = (group['app_category'] != group['app_category'].shift(1)).sum()
            else:
                app_transitions = 0
            
            # Domain diversity (for HTTP activity)
            if 'domain' in group.columns:
                unique_domains = group['domain'].n_unique()
            else:
                unique_domains = 0
            
            entropy_features.append({
                'user': user,
                'time_window': window,
                'activity_entropy': session_entropy,
                'app_transitions': app_transitions,
                'domain_diversity': unique_domains,
            })
        
        if not entropy_features:
            return self._empty_entropy_features()
        
        return pl.DataFrame(entropy_features)
    
    def compute_anomalous_velocity_score(
        self,
        current_df: pl.DataFrame,
        baseline_df: pl.DataFrame,
        feature_name: str = 'file_op_velocity'
    ) -> float:
        """
        Detect anomalous velocity in user actions.
        
        Compares current behavior against 30-day baseline.
        Flags if current velocity > 5x baseline average.
        
        Returns: Anomalous velocity score (0.0 - 1.0)
        """
        if current_df.height == 0 or baseline_df.height == 0:
            return 0.0
        
        # Get baseline statistics
        if feature_name in baseline_df.columns:
            baseline_mean = baseline_df[feature_name].mean()
            baseline_std = baseline_df[feature_name].std()
        else:
            return 0.0
        
        # Get current value
        if feature_name in current_df.columns:
            current_value = current_df[feature_name].mean()
        else:
            return 0.0
        
        # Anomalous if > 5x baseline
        if baseline_mean > 0 and current_value > (5 * baseline_mean):
            # Score based on how far above threshold
            deviation = (current_value - baseline_mean) / (baseline_std + 1e-6)
            return min(1.0, deviation / 10.0)  # Normalize to 0-1
        
        return 0.0
    
    def aggregate_behavioral_signature(
        self,
        mouse_features: pl.DataFrame,
        keystroke_features: pl.DataFrame,
        work_features: pl.DataFrame,
        entropy_features: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Aggregate all behavioral features into unified signature.
        """
        logger.info("Aggregating behavioral signature...")
        
        # Join all features on user
        signature = mouse_features
        
        if keystroke_features.height > 0:
            signature = signature.join(
                keystroke_features, on='user', how='full', suffix='_ks'
            )
        
        if work_features.height > 0:
            signature = signature.join(
                work_features, on='user', how='full', suffix='_work'
            )
        
        # Add entropy features
        if entropy_features.height > 0:
            # Aggregate entropy per user
            entropy_agg = entropy_features.group_by('user').agg([
                pl.col('activity_entropy').mean().alias('mean_activity_entropy'),
                pl.col('activity_entropy').std().alias('entropy_variance'),
                pl.col('app_transitions').mean().alias('avg_app_transitions'),
                pl.col('domain_diversity').mean().alias('avg_domain_diversity'),
            ])
            signature = signature.join(entropy_agg, on='user', how='left')
        
        return signature
    
    # Empty feature helpers
    def _empty_mouse_features(self) -> pl.DataFrame:
        return pl.DataFrame({
            'mouse_velocity_mean': [0.0],
            'mouse_velocity_std': [0.0],
            'mouse_tortuosity_index': [1.0],
            'mouse_activity_ratio': [0.0],
        })
    
    def _empty_keystroke_features(self) -> pl.DataFrame:
        return pl.DataFrame({
            'keystroke_flight_mean': [0.0],
            'keystroke_flight_std': [0.0],
            'keystroke_dwell_mean': [0.0],
            'typing_speed_wpm': [0.0],
        })
    
    def _empty_work_integrity_features(self) -> pl.DataFrame:
        return pl.DataFrame({
            'productive_app_ratio': [1.0],
            'idle_time_ratio': [0.0],
            'non_work_http_ratio': [0.0],
            'file_op_velocity': [0.0],
            'after_hours_ratio': [0.0],
        })
    
    def _empty_entropy_features(self) -> pl.DataFrame:
        return pl.DataFrame({
            'activity_entropy': [0.0],
            'app_transitions': [0],
            'domain_diversity': [0],
        })


def extract_behavioral_features(
    telemetry_df: pl.DataFrame,
    config: Optional[Dict] = None
) -> Tuple[pl.DataFrame, Dict]:
    """
    Main entry point: Extract all behavioral biometric features.
    
    Args:
        telemetry_df: Raw telemetry with columns:
            - user, timestamp, mouse_x, mouse_y, mouse_velocity
            - key_press_time, key_release_time
            - app_category, activity_type, domain
            - is_productive_app, is_idle, is_non_work_http
        config: Optional configuration dict
    
    Returns:
        Tuple of (behavioral_signature_df, feature_metadata)
    """
    engine = BehavioralBiometricsEngine(config)
    
    # Compute all feature sets
    mouse_feat = engine.compute_mouse_features(telemetry_df)
    keystroke_feat = engine.compute_keystroke_features(telemetry_df)
    work_feat = engine.compute_work_integrity_features(telemetry_df)
    entropy_feat = engine.compute_session_entropy(telemetry_df)
    
    # Aggregate into unified signature
    signature = engine.aggregate_behavioral_signature(
        mouse_feat, keystroke_feat, work_feat, entropy_feat
    )
    
    # Compute metadata
    metadata = {
        'feature_count': len(signature.columns),
        'users_processed': signature['user'].n_unique() if 'user' in signature.columns else 0,
        'timestamp': datetime.now().isoformat(),
    }
    
    return signature, metadata


if __name__ == "__main__":
    # Example usage with synthetic data
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, help="Input telemetry parquet")
    parser.add_argument("--output", type=str, help="Output features parquet")
    args = parser.parse_args()
    
    if args.input:
        df = pl.read_parquet(args.input)
        signature, metadata = extract_behavioral_features(df)
        
        if args.output:
            signature.write_parquet(args.output)
            logger.info(f"Features saved to {args.output}")
            print(f"Metadata: {metadata}")
