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
        # Number of most-recent days treated as the "current" window (excluded
        # from the baseline so we compare recent behavior to earlier behavior).
        # Sized to cover the whole anomaly burst so early anomalous days do not
        # contaminate the (quiet) earlier-period baseline.
        self.recent_window = self.drift_config.get('recent_window_days', 6)

        # In-memory baseline storage (would be DB in production)
        self.user_baselines: Dict[str, Dict] = {}
    
    def update_baseline(self, user: str, daily_risk_scores: List[float]) -> Dict:
        """
        Build a user's OWN earlier-period baseline from their daily risk series.

        The baseline is the mean/std of daily risk over the baseline window
        EXCLUDING the most recent ``recent_window`` days, so drift compares recent
        behavior against the user's own earlier behavior on the SAME scale
        (mean daily risk, 0-100).

        Args:
            user: User ID
            daily_risk_scores: chronologically ordered list of daily risk values

        Returns:
            Baseline dict {avg, std, count, valid, ...}
        """
        # Split off the most-recent window; baseline = the earlier days.
        if len(daily_risk_scores) > self.recent_window:
            baseline_scores = daily_risk_scores[:-self.recent_window]
        else:
            baseline_scores = []

        # Restrict baseline to the configured window (most recent baseline days).
        baseline_scores = baseline_scores[-self.baseline_window:]

        if len(baseline_scores) < 3:
            baseline = {
                'avg': 0.0,
                'std': 0.0,
                'count': len(baseline_scores),
                'valid': False,
            }
            self.user_baselines[user] = baseline
            return baseline

        baseline = {
            'avg': float(np.mean(baseline_scores)),
            'std': float(np.std(baseline_scores)),
            'min': float(np.min(baseline_scores)),
            'max': float(np.max(baseline_scores)),
            'count': len(baseline_scores),
            'valid': True,
            'updated_at': datetime.now().isoformat()
        }

        self.user_baselines[user] = baseline
        return baseline

    def detect_drift(self, user: str, recent_risk: float) -> Tuple[bool, float, str]:
        """
        Detect drift: does the user's RECENT daily risk exceed their own
        earlier-period baseline by more than ``drift_sigma`` standard deviations?

        Both ``recent_risk`` and the baseline are on the same scale (daily risk,
        0-100), so the comparison is honest and only a small minority drift.

        Args:
            user: User ID
            recent_risk: the user's recent-window daily risk (e.g. max of the
                         most recent days)

        Returns:
            Tuple of (is_drift, deviation_sigma, explanation)
        """
        baseline = self.user_baselines.get(user)

        if not baseline or not baseline.get('valid', False):
            return False, 0.0, "Insufficient baseline data"

        if baseline['std'] < 1.0:
            # Very low variance baseline: require a clear absolute jump.
            if recent_risk > baseline['avg'] + 15:
                deviation = (recent_risk - baseline['avg']) / max(baseline['std'], 1.0)
                return True, deviation, (
                    f"Recent daily risk {recent_risk:.1f} >> baseline "
                    f"avg={baseline['avg']:.1f} (low-variance user)"
                )
            return False, 0.0, "Within expected range (low variance user)"

        z_score = (recent_risk - baseline['avg']) / baseline['std']

        if z_score > self.drift_sigma:
            explanation = (f"Recent daily risk {recent_risk:.1f} exceeds baseline "
                           f"(avg={baseline['avg']:.1f}, +{z_score:.1f} sigma)")
            return True, z_score, explanation

        return False, z_score, f"Within {self.drift_sigma} sigma of baseline"
    
    def aggregate_user_risk_with_drift(
        self,
        user_events: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> Dict:
        """
        Aggregate risk for a user with drift detection.

        Drift compares the user's RECENT daily risk to their OWN earlier-period
        baseline (built via update_baseline), so it is on the same scale and
        only a small minority drift.

        Aggregation weights (max_weight / sum_weight) are read from config.

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
        max_weight = risk_config.get('max_weight', 1.0)
        sum_weight = risk_config.get('sum_weight', 0.1)

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

        # Hybrid aggregate score (config-weighted).
        aggregated_risk = (max_weight * max_risk) + (sum_weight * total_risk)

        # Drift: compare the user's recent daily risk to their earlier baseline.
        user = user_events['user'].iloc[0]
        daily_series = self._daily_series_from_events(user_events)
        if len(daily_series) > self.recent_window:
            recent_risk = float(np.max(daily_series[-self.recent_window:]))
        elif daily_series:
            recent_risk = float(np.max(daily_series))
        else:
            recent_risk = 0.0

        is_drift, deviation, explanation = self.detect_drift(user, recent_risk)

        return {
            'total_risk': aggregated_risk,
            'max_risk': max_risk,
            'decayed_sum': total_risk,
            'recent_daily_risk': recent_risk,
            'event_count': len(user_events),
            'is_drift': is_drift,
            'deviation_sigma': deviation,
            'drift_explanation': explanation
        }

    @staticmethod
    def _daily_series_from_events(user_events: pd.DataFrame) -> List[float]:
        """Mean daily risk series (chronological) for a single user's events."""
        ue = user_events.copy()
        ue['date_only'] = pd.to_datetime(ue['date']).dt.date
        daily = ue.groupby('date_only')['risk_score'].mean().sort_index()
        return daily.tolist()
    
    def calculate_daily_risk_history(self, df: pd.DataFrame, user: str) -> List[float]:
        """Chronologically ordered MEAN daily risk series for a user.

        Uses the mean (not sum) so it is on the same 0-100 scale as the recent
        daily risk used for drift comparison.
        """
        user_data = df[df['user'] == user].copy()

        if user_data.empty:
            return []

        user_data['date_only'] = pd.to_datetime(user_data['date']).dt.date
        daily_risk = user_data.groupby('date_only')['risk_score'].mean().sort_index()

        return daily_risk.tolist()


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
