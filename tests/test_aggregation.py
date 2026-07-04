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
        """Enough history → valid baseline from the EARLIER-period days.

        The baseline now excludes the most-recent ``recent_window`` days and is
        computed only over the earlier days (so drift compares recent behavior to
        the user's own earlier behavior). We therefore need more than
        recent_window days of history, and avg/std are over the earlier slice.
        """
        # 10 chronological daily-risk values; the last recent_window are the
        # "current" window and are excluded from the baseline.
        scores = [10.0, 12.0, 8.0, 15.0, 9.0, 11.0, 10.0, 13.0, 7.0, 9.0]
        baseline_slice = scores[:-tracker.recent_window]
        assert len(baseline_slice) >= 3  # sanity: enough earlier days

        result = tracker.update_baseline('U100', scores)
        assert result['valid'] is True
        assert result['count'] == len(baseline_slice)
        # avg/std are computed over the EARLIER-period slice, not all scores.
        assert result['avg'] == pytest.approx(np.mean(baseline_slice))
        assert result['std'] == pytest.approx(np.std(baseline_slice))

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
        """Recent daily risk within N-sigma of the earlier baseline → no drift.

        Feed enough history for a VALID baseline (more than recent_window days)
        so the "within sigma" branch — not the insufficient-data branch — is what
        returns False.
        """
        history = [10, 11, 9, 12, 10, 8, 10, 11, 9, 10]
        tracker.update_baseline('U100', history)
        baseline = tracker.user_baselines['U100']
        assert baseline['valid'] is True

        # A recent daily risk of 12 sits within drift_sigma of the ~10 baseline.
        is_drift, z, _ = tracker.detect_drift('U100', 12.0)
        assert is_drift is False
        assert z <= tracker.drift_sigma

    def test_detect_drift_above_sigma(self, tracker):
        """Recent daily risk far above the user's earlier baseline → drift.

        The baseline is built from the earlier-period days (recent_window days
        are excluded), so we feed a quiet daily history and then probe with a
        recent daily-risk value many sigma above that quiet baseline.
        """
        # 10 quiet days; earlier-period baseline ≈ 10 with small std.
        history = [10, 11, 9, 12, 10, 8, 10, 11, 9, 10]
        tracker.update_baseline('U100', history)
        baseline = tracker.user_baselines['U100']
        assert baseline['valid'] is True

        # A recent daily risk of 20 is many sigma above the ~10 baseline.
        is_drift, z, _ = tracker.detect_drift('U100', 20.0)
        assert is_drift is True
        assert z > tracker.drift_sigma

    def test_detect_drift_low_variance_user(self, tracker):
        """Very low variance user — a clear absolute jump triggers drift.

        With a near-zero-variance baseline the sigma test is meaningless, so the
        engine falls back to an absolute-jump rule (recent > baseline avg + 15).
        Feed enough flat history for a valid, ~0-std baseline, then probe with a
        recent value well above avg + 15.
        """
        tracker.update_baseline('U100', [5.0] * 10)
        baseline = tracker.user_baselines['U100']
        assert baseline['valid'] is True
        assert baseline['std'] < 1.0  # low-variance branch applies

        # Recent daily risk of 30 is 25 above the flat baseline of 5 → drift.
        is_drift, _, _ = tracker.detect_drift('U100', 30.0)
        assert is_drift is True

    def test_detect_drift_low_variance_small_jump_no_drift(self, tracker):
        """Low-variance user with only a small jump stays within range → no drift.

        A recent value just a few points above the flat baseline must NOT trip
        drift (the absolute-jump gate is +15), proving the low-variance branch
        isn't hair-trigger.
        """
        tracker.update_baseline('U100', [5.0] * 10)
        baseline = tracker.user_baselines['U100']
        assert baseline['std'] < 1.0

        # 10 is only +5 above the baseline of 5 — below the +15 absolute gate.
        is_drift, _, _ = tracker.detect_drift('U100', 10.0)
        assert is_drift is False


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
