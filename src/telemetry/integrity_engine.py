"""
Work Integrity Engine.

Implements:
1. Productivity Alignment: Compare active app against role-permitted list
2. Signature Matching: Detect deviations from user's behavioral baseline
3. Risk Multiplier Calculation
"""

import yaml
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import math

logger = logging.getLogger("uba.telemetry.integrity")


class WorkIntegrityEngine:
    """
    Calculates work integrity metrics and risk multipliers.
    
    Features:
    - Productivity Alignment Score
    - Behavioral Signature Matching (2-sigma rule)
    - Dynamic Risk Multiplier
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.role_app_mapping = self._load_role_app_mapping()
        self.productivity_weights = self._load_productivity_weights()
        
        logger.info("WorkIntegrityEngine initialized")
    
    def _load_role_app_mapping(self) -> Dict[str, List[str]]:
        """Load role-to-application mapping from YAML."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('role_app_mapping', {})
        except Exception as e:
            logger.error(f"Error loading role-app mapping: {e}")
            return {}
    
    def _load_productivity_weights(self) -> Dict:
        """Load productivity weights from config."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('productivity', {})
        except Exception as e:
            logger.error(f"Error loading productivity weights: {e}")
            return {}
    
    def calculate_productivity_alignment(
        self,
        active_app: str,
        user_role: str,
        window_title: str = ""
    ) -> Tuple[float, str, str]:
        """
        Calculate productivity alignment score.
        
        Compares active application against role-permitted list.
        
        Args:
            active_app: Current application name
            user_role: User's role (Admin, Developer, HR, etc.)
            window_title: Window title for additional context
        
        Returns:
            Tuple of (score, category, explanation)
            - score: 0.0 to 1.0 (1.0 = fully aligned)
            - category: "productive" | "neutral" | "distracted"
            - explanation: Human-readable explanation
        """
        # Get role-specific permitted apps
        role_apps = self.role_app_mapping.get(user_role, [])
        
        # Normalize app name
        active_app_lower = active_app.lower()
        
        # Check if app is in role-permitted list
        is_permitted = any(
            permitted.lower() in active_app_lower 
            for permitted in role_apps
        )
        
        # Check against global productive/neutral/distracted lists
        productive_apps = self.productivity_weights.get('productive_apps', [])
        neutral_apps = self.productivity_weights.get('neutral_apps', [])
        distracted_apps = self.productivity_weights.get('distracted_apps', [])
        
        # Determine category
        if is_permitted or any(app in active_app_lower for app in productive_apps):
            category = "productive"
            score = 1.0
            explanation = f"Using role-permitted app: {active_app}"
        
        elif any(app in active_app_lower for app in neutral_apps):
            category = "neutral"
            score = 0.7
            explanation = f"Using neutral app: {active_app}"
        
        elif any(app in active_app_lower for app in distracted_apps):
            category = "distracted"
            score = 0.2
            explanation = f"Distracted by non-work app: {active_app}"
        
        else:
            # Unknown app - check if it matches any known patterns
            category = "neutral"
            score = 0.5
            explanation = f"Unknown application: {active_app}"
        
        return score, category, explanation
    
    def calculate_signature_deviation(
        self,
        current_mouse_velocity: float,
        current_mouse_std: float,
        current_flight_time: float,
        current_flight_std: float,
        baseline: Dict
    ) -> Tuple[float, float, str]:
        """
        Calculate behavioral signature deviation.
        
        Uses 2-sigma rule: If current metrics deviate > 2σ from
        7-day baseline, flag as potential account takeover or impaired user.
        
        Args:
            current_mouse_velocity: Current session mouse velocity avg
            current_mouse_std: Current session mouse velocity std
            current_flight_time: Current keystroke flight time avg
            current_flight_std: Current keystroke flight time std
            baseline: User's 7-day baseline metrics
        
        Returns:
            Tuple of (deviation_score, sigma_level, interpretation)
        """
        if not baseline:
            return 0.0, 0.0, "No baseline available"
        
        # Extract baseline metrics
        baseline_mv_avg = baseline.get('mouse_velocity_avg', 0)
        baseline_mv_std = baseline.get('mouse_velocity_std', 1)
        baseline_kf_avg = baseline.get('keystroke_flight_avg_ms', 0)
        baseline_kf_std = baseline.get('keystroke_flight_std_ms', 1)
        
        # Calculate z-scores
        mv_zscore = abs(current_mouse_velocity - baseline_mv_avg) / (baseline_mv_std + 1e-6)
        kf_zscore = abs(current_flight_time - baseline_kf_avg) / (baseline_kf_std + 1e-6)
        
        # Combined deviation score
        combined_zscore = (mv_zscore + kf_zscore) / 2
        
        # Determine sigma level
        if combined_zscore > 3.0:
            sigma_level = 3.0
            interpretation = "CRITICAL: >3σ deviation - Potential account takeover"
        elif combined_zscore > 2.0:
            sigma_level = 2.0
            interpretation = "HIGH: >2σ deviation - Impaired user or different person"
        elif combined_zscore > 1.5:
            sigma_level = 1.5
            interpretation = "MODERATE: >1.5σ deviation - Unusual pattern"
        else:
            sigma_level = combined_zscore
            interpretation = "NORMAL: Within expected range"
        
        # Normalize deviation score to 0-1
        deviation_score = min(1.0, combined_zscore / 3.0)
        
        return deviation_score, sigma_level, interpretation
    
    def calculate_risk_multiplier(
        self,
        productivity_score: float,
        signature_deviation: float,
        sigma_level: float,
        context_factors: Optional[Dict] = None
    ) -> float:
        """
        Calculate dynamic risk multiplier.
        
        Args:
            productivity_score: Productivity alignment score (0-1)
            signature_deviation: Behavioral deviation score (0-1)
            sigma_level: Sigma deviation level
            context_factors: Additional context (time of day, etc.)
        
        Returns:
            Risk multiplier (1.0 = normal, >1.0 = elevated risk)
        """
        multiplier = 1.0
        
        # Productivity penalty
        if productivity_score < 0.5:
            multiplier *= 1.5
        elif productivity_score < 0.7:
            multiplier *= 1.2
        
        # Signature deviation penalty
        if sigma_level > 2.0:
            multiplier *= 2.0
        elif sigma_level > 1.5:
            multiplier *= 1.5
        elif sigma_level > 1.0:
            multiplier *= 1.2
        
        # Context factors
        if context_factors:
            # After hours penalty
            hour = context_factors.get('hour', 12)
            if hour < 7 or hour > 20:
                multiplier *= 1.3
            
            # Weekend penalty
            if context_factors.get('is_weekend'):
                multiplier *= 1.2
        
        return min(multiplier, 5.0)  # Cap at 5.0
    
    def process_telemetry(
        self,
        telemetry: Dict,
        user_role: str = "Employee",
        baseline: Optional[Dict] = None
    ) -> Dict:
        """
        Process raw telemetry and compute integrity metrics.
        
        Args:
            telemetry: Raw telemetry data
            user_role: User's role
            baseline: User's baseline metrics
        
        Returns:
            Processed metrics dictionary
        """
        # Extract telemetry fields
        active_app = telemetry.get('active_app', '')
        mouse_velocity = telemetry.get('mouse_velocity_avg', 0)
        mouse_std = telemetry.get('mouse_velocity_std', 0)
        flight_time = telemetry.get('keystroke_flight_avg_ms', 0)
        flight_std = telemetry.get('keystroke_flight_std_ms', 0)
        
        # Calculate productivity alignment
        productivity_score, productivity_category, productivity_explanation = \
            self.calculate_productivity_alignment(active_app, user_role)
        
        # Calculate signature deviation
        deviation_score, sigma_level, deviation_interpretation = \
            self.calculate_signature_deviation(
                mouse_velocity, mouse_std,
                flight_time, flight_std,
                baseline
            )
        
        # Get context factors
        context = {
            'hour': datetime.now().hour,
            'is_weekend': datetime.now().weekday() >= 5,
        }
        
        # Calculate risk multiplier
        risk_multiplier = self.calculate_risk_multiplier(
            productivity_score,
            deviation_score,
            sigma_level,
            context
        )
        
        # Calculate anomaly score
        anomaly_score = deviation_score * risk_multiplier
        
        return {
            'productivity_score': productivity_score,
            'productivity_category': productivity_category,
            'productivity_explanation': productivity_explanation,
            'signature_deviation': deviation_score,
            'sigma_level': sigma_level,
            'deviation_interpretation': deviation_interpretation,
            'risk_multiplier': risk_multiplier,
            'anomaly_score': anomaly_score,
        }


# Global instance
integrity_engine = WorkIntegrityEngine()
