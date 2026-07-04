"""
Unit tests for the Risk Scoring Engine (scoring.py).

Covers:
  - AdvancedRiskScoringEngine.calculate_risk_score() with various inputs
  - AlertManager persistence and cooldown logic
  - MITRE ATT&CK mapping lookup
  - Config-driven multipliers
"""

import pytest
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from risk_engine.scoring import (
    AdvancedRiskScoringEngine,
    AlertManager,
    RiskExplanation,
    RiskScoringEngine,  # backward-compatible alias
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Fresh scoring engine per test."""
    e = AdvancedRiskScoringEngine()
    e.user_roles = {
        'U100': 'Employee',
        'U101': 'Admin',
        'U102': 'Contractor',
    }
    return e


@pytest.fixture
def alert_mgr():
    """Fresh AlertManager per test."""
    return AlertManager()


def _make_row(user='U100', hour=10, activity='Logon', **extra):
    """Helper to build a fake event row.

    The scoring engine now consumes DAILY behavioral aggregate columns rather
    than a single 'activity' string / single 'hour'. This helper still accepts
    the legacy kwargs (kept so unchanged tests read naturally) but maps them
    onto the new count columns, and lets callers override any aggregate via
    ``**extra`` (e.g. file_copy_count=, usb_count=, after_hours_ratio=).
    """
    # Derive daily aggregates from the legacy activity/hour so existing tests
    # that only care about "File Copy at night" still exercise the same path.
    after_hours = hour < 7 or hour > 20
    row = {
        'user': user,
        'date': pd.Timestamp(f'2024-01-15 {hour:02d}:00:00'),
        'source': 'Logon',
        'activity': activity,
        'event_count': 10.0,
        'file_copy_count': 3.0 if activity == 'File Copy' else 0.0,
        'usb_count': 0.0,
        'removable_media_count': 0.0,
        'delete_count': 3.0 if activity == 'File Delete' else 0.0,
        # After-hours is now driven by a ratio + a volume gate (>=6 events),
        # not a single hour, so populate both when the legacy hour is nocturnal.
        'after_hours_ratio': 0.8 if after_hours else 0.0,
        'after_hours_count': 8.0 if after_hours else 0.0,
    }
    row.update(extra)
    return row


# ── AdvancedRiskScoringEngine Tests ──────────────────────────────────────────

class TestRiskScoring:
    def test_returns_tuple(self, engine):
        """calculate_risk_score returns (float, RiskExplanation)."""
        row = _make_row()
        result = engine.calculate_risk_score(row, anomaly_score=0.2)
        assert isinstance(result, tuple)
        assert len(result) == 2
        score, explanation = result
        assert isinstance(score, float)
        assert isinstance(explanation, RiskExplanation)

    def test_low_anomaly_returns_zero(self, engine):
        """Anomaly score below mean → risk = 0."""
        row = _make_row()
        score, explanation = engine.calculate_risk_score(row, 0.05, 'lstm')
        assert score == 0
        assert explanation.primary_factor == "Normal activity"

    def test_high_anomaly_caps_at_100(self, engine):
        """Extreme anomaly score → capped at max_risk (100)."""
        row = _make_row(user='U101', hour=23, activity='File Copy')
        score, _ = engine.calculate_risk_score(row, 1.0, 'lstm')
        assert score == 100

    def test_admin_role_multiplier(self, engine):
        """Admin gets higher score than Employee for same event."""
        base_row = _make_row(hour=10, activity='Logon')

        emp_score, _ = engine.calculate_risk_score({**base_row, 'user': 'U100'}, 0.3)
        admin_score, _ = engine.calculate_risk_score({**base_row, 'user': 'U101'}, 0.3)

        assert admin_score >= emp_score, "Admin should score equal or higher than Employee"

    def test_after_hours_multiplier(self, engine):
        """After-hours event gets higher score than daytime."""
        day_row = _make_row(hour=10)
        night_row = _make_row(hour=2)

        day_score, _ = engine.calculate_risk_score(day_row, 0.3)
        night_score, _ = engine.calculate_risk_score(night_row, 0.3)

        assert night_score >= day_score, "After-hours should score equal or higher"

    def test_after_hours_factor_in_explanation(self, engine):
        """A high after-hours ratio over the volume gate adds an after-hours factor.

        After-hours is now derived from after_hours_ratio (> 0.3) combined with
        a volume gate (after_hours_count >= after_hours_min_events), not a single
        clock hour.
        """
        row = _make_row(
            hour=10,  # daytime timestamp; the aggregates drive the signal now
            after_hours_ratio=0.75,
            after_hours_count=8.0,
            event_count=10.0,
        )
        _, explanation = engine.calculate_risk_score(row, 0.4)
        factor_texts = ' '.join(explanation.factors)
        assert 'After-hours' in factor_texts

    def test_after_hours_volume_gate_suppresses_low_activity(self, engine):
        """A high after-hours RATIO on a tiny-volume day must NOT flag after-hours.

        The volume gate suppresses noise: one stray late event on a 2-event day
        would otherwise make the ratio look extreme.
        """
        row = _make_row(
            hour=10,
            after_hours_ratio=1.0,     # every event was after-hours...
            after_hours_count=1.0,     # ...but there was only ONE event (below gate)
            event_count=1.0,
        )
        _, explanation = engine.calculate_risk_score(row, 0.4)
        factor_texts = ' '.join(explanation.factors)
        assert 'After-hours' not in factor_texts

    def test_file_copy_activity_multiplier(self, engine):
        """File Copy activity gets a multiplier boost."""
        normal_row = _make_row(activity='Logon')
        copy_row = _make_row(activity='File Copy')

        normal_score, _ = engine.calculate_risk_score(normal_row, 0.3)
        copy_score, _ = engine.calculate_risk_score(copy_row, 0.3)

        assert copy_score >= normal_score

    def test_heuristic_override_file_copy_usb_afterhours(self, engine):
        """Bulk file copy + USB connect + after-hours on one day → at least 85.

        The exfil pattern override now fires when the daily aggregates show
        file_copy_count > 0 AND usb_count > 0 AND the after-hours gate is met.
        """
        row = _make_row(
            hour=10,
            file_copy_count=12.0,
            usb_count=3.0,
            after_hours_ratio=0.8,
            after_hours_count=9.0,
            event_count=20.0,
        )
        score, explanation = engine.calculate_risk_score(row, 0.4)
        assert score >= 85
        assert any('PATTERN' in f for f in explanation.factors)

    def test_no_override_without_after_hours(self, engine):
        """File copy + USB but WITHOUT after-hours does not trigger the override.

        Removing the after-hours condition must drop the PATTERN factor, proving
        the override genuinely depends on all three signals (not file+USB alone).
        """
        row = _make_row(
            hour=10,
            file_copy_count=12.0,
            usb_count=3.0,
            after_hours_ratio=0.0,
            after_hours_count=0.0,
            event_count=20.0,
        )
        _, explanation = engine.calculate_risk_score(row, 0.4)
        assert not any('PATTERN' in f for f in explanation.factors)

    def test_baseline_model_type(self, engine):
        """Baseline (Isolation Forest) model type works."""
        row = _make_row()
        score, _ = engine.calculate_risk_score(row, -0.5, 'baseline')
        assert score > 0  # negative anomaly score = more anomalous

    def test_baseline_positive_returns_zero(self, engine):
        """Baseline positive score → risk = 0."""
        row = _make_row()
        score, _ = engine.calculate_risk_score(row, 0.5, 'baseline')
        assert score == 0

    def test_backward_compatible_alias(self):
        """RiskScoringEngine is an alias for AdvancedRiskScoringEngine."""
        assert RiskScoringEngine is AdvancedRiskScoringEngine


# ── MITRE Mapping Tests ──────────────────────────────────────────────────────

class TestMitreMapping:
    def test_file_copy_maps_to_exfiltration(self, engine):
        """A day with file-copy activity maps to TA0010 Exfiltration."""
        mitre = engine._get_mitre_mapping(file_copy_count=3.0)
        assert mitre.get('tactic') == 'TA0010'
        assert mitre.get('technique') == 'T1052'

    def test_usb_connect_maps_to_exfiltration(self, engine):
        """USB connect activity maps to TA0010 Exfiltration (Hardware Additions)."""
        mitre = engine._get_mitre_mapping(usb_count=2.0)
        assert mitre.get('tactic') == 'TA0010'
        assert mitre.get('technique') == 'T1200'

    def test_file_delete_maps_to_impact(self, engine):
        """File-delete activity maps to TA0040 Impact (Data Destruction)."""
        mitre = engine._get_mitre_mapping(delete_count=1.0)
        assert mitre.get('tactic') == 'TA0040'
        assert mitre.get('technique') == 'T1485'

    def test_after_hours_maps_to_credential_access(self, engine):
        """An after-hours-only day maps to Credential Access."""
        mitre = engine._get_mitre_mapping(is_after_hours=True)
        assert mitre.get('tactic') == 'TA0006'

    def test_file_copy_takes_priority_over_after_hours(self, engine):
        """File copy outranks after-hours logon in the mapping priority."""
        mitre = engine._get_mitre_mapping(file_copy_count=5.0, is_after_hours=True)
        # Exfiltration (File Copy) wins over Credential Access (after-hours).
        assert mitre.get('tactic') == 'TA0010'

    def test_no_activity_returns_empty(self, engine):
        """No behavioral counts and no after-hours → empty dict."""
        mitre = engine._get_mitre_mapping()
        assert mitre == {}


# ── AlertManager Tests ───────────────────────────────────────────────────────

class TestAlertManager:
    def test_below_threshold_no_alert(self, alert_mgr):
        """Score below medium threshold → no alert."""
        should, severity = alert_mgr.should_generate_alert('U100', 50.0, datetime.now())
        assert should is False
        assert severity == ''

    def test_persistence_requires_multiple_events(self, alert_mgr):
        """First high-risk event doesn't alert alone (persistence_count=2)."""
        t = datetime.now()
        should1, _ = alert_mgr.should_generate_alert('U100', 90.0, t)
        # First event → below persistence count → no alert
        assert should1 is False

        should2, severity = alert_mgr.should_generate_alert('U100', 90.0, t + timedelta(minutes=5))
        # Second event → meets persistence count → alert
        assert should2 is True
        assert severity == 'HIGH'

    def test_cooldown_suppresses_non_critical(self, alert_mgr):
        """After alerting, non-critical alerts are suppressed during cooldown."""
        t = datetime.now()
        # Trigger 2 events to generate alert
        alert_mgr.should_generate_alert('U100', 90.0, t)
        alert_mgr.should_generate_alert('U100', 90.0, t + timedelta(minutes=1))

        # Now in cooldown — HIGH should be suppressed
        should, _ = alert_mgr.should_generate_alert('U100', 90.0, t + timedelta(minutes=30))
        # First event resets count, won't alert immediately
        # But even on second try within cooldown, non-critical is suppressed
        should2, _ = alert_mgr.should_generate_alert('U100', 90.0, t + timedelta(minutes=31))
        assert should2 is False

    def test_critical_bypasses_cooldown(self, alert_mgr):
        """CRITICAL alerts bypass cooldown."""
        t = datetime.now()
        # Generate initial alert
        alert_mgr.should_generate_alert('U100', 90.0, t)
        alert_mgr.should_generate_alert('U100', 90.0, t + timedelta(minutes=1))

        # Critical during cooldown
        alert_mgr.should_generate_alert('U100', 99.0, t + timedelta(minutes=10))
        should, severity = alert_mgr.should_generate_alert('U100', 99.0, t + timedelta(minutes=11))
        assert should is True
        assert severity == 'CRITICAL'

    def test_get_alert_stats(self, alert_mgr):
        """get_alert_stats returns dict with expected keys."""
        stats = alert_mgr.get_alert_stats()
        assert 'users_in_warning' in stats
        assert 'users_in_cooldown' in stats
