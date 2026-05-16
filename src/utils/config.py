"""
Centralized Configuration Loader for UBA & ITD System.
Loads settings from config.yaml and provides easy access throughout the codebase.
"""

import os
import yaml
from typing import Any, Dict, Optional

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


class Config:
    """Singleton configuration class that loads and provides access to config.yaml"""
    
    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                self._config = yaml.safe_load(f)
        else:
            print(f"Warning: Config file not found at {CONFIG_PATH}. Using defaults.")
            self._config = self._get_defaults()
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Return default configuration if YAML not found."""
        return {
            'paths': {
                'data_raw': 'data/raw',
                'data_processed': 'data/processed',
                'risk_output': 'data/risk_output',
                'models_lstm': 'models/lstm',
                'models_baseline': 'models/baseline',
            },
            'lstm': {
                'sequence_length': 10,
                'hidden_dim': 32,
                'num_layers': 2,
                'batch_size': 64,
                'epochs': 10,
                'learning_rate': 0.001,
            },
            'thresholds': {
                'method': 'percentile',
                'percentile': 99.5,
            },
            'risk_scoring': {
                'base_multiplier': 250,
                'max_risk': 100,
                'role_multipliers': {'Admin': 1.5, 'Contractor': 1.2, 'Employee': 1.0},
                'after_hours_multiplier': 1.5,
                'decay_rate': 0.9,
            },
            'alerting': {
                'medium_threshold': 70,
                'high_threshold': 85,
                'persistence_count': 2,
                'cooldown_hours': 24,
            },
            'features': {
                'window_24h': 24,
                'window_7d': 168,
                'work_start_hour': 7,
                'work_end_hour': 20,
            },
            'api': {
                'title': 'UBA ITD API',
                'version': '2.0.0',
                'cors_origins': ['http://localhost:5173', 'http://localhost:5174'],
                'rate_limit_requests': 100,
                'rate_limit_window_seconds': 60,
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config section."""
        return self._config.get(key, default)
    
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value using dot notation."""
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value
    
    # Convenience properties for common access patterns
    @property
    def paths(self) -> Dict[str, str]:
        return self.get('paths', {})
    
    @property
    def lstm(self) -> Dict[str, Any]:
        return self.get('lstm', {})
    
    @property
    def thresholds(self) -> Dict[str, Any]:
        return self.get('thresholds', {})
    
    @property
    def risk_scoring(self) -> Dict[str, Any]:
        return self.get('risk_scoring', {})
    
    @property
    def alerting(self) -> Dict[str, Any]:
        return self.get('alerting', {})
    
    @property
    def features(self) -> Dict[str, Any]:
        return self.get('features', {})
    
    @property
    def mitre_mapping(self) -> Dict[str, Any]:
        return self.get('mitre_mapping', {})
    
    @property
    def api(self) -> Dict[str, Any]:
        return self.get('api', {})
    
    def get_full_path(self, path_key: str) -> str:
        """Get full absolute path for a path config key."""
        relative_path = self.paths.get(path_key, '')
        return os.path.join(PROJECT_ROOT, relative_path)


# Global config instance
config = Config()
