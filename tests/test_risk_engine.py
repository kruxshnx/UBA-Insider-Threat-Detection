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
    """Helper to build a fake event row."""
    return {
        'user': user,
        'date': pd.Timestamp(f'2024-01-15 {hour:02d}:00:00'),
        'hour': hour,
        'source': 'Logon',
        'activity': activity,
        **extra,
    }


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
        """After-hours triggers a factor in the explanation."""
        row = _make_row(hour=3)
        _, explanation = engine.calculate_risk_score(row, 0.4)
        factor_texts = ' '.join(explanation.factors)
        assert 'After-hours' in factor_texts

    def test_file_copy_activity_multiplier(self, engine):
        """File Copy activity gets a multiplier boost."""
        normal_row = _make_row(activity='Logon')
        copy_row = _make_row(activity='File Copy')

        normal_score, _ = engine.calculate_risk_score(normal_row, 0.3)
        copy_score, _ = engine.calculate_risk_score(copy_row, 0.3)

        assert copy_score >= normal_score

    def test_heuristic_override_file_copy_usb_afterhours(self, engine):
        """File Copy + USB + after-hours → at least 85."""
        row = _make_row(hour=2, activity='File Copy', usb_events_7d=5)
        score, explanation = engine.calculate_risk_score(row, 0.4)
        assert score >= 85
        assert any('PATTERN' in f for f in explanation.factors)

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
        """File Copy should map to TA0010 Exfiltration."""
        mitre = engine._get_mitre_mapping('File Copy', False)
        assert mitre.get('tactic') == 'TA0010'

    def test_logon_after_hours_maps_to_credential_access(self, engine):
        """Logon + after-hours should map to Credential Access."""
        mitre = engine._get_mitre_mapping('Logon', True)
        # Could be TA0006 (After Hours Logon) or TA0001 (Logon)
        assert mitre.get('tactic') in ('TA0006', 'TA0001')

    def test_unknown_activity_returns_empty(self, engine):
        """Unknown activity returns empty dict."""
        mitre = engine._get_mitre_mapping('SomeRandomActivity', False)
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
