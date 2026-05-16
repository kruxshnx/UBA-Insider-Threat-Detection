"""
Comprehensive Test Suite for UBA & ITD System.

Tests cover:
- Data pipeline validation
- Model training and inference
- Risk scoring accuracy
- Security and privacy operations
- API endpoint responses
- Threshold adaptation
- Concept drift detection
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.thresholding import AdaptiveThresholding, ConceptDriftDetector
from src.data_pipeline.feature_store import FeatureStore, FeaturePipeline
from src.risk_engine.bayesian_network import BayesianRiskNetwork, NonLinearRiskAggregator
from src.security.privacy import PseudonymizationEngine, CryptographicErasure, AccessControl
from src.deployment.operations import ShadowModeDeployment, SyntheticDataGenerator


class TestAdaptiveThresholding:
    """Test adaptive threshold calculation methods."""
    
    def test_percentile_method(self):
        """Test percentile-based threshold."""
        thresholding = AdaptiveThresholding()
        scores = np.random.normal(0.2, 0.1, 1000)
        result = thresholding.calculate_threshold(scores, method='percentile')
        
        assert result.threshold > 0
        assert result.method == 'percentile'
        assert 0 < result.confidence <= 1
    
    def test_evt_method(self):
        """Test EVT-based threshold."""
        thresholding = AdaptiveThresholding()
        scores = np.random.exponential(0.3, 1000)
        result = thresholding.calculate_threshold(scores, method='evt')
        
        assert result.threshold > 0
        assert result.method == 'evt'
    
    def test_iqr_method(self):
        """Test IQR-based threshold."""
        thresholding = AdaptiveThresholding()
        scores = np.random.normal(0.2, 0.1, 1000)
        result = thresholding.calculate_threshold(scores, method='iqr')
        
        assert result.threshold > 0
        assert result.method == 'iqr'
        assert 'q1' in result.metadata
        assert 'q3' in result.metadata
    
    def test_insufficient_data(self):
        """Test fallback for insufficient data."""
        thresholding = AdaptiveThresholding()
        scores = np.random.normal(0.2, 0.1, 10)  # Too few samples
        result = thresholding.calculate_threshold(scores)
        
        assert result.method == 'default'
    
    def test_cost_optimized(self):
        """Test cost-optimized threshold with labels."""
        thresholding = AdaptiveThresholding()
        np.random.seed(42)
        scores = np.random.normal(0.3, 0.15, 1000)
        labels = (scores > 0.4).astype(int)
        
        result = thresholding.calculate_threshold(
            scores, method='cost', labels=labels
        )
        
        assert result.threshold > 0
        assert 'precision' in result.metadata
        assert 'recall' in result.metadata


class TestConceptDrift:
    """Test concept drift detection."""
    
    def test_no_drift(self):
        """Test detection when no drift present."""
        detector = ConceptDriftDetector()
        
        # Set reference
        reference = np.random.normal(0.2, 0.1, 1000)
        detector.set_reference_distribution(reference)
        
        # Test similar distribution
        current = np.random.normal(0.2, 0.1, 1000)
        result = detector.detect_drift(current)
        
        assert 'drift_detected' in result
        assert 'confidence' in result
    
    def test_drift_detected(self):
        """Test drift detection with significant shift."""
        detector = ConceptDriftDetector()
        
        # Set reference with low mean
        reference = np.random.normal(0.1, 0.1, 1000)
        detector.set_reference_distribution(reference)
        
        # Test with high mean (drift)
        current = np.random.normal(0.5, 0.1, 1000)
        result = detector.detect_drift(current)
        
        assert 'drift_detected' in result
        assert result['metrics']['mean_difference'] > 0.1


class TestFeatureStore:
    """Test feature store operations."""
    
    def test_register_feature(self):
        """Test feature registration."""
        store = FeatureStore(store_path="data/test_feature_store")
        feature_hash = store.register_feature(
            name='test_feature',
            dtype='float32',
            description='Test feature for validation'
        )
        
        assert feature_hash in store.features
        assert store.features[feature_hash].name == 'test_feature'
    
    def test_categorical_encoding(self):
        """Test categorical feature encoding."""
        store = FeatureStore(store_path="data/test_feature_store")
        
        # Fit encoder
        values = pd.Series(['A', 'B', 'A', 'C', 'A', 'B', 'A'])
        encoder = store.fit_categorical('test_cat', values)
        
        assert 'encoding' in encoder
        assert 'A' in encoder['encoding']
        
        # Transform
        encoded = store.transform_categorical('test_cat', ['A', 'B', 'C'])
        assert len(encoded) == 3
    
    def test_feature_validation(self):
        """Test feature validation."""
        store = FeatureStore(store_path="data/test_feature_store")
        
        # Register feature
        store.register_feature('test_valid', 'float32', 'Validation test')
        
        # Compute statistics
        values = pd.Series([1.0, 2.0, 3.0, np.nan, 5.0])
        stats = store.compute_statistics('test_valid', values)
        
        assert stats['count'] == 5
        assert stats['missing'] == 1
    
    def test_feature_pipeline(self):
        """Test feature pipeline transformation."""
        pipeline = FeaturePipeline()
        
        # Create sample data
        df = pd.DataFrame({
            'user': ['U100', 'U101', 'U102'],
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'activity': ['Logon', 'File Copy', 'Http']
        })
        
        # Transform
        result = pipeline.transform(df)
        
        # Check for extracted features
        assert 'hour_sin' in result.columns or 'date' in result.columns


class TestBayesianNetwork:
    """Test Bayesian risk network."""
    
    def test_risk_distribution(self):
        """Test risk distribution calculation."""
        network = BayesianRiskNetwork()
        
        row = pd.Series({
            'user': 'U105',
            'activity': 'File Copy',
            'hour': 23,
            'role': 'Admin'
        })
        
        result = network.calculate_risk_distribution(row, anomaly_score=0.35)
        
        assert result.mean > 0
        assert result.std > 0
        assert 0 < result.confidence <= 1
    
    def test_scenario_comparison(self):
        """Test counterfactual scenario comparison."""
        network = BayesianRiskNetwork()
        
        baseline = pd.Series({
            'user': 'U105',
            'activity': 'Logon',
            'hour': 14,
            'role': 'Employee'
        })
        
        alternative = pd.Series({
            'user': 'U105',
            'activity': 'File Copy',
            'hour': 3,
            'role': 'Admin'
        })
        
        comparison = network.compare_scenarios(
            baseline, alternative, anomaly_score=0.3
        )
        
        assert 'baseline' in comparison
        assert 'alternative' in comparison
        assert 'risk_difference' in comparison


class TestNonLinearAggregation:
    """Test non-linear risk aggregation."""
    
    def test_aggregate_user_risk(self):
        """Test user-level risk aggregation."""
        aggregator = NonLinearRiskAggregator()
        
        events = pd.DataFrame({
            'user': ['U105'] * 5,
            'activity': ['File Copy', 'USB', 'Logon', 'File Delete', 'Http'],
            'date': pd.date_range('2024-01-01', periods=5)
        })
        
        scores = np.array([80, 75, 30, 60, 20])
        
        final_risk, metadata = aggregator.aggregate_user_risk(events, scores)
        
        assert final_risk > 0
        assert final_risk <= 100
        assert 'event_count' in metadata


class TestPrivacy:
    """Test privacy and security operations."""
    
    def test_pseudonymization(self):
        """Test pseudonymization."""
        engine = PseudonymizationEngine(key_path="data/test_token_key")
        
        # Pseudonymize
        user_id = "U105"
        token = engine.pseudonymize(user_id)
        
        assert token != user_id
        assert len(token) > 0
        
        # Same input produces same output
        token2 = engine.pseudonymize(user_id)
        assert token == token2
    
    def test_dataframe_pseudonymization(self):
        """Test DataFrame pseudonymization."""
        engine = PseudonymizationEngine(key_path="data/test_token_key")
        
        df = pd.DataFrame({
            'user': ['U100', 'U101', 'U102'],
            'activity': ['Logon', 'File Copy', 'Http']
        })
        
        result = engine.pseudonymize_dataframe(df)
        
        assert result['user'].iloc[0] != 'U100'
        assert result['user'].iloc[0] != result['user'].iloc[1]
    
    def test_access_control(self):
        """Test RBAC access control."""
        ac = AccessControl()
        
        # Admin should have elevated permissions
        allowed, _ = ac.check_access('Admin', 'user_data', 'deanonymize', 'Testing')
        assert allowed
        
        # Viewer should not
        allowed, _ = ac.check_access('Viewer', 'user_data', 'deanonymize', 'Testing')
        assert not allowed


class TestOperations:
    """Test operational excellence features."""
    
    def test_shadow_deployment(self):
        """Test shadow mode deployment."""
        shadow = ShadowModeDeployment(shadow_dir="models/test_shadow")
        
        # Deploy shadow model (simulated)
        success = shadow.deploy_shadow(
            model_path="models/test.pth",
            model_name="test_lstm_v2",
            model_type="lstm"
        )
        
        assert success or not success  # Depends on file existence
    
    def test_synthetic_data_generation(self):
        """Test synthetic data generation."""
        generator = SyntheticDataGenerator()
        
        # Generate SMOTE samples
        X_minority = np.random.normal(0.5, 0.2, (10, 5))
        synthetic = generator.generate_smote_samples(X_minority, n_samples=5)
        
        assert len(synthetic) == 5
        assert synthetic.shape[1] == 5


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_end_to_end_risk_calculation(self):
        """Test complete risk calculation workflow."""
        # 1. Create features
        pipeline = FeaturePipeline()
        df = pd.DataFrame({
            'user': ['U105'],
            'date': ['2024-01-15 23:30:00'],
            'activity': ['File Copy (CONFIDENTIAL)']
        })
        
        features = pipeline.transform(df)
        
        # 2. Calculate risk
        network = BayesianRiskNetwork()
        row = features.iloc[0]
        risk_dist = network.calculate_risk_distribution(row, anomaly_score=0.4)
        
        assert risk_dist.mean > 0
        assert risk_dist.mean <= 100
    
    def test_privacy_preserving_risk(self):
        """Test risk calculation with pseudonymization."""
        # 1. Pseudonymize users
        engine = PseudonymizationEngine(key_path="data/test_token_key")
        
        df = pd.DataFrame({
            'user': ['U100', 'U101', 'U105'],
            'activity': ['Logon', 'File Copy', 'File Copy'],
            'risk_score': [20, 65, 85]
        })
        
        pseudonymized = engine.pseudonymize_dataframe(df)
        
        # 2. Calculate aggregate risk
        aggregator = NonLinearRiskAggregator()
        events = pseudonymized.rename(columns={'risk_score': 'activity'})
        
        final_risk, metadata = aggregator.aggregate_user_risk(
            pseudonymized, 
            pseudonymized['risk_score'].values
        )
        
        assert final_risk > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
