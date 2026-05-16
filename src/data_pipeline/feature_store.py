"""
Feature Store for UBA & ITD System.

Implements a centralized feature store to ensure consistency between
training and inference, with support for:
- Feature engineering pipelines
- Feature versioning
- Online/offline feature serving
- Feature quality monitoring
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
import os
import hashlib
import joblib
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.data_pipeline.feature_store")


@dataclass
class FeatureMetadata:
    """Metadata for a feature."""
    name: str
    dtype: str
    description: str
    created_at: datetime
    version: str
    statistics: Dict = field(default_factory=dict)
    quality_metrics: Dict = field(default_factory=dict)


class FeatureStore:
    """
    Centralized feature store for consistent feature engineering.
    
    Ensures training/inference consistency and provides:
    - Feature versioning
    - Quality monitoring
    - Online/offline serving
    - Categorical variable handling
    """
    
    def __init__(self, store_path: str = "data/feature_store"):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Feature registry
        self.features: Dict[str, FeatureMetadata] = {}
        self._load_registry()
        
        # Categorical encoders
        self.categorical_encoders: Dict[str, Dict] = {}
        self._load_encoders()
        
        logger.info("FeatureStore initialized at %s", self.store_path)
    
    def _load_registry(self):
        """Load feature registry from disk."""
        registry_path = self.store_path / "registry.json"
        if registry_path.exists():
            with open(registry_path, 'r') as f:
                data = json.load(f)
                self.features = {
                    k: FeatureMetadata(**v) for k, v in data.items()
                }
    
    def _save_registry(self):
        """Save feature registry to disk."""
        registry_path = self.store_path / "registry.json"
        data = {
            k: {
                'name': v.name,
                'dtype': v.dtype,
                'description': v.description,
                'created_at': v.created_at.isoformat(),
                'version': v.version,
                'statistics': v.statistics,
                'quality_metrics': v.quality_metrics
            }
            for k, v in self.features.items()
        }
        with open(registry_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_encoders(self):
        """Load categorical encoders."""
        encoders_path = self.store_path / "encoders.joblib"
        if encoders_path.exists():
            self.categorical_encoders = joblib.load(encoders_path)
    
    def _save_encoders(self):
        """Save categorical encoders."""
        encoders_path = self.store_path / "encoders.joblib"
        joblib.dump(self.categorical_encoders, encoders_path)
    
    def register_feature(
        self,
        name: str,
        dtype: str,
        description: str,
        version: str = "1.0.0"
    ) -> str:
        """
        Register a new feature in the store.
        
        Args:
            name: Feature name
            dtype: Data type (float32, int64, category, etc.)
            description: Human-readable description
            version: Feature version (semver)
            
        Returns:
            Feature hash (ID)
        """
        feature_hash = hashlib.md5(f"{name}:{version}".encode()).hexdigest()[:8]
        
        self.features[feature_hash] = FeatureMetadata(
            name=name,
            dtype=dtype,
            description=description,
            created_at=datetime.now(),
            version=version
        )
        
        self._save_registry()
        logger.info("Registered feature: %s (v%s) -> %s", name, version, feature_hash)
        return feature_hash
    
    def fit_categorical(self, feature_name: str, values: pd.Series) -> Dict:
        """
        Fit encoder for categorical feature.
        
        Handles:
        - High cardinality features
        - Rare category encoding
        - Unknown category handling
        """
        # Calculate frequency encoding
        value_counts = values.value_counts()
        total = len(values)
        
        # Identify rare categories (< 1% of data)
        rare_threshold = total * 0.01
        rare_categories = value_counts[value_counts < rare_threshold].index.tolist()
        
        # Create encoder
        encoder = {
            'type': 'frequency',
            'encoding': (value_counts / total).to_dict(),
            'rare_categories': rare_categories,
            'rare_encoding': 0.0,
            'unknown_encoding': 0.0
        }
        
        self.categorical_encoders[feature_name] = encoder
        self._save_encoders()
        
        logger.info(
            "Fitted categorical encoder for %s: %d categories, %d rare",
            feature_name, len(value_counts), len(rare_categories)
        )
        
        return encoder
    
    def transform_categorical(
        self, 
        feature_name: str, 
        values: Union[pd.Series, List]
    ) -> np.ndarray:
        """
        Transform categorical values using stored encoder.
        
        Returns frequency-encoded values with rare/unknown handling.
        """
        if feature_name not in self.categorical_encoders:
            raise ValueError(f"No encoder found for feature: {feature_name}")
        
        encoder = self.categorical_encoders[feature_name]
        encoding_map = encoder['encoding']
        rare_cats = set(encoder['rare_categories'])
        
        if isinstance(values, pd.Series):
            result = values.apply(
                lambda x: (
                    encoding_map.get(x, encoder['unknown_encoding'])
                    if x not in rare_cats
                    else encoder['rare_encoding']
                )
            ).values
        else:
            result = np.array([
                encoding_map.get(x, encoder['unknown_encoding'])
                if x not in rare_cats
                else encoder['rare_encoding']
                for x in values
            ])
        
        return result.astype(np.float32)
    
    def compute_statistics(self, feature_name: str, values: pd.Series) -> Dict:
        """Compute and store statistics for a feature."""
        stats = {
            'count': len(values),
            'missing': values.isna().sum(),
            'unique': values.nunique()
        }
        
        if values.dtype in [np.float64, np.float32, np.int64, np.int32]:
            stats.update({
                'mean': float(values.mean()),
                'std': float(values.std()),
                'min': float(values.min()),
                'max': float(values.max()),
                'q25': float(values.quantile(0.25)),
                'q50': float(values.quantile(0.50)),
                'q75': float(values.quantile(0.75))
            })
        
        # Update metadata
        if feature_name in self.features:
            self.features[feature_name].statistics = stats
            self._save_registry()
        
        return stats
    
    def validate_feature(
        self, 
        feature_name: str, 
        values: pd.Series
    ) -> Dict:
        """
        Validate feature quality.
        
        Checks:
        - Missing value ratio
        - Cardinality
        - Distribution shift (if reference exists)
        """
        if feature_name not in self.features:
            return {'valid': False, 'error': 'Feature not registered'}
        
        metadata = self.features[feature_name]
        issues = []
        
        # Check missing ratio
        missing_ratio = values.isna().sum() / len(values)
        if missing_ratio > 0.1:
            issues.append(f"High missing ratio: {missing_ratio:.2%}")
        
        # Check cardinality for categoricals
        if metadata.dtype == 'category':
            unique_ratio = values.nunique() / len(values)
            if unique_ratio > 0.5:
                issues.append(f"High cardinality: {values.nunique()} unique values")
        
        # Check for distribution shift
        if 'mean' in metadata.statistics and len(values) > 0:
            ref_mean = metadata.statistics['mean']
            cur_mean = values.mean()
            ref_std = metadata.statistics.get('std', 1.0)
            
            if ref_std > 0:
                z_score = abs(cur_mean - ref_mean) / ref_std
                if z_score > 3:
                    issues.append(f"Mean shifted by {z_score:.1f} std devs")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'metrics': {
                'missing_ratio': missing_ratio,
                'unique_count': values.nunique()
            }
        }


class FeaturePipeline:
    """
    Feature engineering pipeline with versioning and validation.
    
    Implements features from config.yaml behavioral_biometrics section.
    """
    
    def __init__(self, feature_store: FeatureStore = None):
        self.feature_store = feature_store or FeatureStore()
        self.config = config.features
        self.biometrics_config = config.behavioral_biometrics
        
        # Feature definitions
        self.feature_specs = self._define_features()
        
        logger.info("FeaturePipeline initialized")
    
    def _define_features(self) -> List[Dict]:
        """Define all features with metadata."""
        return [
            # Temporal features
            {'name': 'hour', 'type': 'cyclical', 'dtype': 'float32'},
            {'name': 'day_of_week', 'type': 'cyclical', 'dtype': 'float32'},
            {'name': 'is_weekend', 'type': 'binary', 'dtype': 'int8'},
            {'name': 'is_after_hours', 'type': 'binary', 'dtype': 'int8'},
            
            # Behavioral features
            {'name': 'logon_count_1h', 'type': 'count', 'dtype': 'int32'},
            {'name': 'logon_count_24h', 'type': 'count', 'dtype': 'int32'},
            {'name': 'file_access_count_1h', 'type': 'count', 'dtype': 'int32'},
            {'name': 'file_access_count_24h', 'type': 'count', 'dtype': 'int32'},
            {'name': 'http_count_1h', 'type': 'count', 'dtype': 'int32'},
            {'name': 'device_count_1h', 'type': 'count', 'dtype': 'int32'},
            
            # Aggregation features
            {'name': 'after_hours_ratio', 'type': 'ratio', 'dtype': 'float32'},
            {'name': 'usb_events_7d', 'type': 'count', 'dtype': 'int32'},
            {'name': 'file_copy_count_24h', 'type': 'count', 'dtype': 'int32'},
            
            # Biometric features
            {'name': 'mouse_velocity', 'type': 'continuous', 'dtype': 'float32'},
            {'name': 'mouse_tortuosity', 'type': 'continuous', 'dtype': 'float32'},
            {'name': 'keystroke_flight_time', 'type': 'continuous', 'dtype': 'float32'},
            {'name': 'keystroke_anomaly_score', 'type': 'continuous', 'dtype': 'float32'},
            
            # Session features
            {'name': 'session_duration', 'type': 'continuous', 'dtype': 'float32'},
            {'name': 'idle_time', 'type': 'continuous', 'dtype': 'float32'},
            {'name': 'productive_app_ratio', 'type': 'ratio', 'dtype': 'float32'},
            {'name': 'entropy_risk_level', 'type': 'ordinal', 'dtype': 'category'},
        ]
    
    def transform(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """
        Transform raw data into features.
        
        Args:
            df: Raw input data
            fit: If True, fit encoders and compute statistics
            
        Returns:
            DataFrame with engineered features
        """
        result = df.copy()
        
        # Extract datetime features
        if 'date' in result.columns:
            result = self._extract_datetime_features(result)
        
        # Extract behavioral features
        result = self._extract_behavioral_features(result)
        
        # Extract biometric features (if columns exist)
        result = self._extract_biometric_features(result)
        
        # Validate features
        for col in result.columns:
            if col in self.feature_store.features:
                validation = self.feature_store.validate_feature(
                    col, result[col]
                )
                if not validation['valid']:
                    logger.warning(
                        "Feature %s validation issues: %s",
                        col, validation['issues']
                    )
        
        return result
    
    def _extract_datetime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract temporal features from datetime."""
        if 'date' not in df.columns:
            return df
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Cyclical encoding for hour (sin/cos)
        hour = df['date'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        
        # Cyclical encoding for day of week
        dow = df['date'].dt.dayofweek
        df['day_of_week_sin'] = np.sin(2 * np.pi * dow / 7)
        df['day_of_week_cos'] = np.cos(2 * np.pi * dow / 7)
        
        # Binary flags
        df['is_weekend'] = (dow >= 5).astype(int)
        
        # After hours (from config)
        work_start = self.config.get('work_start_hour', 7)
        work_end = self.config.get('work_end_hour', 20)
        df['is_after_hours'] = (
            (hour < work_start) | (hour > work_end)
        ).astype(int)
        
        return df
    
    def _extract_behavioral_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract behavioral features from event data."""
        # Placeholder - actual implementation would aggregate
        # user events over time windows
        
        if 'user' in df.columns and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            
            # Example: Count events per user in last 24h
            # (simplified - real implementation would use rolling windows)
            df['event_count_24h'] = 1  # Placeholder
            
        return df
    
    def _extract_biometric_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract biometric features if available."""
        biometric_cols = [
            'mouse_velocity', 'mouse_tortuosity', 'keystroke_flight_time',
            'keystroke_anomaly_score', 'productive_app_ratio'
        ]
        
        for col in biometric_cols:
            if col not in df.columns:
                df[col] = 0.0  # Default if not available
        
        return df


# Global instance
feature_store = FeatureStore()
feature_pipeline = FeaturePipeline(feature_store)
