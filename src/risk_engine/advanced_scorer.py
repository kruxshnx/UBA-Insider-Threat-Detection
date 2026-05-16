"""
Advanced Risk Scoring Engine with User Differentiation.

Provides intelligent, role-aware risk scoring that adapts to each user's:
- Role-based behavioral patterns
- Historical baseline
- Time-based context
- Application usage patterns
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import math

class AdvancedRiskScorer:
    """
    Advanced risk scorer with user-specific calibration.
    
    Features:
    - Role-based risk thresholds
    - Time-weighted behavioral analysis
    - Anomaly detection with adaptive baselines
    - Multi-factor risk calculation
    """
    
    def __init__(self):
        # Role-specific risk thresholds
        self.role_risk_profiles = {
            'Admin': {
                'base_risk': 15,
                'productivity_weight': 0.3,
                'behavioral_weight': 0.3,
                'entropy_weight': 0.2,
                'context_weight': 0.2,
                'after_hours_multiplier': 2.5,
                'permitted_variance': 0.3
            },
            'Developer': {
                'base_risk': 20,
                'productivity_weight': 0.4,
                'behavioral_weight': 0.3,
                'entropy_weight': 0.2,
                'context_weight': 0.1,
                'after_hours_multiplier': 2.0,
                'permitted_variance': 0.4
            },
            'HR': {
                'base_risk': 18,
                'productivity_weight': 0.45,
                'behavioral_weight': 0.25,
                'entropy_weight': 0.2,
                'context_weight': 0.1,
                'after_hours_multiplier': 2.2,
                'permitted_variance': 0.25
            },
            'Manager': {
                'base_risk': 16,
                'productivity_weight': 0.35,
                'behavioral_weight': 0.3,
                'entropy_weight': 0.2,
                'context_weight': 0.15,
                'after_hours_multiplier': 1.8,
                'permitted_variance': 0.35
            },
            'Employee': {
                'base_risk': 20,
                'productivity_weight': 0.4,
                'behavioral_weight': 0.3,
                'entropy_weight': 0.2,
                'context_weight': 0.1,
                'after_hours_multiplier': 2.0,
                'permitted_variance': 0.3
            }
        }
        
        # Time-based risk periods
        self.time_periods = {
            'work_hours': (9, 17),  # 9 AM - 5 PM
            'evening': (17, 22),     # 5 PM - 10 PM
            'night': (22, 6),        # 10 PM - 6 AM
            'early_morning': (6, 9)  # 6 AM - 9 AM
        }
        
    def calculate_risk_score(
        self,
        user_id: str,
        role: str,
        telemetry_data: Dict,
        baseline: Optional[Dict] = None,
        historical_data: Optional[Dict] = None
    ) -> Tuple[float, Dict]:
        """
        Calculate comprehensive risk score for a user.
        
        Args:
            user_id: User identifier
            role: User's role
            telemetry_data: Current telemetry data
            baseline: User's historical baseline
            historical_data: Additional historical context
            
        Returns:
            Tuple of (risk_score, explanation_dict)
        """
        role_profile = self.role_risk_profiles.get(role, self.role_risk_profiles['Employee'])
        
        # Extract features
        mouse_velocity = telemetry_data.get('mouse_velocity_avg', 0)
        mouse_std = telemetry_data.get('mouse_velocity_std', 0)
        keystroke_flight = telemetry_data.get('keystroke_flight_avg_ms', 0)
        keystroke_std = telemetry_data.get('keystroke_flight_std_ms', 0)
        active_app = telemetry_data.get('active_app', 'unknown')
        
        # Calculate component scores
        productivity_score = self._calculate_productivity_score(
            active_app, role, telemetry_data
        )
        
        behavioral_score = self._calculate_behavioral_score(
            mouse_velocity, mouse_std, keystroke_flight, keystroke_std,
            baseline, role_profile
        )
        
        entropy_score = self._calculate_entropy_score(
            telemetry_data, historical_data
        )
        
        context_score = self._calculate_context_score(
            role_profile, historical_data
        )
        
        # Weighted combination
        risk_score = (
            productivity_score * role_profile['productivity_weight'] +
            behavioral_score * role_profile['behavioral_weight'] +
            entropy_score * role_profile['entropy_weight'] +
            context_score * role_profile['context_weight']
        )
        
        # Apply time-based multiplier
        time_mult = self._get_time_multiplier()
        risk_score *= time_mult
        
        # Cap at 100
        risk_score = min(100, max(0, risk_score))
        
        explanation = {
            'productivity_score': productivity_score,
            'behavioral_score': behavioral_score,
            'entropy_score': entropy_score,
            'context_score': context_score,
            'time_multiplier': time_mult,
            'role_profile': role_profile['base_risk'],
            'factors': self._identify_risk_factors(
                productivity_score, behavioral_score, entropy_score, context_score
            )
        }
        
        return risk_score, explanation
    
    def _calculate_productivity_score(
        self,
        active_app: str,
        role: str,
        telemetry_data: Dict
    ) -> float:
        """Calculate productivity alignment score (0-100)."""
        app_lower = active_app.lower()
        
        # Role-specific permitted apps
        role_apps = {
            'Admin': ['admin', 'console', 'terminal', 'powershell', 'cmd'],
            'Developer': ['code', 'studio', 'terminal', 'git', 'docker', 'pycharm', 'intellij'],
            'HR': ['excel', 'workday', 'successfactors', 'outlook', 'teams'],
            'Manager': ['excel', 'powerpoint', 'outlook', 'teams', 'salesforce', 'hubspot'],
        }
        
        # Productive apps (universal)
        productive_apps = ['excel', 'word', 'powerpoint', 'outlook', 'teams', 'slack', 'zoom']
        
        # Distracting apps
        distracted_apps = ['netflix', 'youtube', 'steam', 'facebook', 'twitter', 'instagram', 'tiktok']
        
        # Check role-permitted apps
        permitted = role_apps.get(role, [])
        if any(app in app_lower for app in permitted):
            return 0  # No risk - using permitted app
        
        # Check productive apps
        if any(app in app_lower for app in productive_apps):
            return 10  # Low risk
        
        # Check distracting apps
        if any(app in app_lower for app in distracted_apps):
            return 80  # High risk
        
        # Unknown app
        return 40  # Medium risk
    
    def _calculate_behavioral_score(
        self,
        mouse_velocity: float,
        mouse_std: float,
        keystroke_flight: float,
        keystroke_std: float,
        baseline: Optional[Dict],
        role_profile: Dict
    ) -> float:
        """Calculate behavioral anomaly score (0-100)."""
        if not baseline:
            return 20  # Default low risk if no baseline
        
        # Get baseline metrics
        baseline_mv = baseline.get('mouse_velocity_avg', 250)
        baseline_mv_std = baseline.get('mouse_velocity_std', 50)
        baseline_kf = baseline.get('keystroke_flight_avg_ms', 120)
        baseline_kf_std = baseline.get('keystroke_flight_std_ms', 30)
        
        # Calculate z-scores
        mv_zscore = abs(mouse_velocity - baseline_mv) / (baseline_mv_std + 1)
        kf_zscore = abs(keystroke_flight - baseline_kf) / (baseline_kf_std + 1)
        
        # Combined behavioral deviation
        combined_zscore = (mv_zscore + kf_zscore) / 2
        
        # Convert to risk score
        if combined_zscore < 1.0:
            return 10  # Normal
        elif combined_zscore < 2.0:
            return 40  # Elevated
        elif combined_zscore < 3.0:
            return 70  # High
        else:
            return 90  # Critical
    
    def _calculate_entropy_score(
        self,
        telemetry_data: Dict,
        historical_data: Optional[Dict]
    ) -> float:
        """Calculate session entropy score (0-100)."""
        # Placeholder - would analyze activity pattern consistency
        return 20
    
    def _calculate_context_score(
        self,
        role_profile: Dict,
        historical_data: Optional[Dict]
    ) -> float:
        """Calculate context-based risk score (0-100)."""
        hour = datetime.now().hour
        is_weekend = datetime.now().weekday() >= 5
        
        # After hours
        if hour < 6 or hour > 22:
            return 60  # Suspicious time
        
        # Weekend
        if is_weekend:
            return 40  # Slightly elevated
        
        return 10  # Normal work hours
    
    def _get_time_multiplier(self) -> float:
        """Get time-based risk multiplier."""
        hour = datetime.now().hour
        is_weekend = datetime.now().weekday() >= 5
        
        # Night time (10 PM - 6 AM)
        if hour >= 22 or hour < 6:
            return 2.5
        
        # Early morning (6 AM - 9 AM)
        if 6 <= hour < 9:
            return 1.5
        
        # Evening (5 PM - 10 PM)
        if 17 <= hour < 22:
            return 1.8
        
        # Weekend
        if is_weekend:
            return 2.0
        
        # Normal work hours
        return 1.0
    
    def _identify_risk_factors(
        self,
        productivity: float,
        behavioral: float,
        entropy: float,
        context: float
    ) -> list:
        """Identify specific risk factors."""
        factors = []
        
        if productivity > 50:
            factors.append("Low productivity alignment")
        
        if behavioral > 50:
            factors.append("Behavioral anomaly detected")
        
        if entropy > 50:
            factors.append("Erratic session pattern")
        
        if context > 50:
            factors.append("Suspicious time context")
        
        return factors


# Global instance
advanced_scorer = AdvancedRiskScorer()
