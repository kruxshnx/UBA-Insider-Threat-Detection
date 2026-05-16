"""
Bayesian Risk Network for Advanced Risk Assessment.

Implements a probabilistic risk scoring engine that:
- Models risk as a probability distribution rather than point estimate
- Captures non-linear interactions between risk factors
- Provides uncertainty quantification
- Supports causal reasoning about threat scenarios
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy import stats
import logging
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.risk_engine.bayesian")


@dataclass
class RiskDistribution:
    """Represents risk as a probability distribution."""
    mean: float
    std: float
    confidence: float
    distribution_type: str = 'beta'
    alpha: float = 1.0  # Beta distribution parameter
    beta: float = 1.0   # Beta distribution parameter
    samples: Optional[np.ndarray] = None  # Monte Carlo samples
    
    def to_dict(self) -> Dict:
        return {
            'mean': self.mean,
            'std': self.std,
            'confidence': self.confidence,
            'distribution_type': self.distribution_type,
            'alpha': self.alpha,
            'beta': self.beta,
            'p90': float(np.percentile(self.samples, 90)) if self.samples is not None else None,
            'p95': float(np.percentile(self.samples, 95)) if self.samples is not None else None,
            'p99': float(np.percentile(self.samples, 99)) if self.samples is not None else None
        }


class BayesianRiskNetwork:
    """
    Bayesian Network for risk assessment.
    
    Models risk factors as nodes in a probabilistic graphical model:
    
    User Role ──► Base Risk ◄── Anomaly Score
                    │
                    ▼
    Time Context ──► Contextual Risk ◄── Activity Type
                    │
                    ▼
    Behavioral ───► Final Risk ◄── Work Integrity
    Indicators      (Posterior)
    
    Each edge represents a conditional probability relationship.
    """
    
    def __init__(self, config_path: str = None):
        self.config = config.risk_scoring
        self.work_integrity_config = self.config.get('work_integrity', {})
        
        # Prior distributions (Beta distribution parameters)
        # Beta is ideal for probabilities [0, 1]
        self.role_priors = {
            'Admin': (7, 3),      # Higher risk prior
            'Contractor': (6, 4),  # Medium-high risk
            'Employee': (5, 5),   # Neutral prior
            'IT': (6, 4),
            'Developer': (5, 5),
            'Analyst': (5, 5)
        }
        
        # Activity risk parameters (likelihood ratios)
        self.activity_likelihoods = {
            'File Copy': 4.0,
            'Connect': 3.0,  # USB
            'File Delete': 2.5,
            'File Write': 1.5,
            'Logon': 1.0,
            'default': 1.0
        }
        
        # Time-based risk multipliers (as likelihood ratios)
        self.time_likelihoods = {
            'after_hours': 2.0,
            'weekend': 1.5,
            'holiday': 1.8,
            'normal': 1.0
        }
        
        # Behavioral indicator weights
        self.behavioral_weights = {
            'usb_frequency': 0.25,
            'file_velocity': 0.20,
            'after_hours_pattern': 0.15,
            'productivity_anomaly': 0.15,
            'session_entropy': 0.15,
            'biometric_anomaly': 0.10
        }
        
        logger.info("BayesianRiskNetwork initialized")
    
    def calculate_risk_distribution(
        self,
        row: pd.Series,
        anomaly_score: float,
        model_type: str = "lstm"
    ) -> RiskDistribution:
        """
        Calculate risk as a probability distribution.
        
        Args:
            row: Event data
            anomaly_score: Raw anomaly score from ML model
            model_type: Type of model that generated the score
            
        Returns:
            RiskDistribution with mean, std, and confidence
        """
        # 1. Calculate prior from user role
        user = row.get('user', '')
        role = self._infer_role(user, row.get('role', 'Employee'))
        prior_alpha, prior_beta = self.role_priors.get(role, (5, 5))
        
        # 2. Update with anomaly score (likelihood)
        likelihood_anomaly = self._anomaly_likelihood(anomaly_score, model_type)
        posterior_alpha = prior_alpha + likelihood_anomaly
        posterior_beta = prior_beta + (1 - likelihood_anomaly)
        
        # 3. Apply contextual multipliers (as additional evidence)
        time_factor = self._time_factor(row)
        activity_factor = self._activity_factor(row.get('activity', ''))
        
        # 4. Behavioral indicators (weighted evidence)
        behavioral_evidence = self._behavioral_evidence(row)
        
        # 5. Work integrity factors
        integrity_evidence = self._work_integrity_evidence(row)
        
        # 6. Combine all evidence
        # Use weighted geometric mean to combine factors
        combined_evidence = (
            likelihood_anomaly * 0.30 +
            time_factor * 0.20 +
            activity_factor * 0.25 +
            behavioral_evidence * 0.15 +
            integrity_evidence * 0.10
        )
        
        # Update posterior distribution
        final_alpha = prior_alpha * combined_evidence
        final_beta = prior_beta * (2 - combined_evidence)
        
        # Ensure valid parameters
        final_alpha = max(1.0, final_alpha)
        final_beta = max(1.0, final_beta)
        
        # Generate Monte Carlo samples for uncertainty quantification
        samples = np.random.beta(final_alpha, final_beta, size=10000)
        
        # Convert from [0,1] to [0,100] scale
        risk_samples = samples * 100
        
        return RiskDistribution(
            mean=float(np.mean(risk_samples)),
            std=float(np.std(risk_samples)),
            confidence=self._calculate_confidence(row, anomaly_score),
            distribution_type='beta',
            alpha=final_alpha,
            beta=final_beta,
            samples=risk_samples
        )
    
    def _anomaly_likelihood(self, score: float, model_type: str) -> float:
        """Convert anomaly score to likelihood ratio."""
        if model_type == "lstm":
            # LSTM scores: typical range 0.0-0.5 for normal, >0.5 anomalous
            if score < 0.16:  # Below mean
                return 0.3 + 0.7 * (score / 0.16)
            else:
                return min(3.0, 1.0 + 2.0 * ((score - 0.16) / 0.12))
        else:
            # Baseline models
            return 1.0 + score
    
    def _time_factor(self, row: pd.Series) -> float:
        """Calculate time-based risk factor."""
        hour = row.get('hour', 12)
        if hasattr(hour, 'hour'):
            hour = hour.hour
        
        # Check if after hours
        work_start = 7
        work_end = 20
        
        if hour < work_start or hour > work_end:
            return self.time_likelihoods['after_hours']
        
        # Check if weekend
        day_of_week = row.get('day_of_week', 0)
        if day_of_week >= 5:
            return self.time_likelihoods['weekend']
        
        return self.time_likelihoods['normal']
    
    def _activity_factor(self, activity: str) -> float:
        """Calculate activity-based risk factor."""
        for pattern, factor in self.activity_likelihoods.items():
            if pattern in activity:
                return factor
        return self.activity_likelihoods['default']
    
    def _behavioral_evidence(self, row: pd.Series) -> float:
        """Calculate weighted behavioral evidence."""
        evidence = 1.0
        
        # USB frequency
        usb_events = row.get('usb_events_7d', 0)
        if usb_events > 3:
            evidence += self.behavioral_weights['usb_frequency'] * min(2.0, usb_events / 3)
        
        # File operation velocity
        file_velocity = row.get('file_op_velocity', 1.0)
        baseline_velocity = row.get('baseline_file_velocity', 1.0)
        if baseline_velocity > 0 and file_velocity > baseline_velocity:
            velocity_ratio = file_velocity / baseline_velocity
            if velocity_ratio > 2:
                evidence += self.behavioral_weights['file_velocity'] * min(1.5, velocity_ratio / 2)
        
        # After-hours pattern
        after_hours_ratio = row.get('after_hours_ratio', 0)
        if after_hours_ratio > 0.3:
            evidence += self.behavioral_weights['after_hours_pattern'] * (after_hours_ratio / 0.3)
        
        return min(3.0, evidence)
    
    def _work_integrity_evidence(self, row: pd.Series) -> float:
        """Calculate work integrity evidence."""
        evidence = 1.0
        
        # Productivity anomaly
        productive_ratio = row.get('productive_app_ratio', 1.0)
        if productive_ratio < 0.5:
            evidence += 0.3 * (0.5 - productive_ratio) / 0.5
        
        # Session entropy
        entropy_risk = row.get('entropy_risk_level', 'Low')
        if entropy_risk == 'Critical':
            evidence *= 1.5
        elif entropy_risk == 'High':
            evidence *= 1.3
        
        # Biometric anomalies
        mouse_anomaly = row.get('mouse_tortuosity_index', 1.0) > 3.0
        keystroke_anomaly = row.get('keystroke_anomaly_score', 0.0) > 0.5
        
        if mouse_anomaly or keystroke_anomaly:
            evidence *= 1.2
        
        return min(3.0, evidence)
    
    def _infer_role(self, user: str, default_role: str) -> str:
        """Infer user role from context or metadata."""
        # In production, this would query a user metadata service
        return default_role
    
    def _calculate_confidence(self, row: pd.Series, anomaly_score: float) -> float:
        """
        Calculate confidence in risk assessment.
        
        Confidence is based on:
        - Data completeness
        - Model agreement
        - Historical accuracy
        """
        confidence = 0.8  # Base confidence
        
        # Reduce confidence if key features are missing
        required_features = ['user', 'activity', 'date']
        missing = sum(1 for f in required_features if f not in row or pd.isna(row.get(f)))
        confidence -= missing * 0.1
        
        # Reduce confidence if anomaly score is unreliable
        if np.isnan(anomaly_score):
            confidence -= 0.2
        
        return max(0.1, min(1.0, confidence))
    
    def compare_scenarios(
        self,
        baseline_row: pd.Series,
        alternative_row: pd.Series,
        anomaly_score: float
    ) -> Dict:
        """
        Compare risk between two scenarios (counterfactual analysis).
        
        Useful for explainability: "What if this happened at 3 PM instead of 3 AM?"
        """
        baseline_dist = self.calculate_risk_distribution(baseline_row, anomaly_score)
        alternative_dist = self.calculate_risk_distribution(alternative_row, anomaly_score)
        
        return {
            'baseline': baseline_dist.to_dict(),
            'alternative': alternative_dist.to_dict(),
            'risk_difference': alternative_dist.mean - baseline_dist.mean,
            'risk_ratio': alternative_dist.mean / max(0.01, baseline_dist.mean),
            'significant': abs(alternative_dist.mean - baseline_dist.mean) > 10
        }


class NonLinearRiskAggregator:
    """
    Non-linear risk aggregation using exponential weighting.
    
    Replaces simple addition with:
    - Exponential decay for old events
    - Multiplicative combination for correlated risk factors
    - Threshold-based escalation
    """
    
    def __init__(self, config_path: str = None):
        self.config = config.risk_scoring
        self.decay_rate = self.config.get('decay_rate', 0.9)
        self.escalation_threshold = self.config.get('critical_threshold', 95)
        
        # Correlation matrix for risk factors
        self.risk_correlations = {
            ('File Copy', 'USB'): 0.8,
            ('After Hours', 'File Copy'): 0.6,
            ('Admin Role', 'High Privilege Activity'): 0.7
        }
        
        logger.info("NonLinearRiskAggregator initialized")
    
    def aggregate_user_risk(
        self,
        user_events: pd.DataFrame,
        risk_scores: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Aggregate risk scores for a user's events.
        
        Uses exponential decay and accounts for:
        - Recency (newer events weighted more)
        - Correlation (related events compound)
        - Severity (high scores dominate)
        
        Returns:
            Tuple of (aggregate_risk, metadata)
        """
        if len(risk_scores) == 0:
            return 0.0, {'count': 0}
        
        # Time decay weights
        if 'date' in user_events.columns:
            user_events['date'] = pd.to_datetime(user_events['date'])
            time_diff = (datetime.now() - user_events['date']).dt.total_seconds() / 86400
            decay_weights = self.decay_rate ** time_diff
        else:
            decay_weights = np.ones(len(risk_scores))
        
        # Exponential severity weighting (high scores get disproportionate weight)
        severity_weights = np.exp(risk_scores / 50)  # Exponential
        severity_weights = severity_weights / severity_weights.max()  # Normalize
        
        # Combined weights
        combined_weights = decay_weights * severity_weights
        
        # Weighted aggregation
        weighted_sum = np.sum(risk_scores * combined_weights)
        weight_total = np.sum(combined_weights)
        
        base_risk = weighted_sum / max(weight_total, 1.0)
        
        # Apply correlation boost
        correlation_boost = self._calculate_correlation_boost(user_events)
        final_risk = base_risk * (1 + correlation_boost)
        
        # Cap at 100
        final_risk = min(100.0, final_risk)
        
        metadata = {
            'event_count': len(risk_scores),
            'base_risk': base_risk,
            'correlation_boost': correlation_boost,
            'max_risk': np.max(risk_scores),
            'avg_risk': np.mean(risk_scores),
            'recency_weighted': True
        }
        
        return final_risk, metadata
    
    def _calculate_correlation_boost(self, events: pd.DataFrame) -> float:
        """
        Calculate additional risk boost for correlated activities.
        
        If user performs multiple related high-risk activities,
        boost the overall risk.
        """
        if len(events) < 2:
            return 0.0
        
        activities = set(events.get('activity', []).tolist())
        
        boost = 0.0
        for (act1, act2), correlation in self.risk_correlations.items():
            if act1 in activities and act2 in activities:
                boost += correlation * 0.1  # 10% boost per correlated pair
        
        return min(0.5, boost)  # Cap at 50% boost


# Global instances
bayesian_network = BayesianRiskNetwork()
nonlinear_aggregator = NonLinearRiskAggregator()
