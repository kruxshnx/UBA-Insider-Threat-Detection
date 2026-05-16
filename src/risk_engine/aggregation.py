"""
User Baseline Drift Aggregation Module.

Implements:
- Rolling baseline per user (avg daily risk, std)
- Drift detection using N-sigma threshold
- Historical risk tracking
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config


class UserBaselineTracker:
    """
    Tracks and calculates per-user behavioral baselines for drift detection.
    """
    
    def __init__(self):
        self.drift_config = config.get('baseline_drift', {})
        self.baseline_window = self.drift_config.get('baseline_window_days', 14)
        self.drift_sigma = self.drift_config.get('drift_sigma', 2.0)
        
        # In-memory baseline storage (would be DB in production)
        self.user_baselines: Dict[str, Dict] = {}
    
    def update_baseline(self, user: str, daily_risk_scores: List[float]) -> Dict:
        """
        Update baseline for a user based on their recent daily risk scores.
        
        Args:
            user: User ID
            daily_risk_scores: List of daily aggregated risk scores
        
        Returns:
            Updated baseline dict
        """
        if len(daily_risk_scores) < 3:
            # Not enough data for baseline
            return {
                'avg': 0.0,
                'std': 0.0,
                'count': len(daily_risk_scores),
                'valid': False
            }
        
        # Use last N days
        recent_scores = daily_risk_scores[-self.baseline_window:]
        
        baseline = {
            'avg': float(np.mean(recent_scores)),
            'std': float(np.std(recent_scores)),
            'min': float(np.min(recent_scores)),
            'max': float(np.max(recent_scores)),
            'count': len(recent_scores),
            'valid': True,
            'updated_at': datetime.now().isoformat()
        }
        
        self.user_baselines[user] = baseline
        return baseline
    
    def detect_drift(self, user: str, current_risk: float) -> Tuple[bool, float, str]:
        """
        Detect if current risk represents a significant drift from baseline.
        
        Args:
            user: User ID
            current_risk: Current risk score
        
        Returns:
            Tuple of (is_drift, deviation_sigma, explanation)
        """
        baseline = self.user_baselines.get(user)
        
        if not baseline or not baseline.get('valid', False):
            return False, 0.0, "Insufficient baseline data"
        
        if baseline['std'] < 0.1:
            # Very low variance - treat any significant increase as drift
            if current_risk > baseline['avg'] + 20:
                deviation = (current_risk - baseline['avg']) / max(baseline['std'], 1.0)
                return True, deviation, f"Unusual activity (baseline avg={baseline['avg']:.1f})"
            return False, 0.0, "Within expected range (low variance user)"
        
        # Calculate z-score
        z_score = (current_risk - baseline['avg']) / baseline['std']
        
        if z_score > self.drift_sigma:
            explanation = (f"Risk {current_risk:.1f} exceeds baseline "
                          f"(avg={baseline['avg']:.1f}, +{z_score:.1f}σ)")
            return True, z_score, explanation
        
        return False, z_score, f"Within {self.drift_sigma}σ of baseline"
    
    def aggregate_user_risk_with_drift(
        self,
        user_events: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> Dict:
        """
        Aggregate risk for a user with drift detection.
        
        Args:
            user_events: DataFrame of user's events with 'risk_score' and 'date'
            current_time: Reference time for decay calculation
        
        Returns:
            Aggregation result with drift info
        """
        if user_events.empty:
            return {
                'total_risk': 0.0,
                'max_risk': 0.0,
                'event_count': 0,
                'is_drift': False,
                'deviation_sigma': 0.0,
                'drift_explanation': ''
            }
        
        risk_config = config.risk_scoring
        decay_rate = risk_config.get('decay_rate', 0.9)
        
        if current_time is None:
            current_time = user_events['date'].max()
        
        # Calculate decayed sum
        total_risk = 0.0
        max_risk = 0.0
        
        for _, row in user_events.iterrows():
            score = row.get('risk_score', 0)
            if score == 0:
                continue
            
            event_time = row['date']
            if hasattr(event_time, 'to_pydatetime'):
                event_time = event_time.to_pydatetime()
            
            days_diff = (current_time - event_time).total_seconds() / 86400
            days_diff = max(0, days_diff)
            
            decayed = score * (decay_rate ** days_diff)
            total_risk += decayed
            max_risk = max(max_risk, score)
        
        # Hybrid score
        aggregated_risk = max_risk + (total_risk * 0.1)
        
        # Check drift
        user = user_events['user'].iloc[0]
        is_drift, deviation, explanation = self.detect_drift(user, aggregated_risk)
        
        return {
            'total_risk': aggregated_risk,
            'max_risk': max_risk,
            'decayed_sum': total_risk,
            'event_count': len(user_events),
            'is_drift': is_drift,
            'deviation_sigma': deviation,
            'drift_explanation': explanation
        }
    
    def calculate_daily_risk_history(self, df: pd.DataFrame, user: str) -> List[float]:
        """Calculate daily aggregated risk scores for a user."""
        user_data = df[df['user'] == user].copy()
        
        if user_data.empty:
            return []
        
        user_data['date_only'] = user_data['date'].dt.date
        daily_risk = user_data.groupby('date_only')['risk_score'].sum().tolist()
        
        return daily_risk


class RiskAggregator:
    """
    Aggregates individual event risks into user-level risk profiles.
    """
    
    def __init__(self):
        self.baseline_tracker = UserBaselineTracker()
        self.risk_config = config.risk_scoring
    
    def aggregate_all_users(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate risk for all users in the dataset.
        
        Args:
            df: DataFrame with events and risk_score column
        
        Returns:
            DataFrame with user-level aggregations
        """
        current_time = df['date'].max()
        
        user_risks = []
        
        for user, group in df.groupby('user'):
            # Build baseline from historical data
            daily_history = self.baseline_tracker.calculate_daily_risk_history(df, user)
            self.baseline_tracker.update_baseline(user, daily_history)
            
            # Aggregate with drift
            agg = self.baseline_tracker.aggregate_user_risk_with_drift(group, current_time)
            
            user_risks.append({
                'user': user,
                'total_risk_score': agg['total_risk'],
                'max_risk': agg['max_risk'],
                'event_count': agg['event_count'],
                'is_drift': agg['is_drift'],
                'deviation_sigma': agg['deviation_sigma'],
                'drift_explanation': agg['drift_explanation']
            })
        
        return pd.DataFrame(user_risks).sort_values('total_risk_score', ascending=False)


# Singleton for state persistence
baseline_tracker = UserBaselineTracker()
risk_aggregator = RiskAggregator()
