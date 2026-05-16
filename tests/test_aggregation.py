"""
Unit tests for the Risk Aggregation module (aggregation.py).

Covers:
  - UserBaselineTracker baseline calculation
  - Drift detection (above/below sigma threshold)
  - RiskAggregator user-level aggregation
  - Decay calculation correctness
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from risk_engine.aggregation import UserBaselineTracker, RiskAggregator


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tracker():
    """Fresh baseline tracker per test."""
    return UserBaselineTracker()


@pytest.fixture
def aggregator():
    """Fresh RiskAggregator per test."""
    return RiskAggregator()


def _make_events_df(user='U100', n_events=20, base_score=10.0, days=5):
    """Create a synthetic events DataFrame for testing."""
    dates = [datetime(2024, 1, 1) + timedelta(days=i % days, hours=i) for i in range(n_events)]
    return pd.DataFrame({
        'user': [user] * n_events,
        'date': pd.to_datetime(dates),
        'risk_score': np.random.uniform(0, base_score, n_events),
        'activity': ['Logon'] * n_events,
    })


# ── UserBaselineTracker Tests ────────────────────────────────────────────────

class TestUserBaselineTracker:
    def test_insufficient_data_returns_invalid(self, tracker):
        """Fewer than 3 data points → invalid baseline."""
        result = tracker.update_baseline('U100', [5.0, 10.0])
        assert result['valid'] is False

    def test_sufficient_data_returns_valid(self, tracker):
        """3+ data points → valid baseline with avg/std."""
        scores = [10.0, 12.0, 8.0, 15.0, 9.0]
        result = tracker.update_baseline('U100', scores)
        assert result['valid'] is True
        assert result['avg'] == pytest.approx(np.mean(scores))
        assert result['std'] == pytest.approx(np.std(scores))

    def test_baseline_updates_user_state(self, tracker):
        """update_baseline stores the result in user_baselines dict."""
        tracker.update_baseline('U100', [5, 10, 15, 20])
        assert 'U100' in tracker.user_baselines

    def test_detect_drift_no_baseline(self, tracker):
        """No baseline → no drift detected."""
        is_drift, _, explanation = tracker.detect_drift('U999', 50.0)
        assert is_drift is False
        assert 'Insufficient' in explanation

    def test_detect_drift_below_sigma(self, tracker):
        """Risk within N-sigma of avg → no drift."""
        tracker.update_baseline('U100', [10, 11, 9, 12, 10, 8])
        # avg ≈ 10, std ≈ ~1.4, so 12 is ~1.4σ which is < drift_sigma (2.0)
        is_drift, z, _ = tracker.detect_drift('U100', 12.0)
        assert is_drift is False

    def test_detect_drift_above_sigma(self, tracker):
        """Risk far above avg → drift detected."""
        tracker.update_baseline('U100', [10, 11, 9, 12, 10, 8])
        # avg ≈ 10, std ≈ ~1.4, so 20 is ~7σ which is > drift_sigma (2.0)
        is_drift, z, _ = tracker.detect_drift('U100', 20.0)
        assert is_drift is True
        assert z > 2.0

    def test_detect_drift_low_variance_user(self, tracker):
        """Very low variance user — even small increase triggers drift."""
        tracker.update_baseline('U100', [5.0, 5.0, 5.0, 5.0, 5.0])
        # std ≈ 0, so risk 30 (25 above avg) should trigger
        is_drift, _, _ = tracker.detect_drift('U100', 30.0)
        assert is_drift is True


# ── RiskAggregator Tests ─────────────────────────────────────────────────────

class TestRiskAggregator:
    def test_aggregate_returns_sorted_dataframe(self, aggregator):
        """aggregate_all_users returns DataFrame sorted by total_risk_score desc."""
        df = pd.concat([
            _make_events_df('U100', base_score=5),
            _make_events_df('U101', base_score=50),
        ])
        result = aggregator.aggregate_all_users(df)

        assert isinstance(result, pd.DataFrame)
        assert 'user' in result.columns
        assert 'total_risk_score' in result.columns
        # U101 should be first (higher scores)
        assert result.iloc[0]['user'] == 'U101'

    def test_aggregate_includes_drift_columns(self, aggregator):
        """Result includes is_drift and deviation_sigma columns."""
        df = _make_events_df('U100', base_score=10)
        result = aggregator.aggregate_all_users(df)
        assert 'is_drift' in result.columns
        assert 'deviation_sigma' in result.columns

    def test_aggregate_empty_user(self, aggregator):
        """Empty DataFrame for a user → gracefully handled."""
        df = _make_events_df('U100', n_events=1, base_score=0)
        # This should not crash
        result = aggregator.aggregate_all_users(df)
        assert len(result) == 1

    def test_decay_reduces_old_events(self):
        """Older events contribute less to total via decay."""
        tracker = UserBaselineTracker()

        now = datetime(2024, 1, 10)
        recent_events = pd.DataFrame({
            'user': ['U100'] * 3,
            'date': pd.to_datetime([now - timedelta(hours=1), now - timedelta(hours=2), now]),
            'risk_score': [50.0, 50.0, 50.0],
        })
        old_events = pd.DataFrame({
            'user': ['U100'] * 3,
            'date': pd.to_datetime([now - timedelta(days=10), now - timedelta(days=11), now - timedelta(days=12)]),
            'risk_score': [50.0, 50.0, 50.0],
        })

        recent_agg = tracker.aggregate_user_risk_with_drift(recent_events, now)
        old_agg = tracker.aggregate_user_risk_with_drift(old_events, now)

        # Recent events should contribute more (less decay)
        assert recent_agg['decayed_sum'] > old_agg['decayed_sum']
