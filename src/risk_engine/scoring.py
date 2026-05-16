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
        model_type: str = "lstm"
    ) -> Tuple[float, RiskExplanation]:
        """
        Calculate risk score with full explainability.

        Returns:
            Tuple of (risk_score, RiskExplanation)
        """
        factors = []

        # 1. Base Score Mapping
        base_risk = self._calculate_base_risk(anomaly_score, model_type)
        if base_risk > 10:
            factors.append(f"Anomaly score {anomaly_score:.3f}")

        # 2. Role Multiplier
        user = row.get('user', '')
        role = self.user_roles.get(user, 'Employee')
        role_mult = self.role_multipliers.get(role, 1.0)
        if role_mult > 1.0:
            factors.append(f"{role} role (+{int((role_mult-1)*100)}%)")

        # 3. Time Multiplier
        hour = row.get('hour', row.get('date', pd.Timestamp.now()))
        if hasattr(hour, 'hour'):
            hour = hour.hour

        is_after_hours = hour < self.work_start or hour > self.work_end
        time_mult = self.after_hours_mult if is_after_hours else 1.0
        if is_after_hours:
            factors.append(f"After-hours activity ({hour}:00)")

        # 4. Activity Multiplier (config-driven patterns)
        activity = str(row.get('activity', ''))
        activity_mult = 1.0
        activity_reason = None

        for act_pattern, mult in self.activity_multipliers.items():
            if act_pattern in activity:
                activity_mult = max(activity_mult, mult)
                activity_reason = act_pattern

        if activity_mult > 1.0:
            factors.append(f"{activity_reason} (+{int((activity_mult-1)*100)}%)")

        # 5. Behavioral Feature Boosts
        behavioral_mult = 1.0

        usb_events = row.get('usb_events_7d', 0)
        if usb_events > 3:
            behavioral_mult *= 1.5
            factors.append(f"USB activity spike ({usb_events} events)")

        copies = row.get('file_copy_count_24h', 0)
        if copies > 5:
            behavioral_mult *= 1.3
            factors.append(f"High file copy volume ({copies} files)")

        ah_ratio = row.get('after_hours_ratio', 0)
        if ah_ratio > 0.3:
            behavioral_mult *= 1.2
            factors.append(f"Elevated after-hours pattern ({ah_ratio:.0%})")
        
        # 6. Work-Integrity Multipliers (Vigilant Lens 2.0)
        work_integrity_mult = self._calculate_work_integrity_multiplier(row)
        if work_integrity_mult > 1.0:
            behavioral_mult *= work_integrity_mult
            # Extract explanation from work integrity calculation
            wi_factors = self._get_work_integrity_factors(row)
            factors.extend(wi_factors)

        # 6. Calculate Final Risk
        final_risk = base_risk * role_mult * time_mult * activity_mult * behavioral_mult

        # Heuristic override for dangerous combinations
        if "File Copy" in activity and is_after_hours and usb_events > 0:
            final_risk = max(final_risk, 85)
            factors.append("PATTERN: File copy + USB + After-hours")

        final_risk = min(self.max_risk, final_risk)

        # 7. MITRE Mapping
        mitre = self._get_mitre_mapping(activity, is_after_hours)

        # 8. Build Explanation
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

    def _calculate_base_risk(self, anomaly_score: float, model_type: str) -> float:
        """Convert raw anomaly score to base risk (0-100)."""
        threshold_config = config.thresholds

        if model_type == "lstm":
            mean = threshold_config.get('lstm_anomaly_mean', 0.16)
            deviation = max(0, anomaly_score - mean)
            return min(100, deviation * self.base_multiplier)

        elif model_type == "baseline":
            if anomaly_score < 0:
                return min(100, abs(anomaly_score) * 400)
            return 0

        return 0

    def _get_mitre_mapping(self, activity: str, is_after_hours: bool) -> Dict:
        """Get MITRE ATT&CK mapping for activity."""
        if "Logon" in activity and is_after_hours:
            mapping = self.mitre_mapping.get('After Hours Logon', {})
            if mapping:
                return mapping

        for pattern, mapping in self.mitre_mapping.items():
            if pattern in activity:
                return mapping

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
