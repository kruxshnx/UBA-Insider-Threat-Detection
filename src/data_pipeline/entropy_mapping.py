"""
Dynamic Role-Entropy Mapping Module.

This module implements the "Functional Originality" feature for Vigilant Lens.
It calculates the entropy of user sessions to detect anomalous behavioral patterns:

- Low Entropy: Focused, role-consistent activity (normal behavior)
- High Entropy: Erratic, multi-domain activity (potential insider threat/data hunting)

The entropy calculation is academically defensible and based on:
1. Shannon entropy over activity type distribution
2. Application category transitions
3. Domain/URL diversity
4. Temporal patterns (time-of-day consistency)
"""

import polars as pl
import numpy as np
from scipy.stats import entropy as scipy_entropy
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("uba.data_pipeline.entropy_mapping")


@dataclass
class EntropyMetrics:
    """Structured entropy metrics for a user session."""
    activity_entropy: float  # Shannon entropy over activity types
    app_entropy: float  # Application category entropy
    domain_entropy: float  # Domain/URL diversity entropy
    temporal_entropy: float  # Time-of-day pattern entropy
    composite_entropy: float  # Weighted combination
    entropy_percentile: float  # Compared to baseline (0-100)
    risk_interpretation: str  # "Low", "Medium", "High", "Critical"


