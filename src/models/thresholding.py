"""
Advanced Thresholding Strategies for Anomaly Detection.

Implements:
- Adaptive thresholding with rolling percentiles
- Extreme Value Theory (EVT) based thresholding
- Business cost-optimized thresholding
- Concept drift detection

All threshold methods are config-driven and support dynamic updates.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List, Optional
from scipy import stats
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.models.thresholding")


@dataclass
class ThresholdResult:
    """Result of threshold calculation with metadata."""
    threshold: float
    method: str
    confidence: float
    metadata: Dict


class AdaptiveThresholding:
    """
    Adaptive thresholding using rolling percentiles and EVT.
    
    Replaces static Mean+N*StdDev with dynamic, distribution-aware methods.
    """
    
    def __init__(self, config_path: str = None):
        self.config = config.thresholds
        self.method = self.config.get('method', 'percentile')
        
        # Rolling window configuration
        self.rolling_window_days = self.config.get('rolling_window_days', 7)
        self.min_samples = self.config.get('min_samples', 100)
        
        # Percentile method config
        self.target_percentile = self.config.get('percentile', 99.5)
        
        # EVT config
        self.evt_threshold_percentile = self.config.get('evt_threshold', 95.0)
        
        # Cost optimization config
        self.false_positive_cost = self.config.get('false_positive_cost', 1.0)
        self.false_negative_cost = self.config.get('false_negative_cost', 10.0)
        
        logger.info("AdaptiveThresholding initialized with method: %s", self.method)
    
    def calculate_threshold(
        self, 
        scores: np.ndarray, 
        method: str = None,
        labels: Optional[np.ndarray] = None,
        timestamps: Optional[pd.Series] = None
    ) -> ThresholdResult:
        """
        Calculate adaptive threshold using specified method.
        
        Args:
            scores: Array of anomaly scores
            method: One of 'percentile', 'evt', 'cost', 'iqr', 'std'
            labels: Optional ground truth labels for cost optimization
            timestamps: Optional timestamps for time-based methods
            
        Returns:
            ThresholdResult with threshold value and metadata
        """
        method = method or self.method
        
        if len(scores) < self.min_samples:
            logger.warning(
                "Only %d samples, using default threshold", 
                len(scores)
            )
            return self._default_threshold()
        
        if method == 'percentile':
            return self._percentile_method(scores)
        elif method == 'evt':
            return self._evt_method(scores)
        elif method == 'cost':
            if labels is None:
                logger.warning("Cost method requires labels, falling back to percentile")
                return self._percentile_method(scores)
            return self._cost_optimized_threshold(scores, labels)
        elif method == 'iqr':
            return self._iqr_method(scores)
        elif method == 'std':
            return self._std_method(scores)
        else:
            raise ValueError(f"Unknown threshold method: {method}")
    
    def _percentile_method(self, scores: np.ndarray) -> ThresholdResult:
        """Calculate threshold using rolling percentile."""
        threshold = np.percentile(scores, self.target_percentile)
        
        # Calculate confidence based on sample size
        confidence = min(1.0, len(scores) / (self.min_samples * 10))
        
        return ThresholdResult(
            threshold=threshold,
            method='percentile',
            confidence=confidence,
            metadata={
                'percentile': self.target_percentile,
                'sample_size': len(scores),
                'score_mean': np.mean(scores),
                'score_std': np.std(scores)
            }
        )
    
    def _evt_method(self, scores: np.ndarray) -> ThresholdResult:
        """
        Calculate threshold using Extreme Value Theory (EVT).
        
        Fits a Generalized Pareto Distribution (GPD) to the tail
        of the score distribution and finds the threshold where
        the probability of exceedance is below a certain level.
        """
        # Select tail data (scores above high percentile)
        tail_cutoff = np.percentile(scores, self.evt_threshold_percentile)
        tail_data = scores[scores > tail_cutoff] - tail_cutoff
        
        if len(tail_data) < 20:
            logger.warning("Insufficient tail data for EVT, falling back to percentile")
            return self._percentile_method(scores)
        
        try:
            # Fit Generalized Pareto Distribution
            shape, loc, scale = stats.genpareto.fit(tail_data)
            
            # Calculate threshold at desired exceedance probability
            # P(X > threshold) = 1 - confidence_level
            confidence_level = 0.999  # 99.9%
            threshold_gpd = stats.genpareto.ppf(confidence_level, shape, loc, scale)
            threshold = tail_cutoff + threshold_gpd
            
            # Goodness of fit test
            ks_stat, p_value = stats.kstest(tail_data, 'genpareto', 
                                           args=(shape, loc, scale))
            
            return ThresholdResult(
                threshold=threshold,
                method='evt',
                confidence=p_value,
                metadata={
                    'shape': shape,
                    'scale': scale,
                    'tail_cutoff': tail_cutoff,
                    'tail_size': len(tail_data),
                    'ks_statistic': ks_stat,
                    'p_value': p_value
                }
            )
        except Exception as e:
            logger.warning("EVT fitting failed: %s, falling back to percentile", e)
            return self._percentile_method(scores)
    
    def _cost_optimized_threshold(
        self, 
        scores: np.ndarray, 
        labels: np.ndarray
    ) -> ThresholdResult:
        """
        Optimize threshold based on business cost function.
        
        Finds threshold that minimizes:
        Cost = FP * cost_fp + FN * cost_fn
        
        Where:
        - FP: False positives
        - FN: False negatives
        - cost_fp: Cost of false positive (alert fatigue)
        - cost_fn: Cost of false negative (missed threat)
        """
        thresholds = np.percentile(scores, np.linspace(90, 99.9, 100))
        best_threshold = thresholds[0]
        best_cost = float('inf')
        best_metrics = {}
        
        for thresh in thresholds:
            predictions = (scores > thresh).astype(int)
            
            # Calculate confusion matrix
            tp = np.sum((predictions == 1) & (labels == 1))
            fp = np.sum((predictions == 1) & (labels == 0))
            fn = np.sum((predictions == 0) & (labels == 1))
            tn = np.sum((predictions == 0) & (labels == 0))
            
            # Calculate cost
            cost = fp * self.false_positive_cost + fn * self.false_negative_cost
            
            if cost < best_cost:
                best_cost = cost
                best_threshold = thresh
                best_metrics = {
                    'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
                    'precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
                    'recall': tp / (tp + fn) if (tp + fn) > 0 else 0,
                    'f1': 0,
                    'total_cost': cost
                }
        
        # Calculate F1
        p = best_metrics.get('precision', 0)
        r = best_metrics.get('recall', 0)
        if p + r > 0:
            best_metrics['f1'] = 2 * (p * r) / (p + r)
        
        return ThresholdResult(
            threshold=best_threshold,
            method='cost',
            confidence=1.0 - (best_cost / (len(scores) * max(self.false_positive_cost, self.false_negative_cost))),
            metadata=best_metrics
        )
    
    def _iqr_method(self, scores: np.ndarray) -> ThresholdResult:
        """Calculate threshold using Interquartile Range (IQR)."""
        q1, q3 = np.percentile(scores, [25, 75])
        iqr = q3 - q1
        
        multiplier = self.config.get('iqr_multiplier', 1.5)
        threshold = q3 + multiplier * iqr
        
        return ThresholdResult(
            threshold=threshold,
            method='iqr',
            confidence=0.8,
            metadata={
                'q1': q1,
                'q3': q3,
                'iqr': iqr,
                'multiplier': multiplier
            }
        )
    
    def _std_method(self, scores: np.ndarray) -> ThresholdResult:
        """Calculate threshold using Mean + N*Std."""
        mean = np.mean(scores)
        std = np.std(scores)
        
        multiplier = self.config.get('std_multiplier', 3.0)
        threshold = mean + multiplier * std
        
        return ThresholdResult(
            threshold=threshold,
            method='std',
            confidence=0.7,
            metadata={
                'mean': mean,
                'std': std,
                'multiplier': multiplier
            }
        )
    
    def _default_threshold(self) -> ThresholdResult:
        """Return default threshold when insufficient data."""
        return ThresholdResult(
            threshold=self.config.get('lstm_anomaly_mean', 0.16) + 
                     3 * self.config.get('lstm_anomaly_std', 0.12),
            method='default',
            confidence=0.5,
            metadata={'reason': 'insufficient_data'}
        )


class ConceptDriftDetector:
    """
    Detect concept drift in anomaly scores over time.
    
    Uses statistical tests to detect when the distribution
    of scores changes significantly, indicating model retraining needed.
    """
    
    def __init__(self, config_path: str = None):
        self.config = config.thresholds
        self.drift_threshold = self.config.get('drift_threshold', 0.05)
        self.window_size = self.config.get('drift_window_size', 1000)
        self.test_method = self.config.get('drift_test', 'ks')  # 'ks' or 'cvm'
        
        # Historical distributions
        self.reference_scores: Optional[np.ndarray] = None
        self.reference_timestamp: Optional[datetime] = None
        
        logger.info("ConceptDriftDetector initialized")
    
    def set_reference_distribution(self, scores: np.ndarray, 
                                   timestamp: datetime = None):
        """Set the reference distribution for drift detection."""
        self.reference_scores = scores.copy()
        self.reference_timestamp = timestamp or datetime.now()
        logger.info("Reference distribution set with %d samples", len(scores))
    
    def detect_drift(self, current_scores: np.ndarray) -> Dict:
        """
        Detect if current scores show significant drift from reference.
        
        Returns:
            Dict with drift_detected (bool), metrics, and recommendations
        """
        if self.reference_scores is None:
            return {
                'drift_detected': False,
                'confidence': 0.0,
                'metrics': {'error': 'No reference distribution'},
                'recommendation': 'Set reference distribution first'
            }
        
        # Ensure same sample size for comparison. Draw a random (seeded)
        # subsample from the larger array rather than head-slicing, which
        # would bias the test toward whichever records happen to come first.
        min_len = min(len(self.reference_scores), len(current_scores))
        rng = np.random.default_rng(42)

        def _subsample(arr: np.ndarray, n: int) -> np.ndarray:
            if len(arr) <= n:
                return arr
            idx = rng.choice(len(arr), size=n, replace=False)
            return arr[idx]

        ref_sample = _subsample(self.reference_scores, min_len)
        cur_sample = _subsample(current_scores, min_len)

        # Perform statistical test
        if self.test_method == 'ks':
            statistic, p_value = stats.ks_2samp(ref_sample, cur_sample)
        elif self.test_method == 'cvm':
            # cramervonmises_2samp returns a result object, not a tuple
            cvm_result = stats.cramervonmises_2samp(ref_sample, cur_sample)
            statistic, p_value = cvm_result.statistic, cvm_result.pvalue
        else:
            raise ValueError(f"Unknown test method: {self.test_method}")
        
        drift_detected = p_value < self.drift_threshold
        
        # Calculate effect size
        mean_diff = np.mean(cur_sample) - np.mean(ref_sample)
        std_diff = np.std(cur_sample) - np.std(ref_sample)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            drift_detected, p_value, mean_diff, std_diff
        )
        
        return {
            'drift_detected': drift_detected,
            'confidence': 1.0 - p_value,
            'metrics': {
                'statistic': statistic,
                'p_value': p_value,
                'mean_difference': mean_diff,
                'std_difference': std_diff,
                'reference_mean': np.mean(ref_sample),
                'current_mean': np.mean(cur_sample)
            },
            'recommendation': recommendation,
            'reference_age_hours': (
                (datetime.now() - self.reference_timestamp).total_seconds() / 3600
                if self.reference_timestamp else None
            )
        }
    
    def _generate_recommendation(
        self, 
        drift_detected: bool, 
        p_value: float,
        mean_diff: float,
        std_diff: float
    ) -> str:
        """Generate actionable recommendation based on drift analysis."""
        if not drift_detected:
            return "No significant drift detected. Model is still valid."
        
        recommendations = []
        
        if mean_diff > 0.1:
            recommendations.append(
                "Mean anomaly score increased significantly. "
                "Consider retraining with recent data."
            )
        
        if std_diff > 0.05:
            recommendations.append(
                "Score variance increased. Behavior patterns may have changed."
            )
        
        if not recommendations:
            recommendations.append(
                "Minor drift detected. Monitor closely and consider "
                "threshold adjustment before full retraining."
            )
        
        return " ".join(recommendations)


class RollingWindowThreshold:
    """
    Threshold calculation with rolling time windows.
    
    Automatically adapts to recent behavior patterns while
    maintaining historical context.
    """
    
    def __init__(self, window_days: int = 7, step_hours: int = 1):
        self.window_days = window_days
        self.step_hours = step_hours
        self.threshold_calculator = AdaptiveThresholding()
        
        # Historical thresholds
        self.threshold_history: List[Tuple[datetime, float]] = []
        
        logger.info("RollingWindowThreshold initialized with %d day window", 
                   window_days)
    
    def update_and_get_threshold(
        self,
        scores: np.ndarray,
        timestamps: pd.Series,
        current_time: datetime = None
    ) -> float:
        """
        Update rolling window and calculate current threshold.
        
        Args:
            scores: All available scores
            timestamps: Corresponding timestamps
            current_time: Current time (defaults to now)
            
        Returns:
            Current adaptive threshold
        """
        current_time = current_time or datetime.now()
        window_start = current_time - timedelta(days=self.window_days)
        
        # Select recent data
        mask = timestamps >= window_start
        recent_scores = scores[mask]
        
        if len(recent_scores) < 50:
            # Use all data if insufficient recent data
            recent_scores = scores
        
        # Calculate threshold
        result = self.threshold_calculator.calculate_threshold(
            recent_scores, 
            method='percentile'
        )
        
        # Store in history
        self.threshold_history.append((current_time, result.threshold))
        
        # Prune old history
        cutoff = current_time - timedelta(days=self.window_days * 2)
        self.threshold_history = [
            (t, th) for t, th in self.threshold_history 
            if t > cutoff
        ]
        
        logger.info(
            "Rolling threshold updated: %.4f (window: %d samples)",
            result.threshold, len(recent_scores)
        )
        
        return result.threshold


# Global instances
adaptive_threshold = AdaptiveThresholding()
drift_detector = ConceptDriftDetector()
rolling_threshold = RollingWindowThreshold()
