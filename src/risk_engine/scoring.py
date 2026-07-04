"""
Risk Scoring Engine — Config-Driven with Explainability & MITRE Mapping.

Features:
  - Contextual risk scoring with config-driven multipliers
  - Alert logic with persistence and cooldown
  - Explainability layer (why was this flagged?)
  - MITRE ATT&CK mapping

Consolidated from scoring_v2.py as the canonical implementation.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.risk_engine.scoring")


@dataclass
class RiskExplanation:
    """Structured explanation for why an event was flagged."""
    primary_factor: str
    factors: List[str]
    mitre_tactic: str
    mitre_technique: str
    text_explanation: str
    risk_score: float


class AlertManager:
    """
    Manages alert generation with persistence and cooldown logic.
    Thresholds are read from config.yaml → alerting section.
    """

    def __init__(self):
        self.alert_config = config.alerting
        self.medium_threshold = self.alert_config.get('medium_threshold', 70)
        self.high_threshold = self.alert_config.get('high_threshold', 85)
        self.critical_threshold = self.alert_config.get('critical_threshold', 95)
        self.persistence_count = self.alert_config.get('persistence_count', 2)
        self.cooldown_hours = self.alert_config.get('cooldown_hours', 24)

        # Track user alert state
        self.user_high_risk_counts: Dict[str, int] = {}
        self.user_last_alert: Dict[str, datetime] = {}

    def should_generate_alert(self, user: str, risk_score: float, event_time: datetime) -> Tuple[bool, str]:
        """
        Determine if an alert should be generated based on persistence and cooldown.

        Returns:
            Tuple of (should_alert, severity)
        """
        if risk_score >= self.critical_threshold:
            severity = "CRITICAL"
        elif risk_score >= self.high_threshold:
            severity = "HIGH"
        elif risk_score >= self.medium_threshold:
            severity = "MEDIUM"
        else:
            self.user_high_risk_counts[user] = 0
            return False, ""

        # Check cooldown
        last_alert = self.user_last_alert.get(user)
        if last_alert:
            hours_since = (event_time - last_alert).total_seconds() / 3600
            if hours_since < self.cooldown_hours:
                if severity != "CRITICAL":
                    return False, ""

        # Check persistence
        current_count = self.user_high_risk_counts.get(user, 0) + 1
        self.user_high_risk_counts[user] = current_count

        if current_count >= self.persistence_count:
            self.user_last_alert[user] = event_time
            self.user_high_risk_counts[user] = 0
            return True, severity

        return False, ""

    def get_alert_stats(self) -> Dict:
        """Return current alert state statistics."""
        return {
            'users_in_warning': len([u for u, c in self.user_high_risk_counts.items() if c > 0]),
            'users_in_cooldown': len(self.user_last_alert),
        }


class AdvancedRiskScoringEngine:
    """
    Config-driven risk scoring with explainability and MITRE mapping.

    All multipliers, thresholds, and work-hour definitions are read
    from config.yaml at init time. No hardcoded business logic.
    """

    def __init__(self):
        self.risk_config = config.risk_scoring
        self.mitre_mapping = config.mitre_mapping
        self.features_config = config.features

        self.role_multipliers = self.risk_config.get('role_multipliers', {
            'Admin': 1.5, 'Contractor': 1.2, 'Employee': 1.0
        })
        self.activity_multipliers = self.risk_config.get('activity_multipliers', {})
        self.after_hours_mult = self.risk_config.get('after_hours_multiplier', 1.5)
        self.base_multiplier = self.risk_config.get('base_multiplier', 250)
        self.max_risk = self.risk_config.get('max_risk', 100)
        
        # Work-Integrity multipliers (new for Vigilant Lens 2.0)
        self.work_integrity_config = self.risk_config.get('work_integrity', {})
        self.productivity_penalty = self.work_integrity_config.get('productivity_penalty', 1.3)
        self.anomalous_velocity_mult = self.work_integrity_config.get('anomalous_velocity_mult', 2.0)
        self.entropy_high_mult = self.work_integrity_config.get('entropy_high_mult', 1.5)
        self.entropy_critical_mult = self.work_integrity_config.get('entropy_critical_mult', 2.5)
        self.mouse_tortuosity_threshold = self.work_integrity_config.get('mouse_tortuosity_threshold', 3.0)
        self.keystroke_anomaly_threshold = self.work_integrity_config.get('keystroke_anomaly_threshold', 0.5)

        self.work_start = self.features_config.get('work_start_hour', 7)
        self.work_end = self.features_config.get('work_end_hour', 20)

        # Minimum after-hours events before a day counts as an after-hours
        # session (volume gate — suppresses noise from low-activity days where a
        # single stray late event would otherwise make the ratio look extreme).
        self.after_hours_min_events = self.features_config.get('after_hours_min_events', 6)

        # Base-risk assigned when the LSTM error equals the role's anomaly
        # threshold. Kept MODERATE (below the alert line) so that only errors
        # well beyond the threshold saturate to 100 — this preserves a graded
        # 0-100 score and stops rare-but-benign days from auto-alerting.
        self.threshold_base = self.risk_config.get('threshold_base_risk', 45.0)

        # User metadata cache
        self.user_roles: Dict[str, str] = {}
        self.alert_manager = AlertManager()

        logger.info(
            "RiskScoringEngine initialised — roles=%s, work_hours=%d-%d",
            list(self.role_multipliers.keys()), self.work_start, self.work_end,
        )

    def load_user_metadata(self, users_path: str) -> None:
        """Load user role metadata from CSV."""
        if os.path.exists(users_path):
            users_df = pd.read_csv(users_path)
            self.user_roles = dict(zip(users_df['id'], users_df['role']))
            logger.info("Loaded metadata for %d users.", len(self.user_roles))

    def calculate_risk_score(
        self,
        row: pd.Series,
        anomaly_score: float,
        model_type: str = "lstm",
        role_meta: Optional[Dict] = None,
    ) -> Tuple[float, RiskExplanation]:
        """
        Calculate risk score with full explainability.

        Operates on a DAILY user-day feature row containing behavioral aggregate
        columns (file_copy_count, usb_count, removable_media_count, delete_count,
        after_hours_count, after_hours_ratio, event_count). The single-'activity'
        / single-'hour' logic has been replaced by count-driven logic so it works
        on the daily featured timeline.

        Args:
            row: daily feature row for a user-day
            anomaly_score: LSTM reconstruction error for that day
            model_type: "lstm" or "baseline"
            role_meta: the user's role metadata (error_mean/error_std/threshold)
                       used to normalise the base risk relative to the role.

        Returns:
            Tuple of (risk_score, RiskExplanation)
        """
        factors = []

        # --- Read daily behavioral aggregates ---
        def _num(key, default=0.0):
            try:
                v = row.get(key, default)
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return default
                return float(v)
            except Exception:
                return default

        file_copy_count = _num('file_copy_count')
        usb_count = _num('usb_count')
        removable_count = _num('removable_media_count')
        delete_count = _num('delete_count')
        ah_ratio = _num('after_hours_ratio')
        ah_count = _num('after_hours_count')
        event_count = _num('event_count')

        # 1. Base Score Mapping (normalised relative to the role's error dist)
        base_risk = self._calculate_base_risk(anomaly_score, model_type, role_meta)
        if base_risk > 10:
            factors.append(f"Anomaly score {anomaly_score:.3f} (role-normalised)")

        # 2. Role Multiplier
        user = row.get('user', '')
        role = self.user_roles.get(user, 'Employee')
        role_mult = self.role_multipliers.get(role, 1.0)
        if role_mult > 1.0:
            factors.append(f"{role} role (+{int((role_mult-1)*100)}%)")

        # 3. Time Multiplier — derived from after_hours_ratio, NOT a single hour.
        #    (Daily rows carry midnight timestamps, so a single hour would flag
        #     everyone; the ratio of after-hours events is the honest signal.)
        #    A VOLUME GATE is applied: a high ratio on a 1-2 event day is noise,
        #    not an after-hours exfil session, so we also require several
        #    after-hours events before treating the day as after-hours.
        is_after_hours = ah_ratio > 0.3 and ah_count >= self.after_hours_min_events
        time_mult = self.after_hours_mult if is_after_hours else 1.0
        if is_after_hours:
            factors.append(f"After-hours activity pattern ({ah_ratio:.0%}, {int(ah_count)} events)")

        # 4. Activity Multiplier — max of the config multipliers that apply,
        #    based on which behavioral counts are non-zero this day.
        activity_mult = 1.0
        activity_reason = None
        count_by_pattern = {
            'File Copy': file_copy_count,
            'Connect': usb_count,
            'File Delete': delete_count,
        }
        for act_pattern, mult in self.activity_multipliers.items():
            if act_pattern == 'default':
                continue
            if count_by_pattern.get(act_pattern, 0) > 0 and mult > activity_mult:
                activity_mult = mult
                activity_reason = act_pattern
        if activity_mult > 1.0 and activity_reason:
            factors.append(f"{activity_reason} activity (+{int((activity_mult-1)*100)}%)")

        # 5. Behavioral Feature Boosts (from the daily aggregates)
        behavioral_mult = 1.0

        if usb_count > 0:
            behavioral_mult *= 1.5
            factors.append(f"USB connect activity ({int(usb_count)} events)")

        if removable_count > 0:
            behavioral_mult *= 1.4
            factors.append(f"Removable-media writes ({int(removable_count)} files)")

        if file_copy_count > 5:
            behavioral_mult *= 1.3
            factors.append(f"High file-copy volume ({int(file_copy_count)} files)")

        if is_after_hours:
            behavioral_mult *= 1.2
            factors.append(f"Elevated after-hours ratio ({ah_ratio:.0%})")

        # 6. Work-Integrity Multipliers (Vigilant Lens 2.0) — inert unless the
        #    telemetry columns are present; retained for forward compatibility.
        work_integrity_mult = self._calculate_work_integrity_multiplier(row)
        if work_integrity_mult > 1.0:
            behavioral_mult *= work_integrity_mult
            factors.extend(self._get_work_integrity_factors(row))

        # 7. Calculate Final Risk
        final_risk = base_risk * role_mult * time_mult * activity_mult * behavioral_mult

        # Pattern override for the classic exfil combination:
        #   bulk file copy + USB connect + after-hours all on the same day.
        pattern_hit = file_copy_count > 0 and usb_count > 0 and is_after_hours
        if pattern_hit:
            final_risk = max(final_risk, 85)
            factors.append("PATTERN: File copy + USB + After-hours exfil")

        final_risk = min(self.max_risk, final_risk)

        # 8. MITRE Mapping — derived from which behavioral counts fired.
        mitre = self._get_mitre_mapping(
            file_copy_count=file_copy_count,
            usb_count=usb_count,
            delete_count=delete_count,
            is_after_hours=is_after_hours,
        )

        # 9. Build Explanation
        primary_factor = factors[0] if factors else "Normal activity"
        text_explanation = self._build_explanation(final_risk, factors, mitre)

        explanation = RiskExplanation(
            primary_factor=primary_factor,
            factors=factors,
            mitre_tactic=mitre.get('tactic', ''),
            mitre_technique=mitre.get('technique', ''),
            text_explanation=text_explanation,
            risk_score=final_risk
        )

        return final_risk, explanation

    def _calculate_base_risk(
        self,
        anomaly_score: float,
        model_type: str,
        role_meta: Optional[Dict] = None,
    ) -> float:
        """
        Convert a raw anomaly score to base risk (0-100), normalised RELATIVE to
        the role's reconstruction-error distribution.

        For the LSTM path we map the error onto the interval
        [error_mean, threshold]:
            base = (error - error_mean) / (threshold - error_mean) * 100
        clamped to 0-100. A normal day (~error_mean) maps near 0, a day at the
        role's anomaly threshold maps to ~100, and there is no universal
        saturation because the scale adapts per role. Falls back to a z-score
        when threshold/mean are unusable.
        """
        if model_type == "lstm":
            if role_meta:
                error_mean = float(role_meta.get('error_mean', 0.0))
                error_std = float(role_meta.get('error_std', 0.0))
                threshold = float(role_meta.get('threshold', 0.0))

                span = threshold - error_mean
                if span > 1e-6:
                    # Map error_mean -> 0 and the role's anomaly threshold ->
                    # THRESHOLD_BASE (a MODERATE base, not saturation). The slope
                    # continues beyond the threshold so genuinely extreme errors
                    # (many multiples of the threshold, e.g. bulk exfil) climb to
                    # 100, while borderline days that merely graze the percentile
                    # threshold stay well below the alert line. This is what
                    # separates U105's huge reconstruction errors from ordinary
                    # rare-but-benign days.
                    frac = (anomaly_score - error_mean) / span
                    base = frac * self.threshold_base
                    return float(min(100.0, max(0.0, base)))

                # Fallback: z-score scaled so ~+3 sigma -> ~75
                if error_std > 1e-6:
                    z = (anomaly_score - error_mean) / error_std
                    return float(min(100.0, max(0.0, z * 25.0)))

            # No metadata available: fall back to the legacy fixed mapping.
            threshold_config = config.thresholds
            mean = threshold_config.get('lstm_anomaly_mean', 0.16)
            deviation = max(0.0, anomaly_score - mean)
            return float(min(100.0, deviation * self.base_multiplier))

        elif model_type == "baseline":
            if anomaly_score < 0:
                return float(min(100.0, abs(anomaly_score) * 400))
            return 0.0

        return 0.0

    def _get_mitre_mapping(
        self,
        file_copy_count: float = 0.0,
        usb_count: float = 0.0,
        delete_count: float = 0.0,
        is_after_hours: bool = False,
    ) -> Dict:
        """Get MITRE ATT&CK mapping derived from which daily counts fired.

        Priority: exfil (File Copy) > USB (Connect) > destruction (Delete) >
        after-hours logon.
        """
        if file_copy_count > 0:
            m = self.mitre_mapping.get('File Copy', {})
            if m:
                return m
        if usb_count > 0:
            m = self.mitre_mapping.get('Connect', {})
            if m:
                return m
        if delete_count > 0:
            m = self.mitre_mapping.get('File Delete', {})
            if m:
                return m
        if is_after_hours:
            m = self.mitre_mapping.get('After Hours Logon', {})
            if m:
                return m
        return {}

    def _build_explanation(self, risk: float, factors: List[str], mitre: Dict) -> str:
        """Build human-readable explanation."""
        if risk < 50:
            return "Low risk - normal activity pattern."

        explanation = f"Risk score {risk:.0f}/100. "

        if factors:
            explanation += "Contributing factors: " + "; ".join(factors[:3]) + ". "

        if mitre:
            explanation += f"Maps to MITRE {mitre.get('tactic', '')} - {mitre.get('tactic_name', '')}."

        return explanation
    
    def _calculate_work_integrity_multiplier(self, row: pd.Series) -> float:
        """
        Calculate Work-Integrity Multiplier based on behavioral telemetry.
        
        This implements the "Productivity-Security Nexus" by detecting:
        - Low productivity app ratio (distraction or evasion)
        - Anomalous file operation velocity
        - High session entropy (erratic behavior)
        - Abnormal mouse/keystroke dynamics
        
        Returns:
            Multiplier value (1.0 = normal, >1.0 = elevated risk)
        """
        multiplier = 1.0
        
        # 1. Productivity Penalty
        productive_ratio = row.get('productive_app_ratio', 1.0)
        if productive_ratio < 0.5:  # Less than 50% productive time
            multiplier *= self.productivity_penalty
        
        # 2. Anomalous Velocity Detection
        file_velocity = row.get('file_op_velocity', 0.0)
        baseline_velocity = row.get('baseline_file_velocity', 1.0)
        if baseline_velocity > 0 and file_velocity > (5 * baseline_velocity):
            multiplier *= self.anomalous_velocity_mult
        
        # 3. Session Entropy Risk
        entropy_risk = row.get('entropy_risk_level', 'Low')
        if entropy_risk == 'Critical':
            multiplier *= self.entropy_critical_mult
        elif entropy_risk == 'High':
            multiplier *= self.entropy_high_mult
        elif entropy_risk == 'Medium':
            multiplier *= 1.2
        
        # 4. Mouse Dynamics Anomaly
        mouse_tortuosity = row.get('mouse_tortuosity_index', 1.0)
        if mouse_tortuosity > self.mouse_tortuosity_threshold:
            multiplier *= 1.3  # Erratic mouse movement
        
        # 5. Keystroke Dynamics Anomaly
        keystroke_anomaly_score = row.get('keystroke_anomaly_score', 0.0)
        if keystroke_anomaly_score > self.keystroke_anomaly_threshold:
            multiplier *= 1.3  # Abnormal typing pattern
        
        return multiplier
    
    def _get_work_integrity_factors(self, row: pd.Series) -> List[str]:
        """
        Extract work integrity factors for explainability.
        
        Returns:
            List of factor strings explaining the work integrity risk
        """
        factors = []
        
        # Productivity
        productive_ratio = row.get('productive_app_ratio', 1.0)
        if productive_ratio < 0.5:
            factors.append(f"Low productivity ratio ({productive_ratio:.0%})")
        
        # Anomalous velocity
        file_velocity = row.get('file_op_velocity', 0.0)
        baseline_velocity = row.get('baseline_file_velocity', 1.0)
        if baseline_velocity > 0 and file_velocity > (5 * baseline_velocity):
            factors.append(f"Anomalous file velocity ({file_velocity:.1f}x baseline)")
        
        # Entropy
        entropy_risk = row.get('entropy_risk_level', 'Low')
        if entropy_risk in ['High', 'Critical']:
            factors.append(f"High session entropy ({entropy_risk})")
        
        # Mouse dynamics
        mouse_tortuosity = row.get('mouse_tortuosity_index', 1.0)
        if mouse_tortuosity > self.mouse_tortuosity_threshold:
            factors.append(f"Erratic mouse pattern (tortuosity={mouse_tortuosity:.1f})")
        
        # Keystroke dynamics
        keystroke_anomaly_score = row.get('keystroke_anomaly_score', 0.0)
        if keystroke_anomaly_score > self.keystroke_anomaly_threshold:
            factors.append(f"Abnormal keystroke rhythm (anomaly={keystroke_anomaly_score:.2f})")
        
        return factors

    def process_dataframe(
        self,
        df: pd.DataFrame,
        anomaly_scores: np.ndarray
    ) -> pd.DataFrame:
        """
        Process entire dataframe with risk scoring and explainability.

        Returns:
            DataFrame with risk_score and explanation columns
        """
        risk_scores = []
        explanations = []
        mitre_tactics = []
        should_alerts = []
        alert_severities = []

        for idx, row in df.iterrows():
            score_idx = min(idx, len(anomaly_scores) - 1)
            anomaly = anomaly_scores[score_idx] if len(anomaly_scores) > 0 else 0

            risk, explanation = self.calculate_risk_score(row, anomaly)

            risk_scores.append(risk)
            explanations.append(explanation.text_explanation)
            mitre_tactics.append(explanation.mitre_tactic)

            event_time = row.get('date', datetime.now())
            should_alert, severity = self.alert_manager.should_generate_alert(
                row['user'], risk, event_time
            )
            should_alerts.append(should_alert)
            alert_severities.append(severity)

        df['risk_score'] = risk_scores
        df['explanation'] = explanations
        df['mitre_tactic'] = mitre_tactics
        df['should_alert'] = should_alerts
        df['alert_severity'] = alert_severities

        return df


# ── Backward-compatible aliases ──────────────────────────────────────────────
# These ensure any code importing RiskScoringEngine still works.
RiskScoringEngine = AdvancedRiskScoringEngine

# Global singleton instances
alert_manager = AlertManager()
risk_engine = AdvancedRiskScoringEngine()