class DynamicRoleEntropyMapper:
    """
    Calculates and maps user session entropy against role-based baselines.
    
    The core hypothesis:
    - Normal users exhibit consistent, role-aligned behavioral patterns (low entropy)
    - Insider threats show erratic, exploratory behavior across domains (high entropy)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Entropy calculation parameters
        self.entropy_weights = self.config.get('entropy_weights', {
            'activity': 0.35,
            'app': 0.25,
            'domain': 0.25,
            'temporal': 0.15,
        })
        
        # Risk thresholds (percentile-based)
        self.low_entropy_threshold = self.config.get('low_entropy_threshold', 60)
        self.medium_entropy_threshold = self.config.get('medium_entropy_threshold', 80)
        self.high_entropy_threshold = self.config.get('high_entropy_threshold', 95)
        
        # Role-based baseline multipliers
        # Some roles naturally have higher entropy (e.g., IT support vs data analyst)
        self.role_baseline_multipliers = self.config.get('role_baseline_multipliers', {
            'Admin': 1.3,
            'IT': 1.25,
            'Contractor': 1.15,
            'Employee': 1.0,
            'Analyst': 1.1,
            'Developer': 1.2,
        })
        
        logger.info("DynamicRoleEntropyMapper initialized")
    
    def calculate_activity_entropy(
        self,
        df: pl.DataFrame
    ) -> float:
        """
        Calculate Shannon entropy over activity type distribution.
        
        Activity types might include:
        - File operations (read, write, copy, delete)
        - Network activity (HTTP, FTP, SSH)
        - Application usage (IDE, Office, Browser)
        - Device interactions (USB, printer)
        
        High entropy = user is performing many different types of activities
        Low entropy = user is focused on one type of activity
        """
        if df.height == 0 or 'activity_type' not in df.columns:
            return 0.0
        
        # Get activity type distribution
        activity_counts = df['activity_type'].value_counts()
        probabilities = activity_counts / activity_counts.sum()
        
        # Shannon entropy (base 2 for interpretability)
        ent = scipy_entropy(probabilities, base=2)
        
        # Normalize by maximum possible entropy (log2 of number of unique activities)
        max_entropy = np.log2(len(probabilities)) if len(probabilities) > 1 else 1.0
        normalized_entropy = ent / max_entropy if max_entropy > 0 else 0.0
        
        return normalized_entropy
    
    def calculate_application_entropy(
        self,
        df: pl.DataFrame
    ) -> float:
        """
        Calculate entropy over application categories.
        
        Measures how many different application categories the user switches between.
        High app entropy = frequent context switching, potential distraction or data hunting
        Low app entropy = focused work in single application
        """
        if df.height == 0 or 'app_category' not in df.columns:
            return 0.0
        
        # Get application category distribution
        app_counts = df['app_category'].value_counts()
        probabilities = app_counts / app_counts.sum()
        
        ent = scipy_entropy(probabilities, base=2)
        max_entropy = np.log2(len(probabilities)) if len(probabilities) > 1 else 1.0
        normalized_entropy = ent / max_entropy if max_entropy > 0 else 0.0
        
        return normalized_entropy
    
    def calculate_domain_entropy(
        self,
        df: pl.DataFrame
    ) -> float:
        """
        Calculate entropy over accessed domains/URLs.
        
        High domain entropy = browsing many different domains (potential data exfiltration research)
        Low domain entropy = focused browsing on few domains
        """
        if df.height == 0 or 'domain' not in df.columns:
            return 0.0
        
        # Filter out empty/null domains
        domain_df = df.filter(pl.col('domain').is_not_null())
        
        if domain_df.height == 0:
            return 0.0
        
        domain_counts = domain_df['domain'].value_counts()
        probabilities = domain_counts / domain_counts.sum()
        
        ent = scipy_entropy(probabilities, base=2)
        max_entropy = np.log2(len(probabilities)) if len(probabilities) > 1 else 1.0
        normalized_entropy = ent / max_entropy if max_entropy > 0 else 0.0
        
        return normalized_entropy
    
    def calculate_temporal_entropy(
        self,
        df: pl.DataFrame
    ) -> float:
        """
        Calculate entropy over temporal patterns.
        
        Measures consistency of activity timing.
        High temporal entropy = irregular, unpredictable timing
        Low temporal entropy = consistent, predictable schedule
        """
        if df.height == 0 or 'timestamp' not in df.columns:
            return 0.0
        
        # Extract hour of day
        df = df.with_columns([
            pl.col('timestamp').dt.hour().alias('hour')
        ])
        
        # Get hour distribution
        hour_counts = df['hour'].value_counts()
        probabilities = hour_counts / hour_counts.sum()
        
        ent = scipy_entropy(probabilities, base=2)
        max_entropy = np.log2(len(probabilities)) if len(probabilities) > 1 else 1.0
        normalized_entropy = ent / max_entropy if max_entropy > 0 else 0.0
        
        return normalized_entropy
    
    def calculate_composite_entropy(
        self,
        activity_ent: float,
        app_ent: float,
        domain_ent: float,
        temporal_ent: float
    ) -> float:
        """
        Calculate weighted composite entropy score.
        
        Weights are configurable to emphasize different entropy types
        based on organizational priorities.
        """
        composite = (
            self.entropy_weights['activity'] * activity_ent +
            self.entropy_weights['app'] * app_ent +
            self.entropy_weights['domain'] * domain_ent +
            self.entropy_weights['temporal'] * temporal_ent
        )
        
        return min(1.0, max(0.0, composite))  # Clamp to [0, 1]
    
    def calculate_percentile_rank(
        self,
        composite_entropy: float,
        baseline_entropies: List[float]
    ) -> float:
        """
        Calculate where current entropy falls compared to baseline (30-day history).
        
        Returns: Percentile rank (0-100)
        """
        if not baseline_entropies:
            return 50.0  # Default to median if no baseline
        
        baseline_array = np.array(baseline_entropies)

        # Percentage of baseline values at or below the current entropy
        percentile = (np.sum(baseline_array <= composite_entropy) / len(baseline_array)) * 100

        return percentile
    
    def interpret_entropy_risk(
        self,
        percentile: float,
        role: str = 'Employee'
    ) -> str:
        """
        Interpret entropy percentile as risk level.
        
        Takes role into account - some roles naturally have higher entropy.
        """
        # Adjust thresholds based on role. Roles that naturally exhibit
        # higher entropy (multiplier > 1.0) should require a higher
        # percentile before triggering a given risk level, so we shift the
        # thresholds upward rather than inflating the percentile itself
        # (which could push it past 100 and break the comparison).
        role_mult = self.role_baseline_multipliers.get(role, 1.0)
        low_threshold = min(100.0, self.low_entropy_threshold * role_mult)
        medium_threshold = min(100.0, self.medium_entropy_threshold * role_mult)
        high_threshold = min(100.0, self.high_entropy_threshold * role_mult)

        if percentile >= high_threshold:
            return "Critical"
        elif percentile >= medium_threshold:
            return "High"
        elif percentile >= low_threshold:
            return "Medium"
        else:
            return "Low"
    
    def compute_session_entropy(
        self,
        df: pl.DataFrame,
        baseline_entropies: Optional[List[float]] = None,
        role: str = 'Employee'
    ) -> EntropyMetrics:
        """
        Compute complete entropy metrics for a user session.
        
        Args:
            df: Session telemetry DataFrame
            baseline_entropies: List of historical entropy values for percentile calculation
            role: User role for role-adjusted interpretation
        
        Returns:
            EntropyMetrics dataclass with all entropy measurements
        """
        # Calculate individual entropy components
        activity_ent = self.calculate_activity_entropy(df)
        app_ent = self.calculate_application_entropy(df)
        domain_ent = self.calculate_domain_entropy(df)
        temporal_ent = self.calculate_temporal_entropy(df)
        
        # Calculate composite
        composite = self.calculate_composite_entropy(
            activity_ent, app_ent, domain_ent, temporal_ent
        )
        
        # Calculate percentile rank
        if baseline_entropies:
            percentile = self.calculate_percentile_rank(composite, baseline_entropies)
        else:
            percentile = 50.0  # Default if no baseline
        
        # Interpret risk
        risk_level = self.interpret_entropy_risk(percentile, role)
        
        return EntropyMetrics(
            activity_entropy=activity_ent,
            app_entropy=app_ent,
            domain_entropy=domain_ent,
            temporal_entropy=temporal_ent,
            composite_entropy=composite,
            entropy_percentile=percentile,
            risk_interpretation=risk_level,
        )
    
    def compute_role_entropy_baseline(
        self,
        historical_df: pl.DataFrame,
        role_column: str = 'role'
    ) -> Dict[str, float]:
        """
        Compute entropy baselines per role from historical data.
        
        This establishes what "normal" entropy looks like for each role type.
        """
        logger.info("Computing role-based entropy baselines...")
        
        role_baselines = {}
        
        for role, role_df in historical_df.group_by(role_column):
            # Calculate entropy for this role's historical data
            activity_ent = self.calculate_activity_entropy(role_df)
            app_ent = self.calculate_application_entropy(role_df)
            domain_ent = self.calculate_domain_entropy(role_df)
            temporal_ent = self.calculate_temporal_entropy(role_df)
            
            composite = self.calculate_composite_entropy(
                activity_ent, app_ent, domain_ent, temporal_ent
            )
            
            role_baselines[role] = {
                'composite_mean': composite,
                'activity_mean': activity_ent,
                'app_mean': app_ent,
                'domain_mean': domain_ent,
                'temporal_mean': temporal_ent,
            }
        
        return role_baselines
    
    def detect_entropy_anomalies(
        self,
        current_metrics: EntropyMetrics,
        role_baseline: Dict[str, float],
        threshold_multiplier: float = 2.0
    ) -> Tuple[bool, str]:
        """
        Detect if current entropy is anomalous compared to role baseline.
        
        Returns:
            Tuple of (is_anomalous, explanation)
        """
        baseline_composite = role_baseline.get('composite_mean', 0.5)
        
        # Check if current entropy is significantly higher than baseline
        if current_metrics.composite_entropy > (baseline_composite * threshold_multiplier):
            explanation = (
                f"Entropy anomaly detected: Current composite entropy "
                f"({current_metrics.composite_entropy:.2f}) is {threshold_multiplier}x "
                f"higher than role baseline ({baseline_composite:.2f}). "
                f"This suggests erratic, multi-domain activity inconsistent with "
                f"normal role behavior."
            )
            return True, explanation
        
        return False, ""


def compute_dynamic_entropy(
    session_df: pl.DataFrame,
    historical_df: Optional[pl.DataFrame] = None,
    role: str = 'Employee',
    config: Optional[Dict] = None
) -> Tuple[EntropyMetrics, Dict]:
    """
    Main entry point: Compute dynamic role-entropy mapping.
    
    Args:
        session_df: Current session telemetry
        historical_df: Historical data for baseline (optional)
        role: User role
        config: Configuration dict
    
    Returns:
        Tuple of (EntropyMetrics, metadata dict)
    """
    mapper = DynamicRoleEntropyMapper(config)
    
    # Get baseline if historical data provided
    baseline_entropies = None
    if historical_df is not None:
        # Calculate baseline entropies from historical data
        historical_baseline = mapper.compute_role_entropy_baseline(historical_df)
        if role in historical_baseline:
            baseline_entropies = [historical_baseline[role]['composite_mean']]
    
    # Compute entropy metrics
    metrics = mapper.compute_session_entropy(
        session_df,
        baseline_entropies=baseline_entropies,
        role=role
    )
    
    # Build metadata
    metadata = {
        'role': role,
        'baseline_computed': historical_df is not None,
        'weights_used': mapper.entropy_weights,
        'risk_level': metrics.risk_interpretation,
        'percentile_rank': metrics.entropy_percentile,
    }
    
    return metrics, metadata


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=str, help="Session telemetry parquet")
    parser.add_argument("--historical", type=str, help="Historical baseline parquet")
    parser.add_argument("--role", type=str, default="Employee", help="User role")
    parser.add_argument("--output", type=str, help="Output JSON for metrics")
    args = parser.parse_args()
    
    if args.session:
        session_df = pl.read_parquet(args.session)
        historical_df = pl.read_parquet(args.historical) if args.historical else None
        
        metrics, metadata = compute_dynamic_entropy(
            session_df, historical_df, args.role
        )
        
        print(f"Activity Entropy: {metrics.activity_entropy:.3f}")
        print(f"App Entropy: {metrics.app_entropy:.3f}")
        print(f"Domain Entropy: {metrics.domain_entropy:.3f}")
        print(f"Temporal Entropy: {metrics.temporal_entropy:.3f}")
        print(f"Composite Entropy: {metrics.composite_entropy:.3f}")
        print(f"Percentile: {metrics.entropy_percentile:.1f}")
        print(f"Risk Level: {metrics.risk_interpretation}")
